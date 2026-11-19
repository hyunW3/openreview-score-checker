"""Email changed official OpenReview reviews without calling an AI service."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import smtplib
import ssl
import sys
import time
from email.message import EmailMessage
from email.utils import getaddresses
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlsplit

import openreview

API_BASE = "https://api2.openreview.net"
STATE_PATH = Path(".state/last-seen.json")
EMAIL_SETTINGS_PATH = Path(".state/email-settings.json")
DEFAULT_POLL_INTERVAL_SECONDS = 15 * 60
MIN_POLL_INTERVAL_SECONDS = 60
DEFAULT_EMAIL_BRIDGE_PORT = 8765
MAX_EMAIL_REQUEST_BYTES = 4 * 1024 * 1024
REVIEW_FIELDS = ("score", "confidence", "summary", "strengths", "weaknesses", "questions", "review")


class OpenReviewAuthenticationError(RuntimeError):
    """Raised when the OpenReview login needs to be renewed."""


def value_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict) and "value" in value:
        return value_of(value["value"])
    if isinstance(value, list):
        return ", ".join(filter(None, (value_of(item) for item in value)))
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def field(content: dict[str, Any], names: set[str]) -> str:
    for key, value in content.items():
        normalized = "".join(char for char in key.lower() if char.isalnum())
        if normalized in names:
            rendered = value_of(value)
            if rendered:
                return rendered
    return ""


def openreview_client() -> Any:
    username = os.environ["OPENREVIEW_USERNAME"]
    password = os.environ["OPENREVIEW_PASSWORD"]
    kwargs: dict[str, Any] = {
        "baseurl": API_BASE,
        "username": username,
        "password": password,
    }
    totp_secret = os.getenv("OPENREVIEW_TOTP_SECRET")
    if totp_secret:
        import pyotp

        kwargs["mfa_code_provider"] = lambda _method: pyotp.TOTP(totp_secret).now()
    return openreview.api.OpenReviewClient(**kwargs)


def configured_papers() -> list[dict[str, str]]:
    raw = os.environ["OPENREVIEW_PAPERS_JSON"]
    papers = json.loads(raw)
    if not isinstance(papers, list) or not papers:
        raise ValueError("OPENREVIEW_PAPERS_JSON must be a non-empty JSON array")
    for paper in papers:
        for key in ("venue", "title", "forum"):
            if not paper.get(key):
                raise ValueError(f"Each paper needs a {key!r} value")
    return papers


def official_reviews(client: Any, forum: str) -> list[dict[str, str]]:
    response = client.session.get(
        f"{API_BASE}/notes",
        params={"forum": forum, "limit": 100},
        timeout=30,
    )
    if response.status_code in (401, 403):
        raise OpenReviewAuthenticationError("OpenReview login expired")
    response.raise_for_status()
    notes = response.json().get("notes", [])
    extracted: list[dict[str, str]] = []
    for note in notes:
        invitations = note.get("invitations") or [note.get("invitation", "")]
        if not any(str(invitation).endswith("Official_Review") for invitation in invitations):
            continue
        content = note.get("content") or {}
        review = {
            "score": field(content, {"rating", "score", "overallassessment", "overallrating"}),
            "confidence": field(content, {"confidence", "reviewerconfidence"}),
            "summary": field(content, {"summary", "reviewsummary", "tldr"}),
            "strengths": field(content, {"strengths", "strength"}),
            "weaknesses": field(content, {"weaknesses", "weakness"}),
            "questions": field(content, {"questions", "questionsforauthors"}),
            "review": field(content, {"review", "mainreview", "detailedreview"}),
        }
        if any(review.values()):
            extracted.append({key: value for key, value in review.items() if value})
    return extracted


def email_recipient() -> str:
    if EMAIL_SETTINGS_PATH.exists():
        settings = json.loads(EMAIL_SETTINGS_PATH.read_text(encoding="utf-8"))
        return validate_email_recipient(settings.get("emailTo", ""))
    return validate_email_recipient(os.getenv("EMAIL_TO", ""))


def validate_email_recipient(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 254 or "\r" in value or "\n" in value:
        raise ValueError("Enter one valid recipient email address")
    recipient = value.strip()
    addresses = getaddresses([recipient])
    if len(addresses) != 1:
        raise ValueError("Enter one recipient email address")
    display_name, address = addresses[0]
    if display_name or address != recipient or "@" not in address or any(char.isspace() for char in address):
        raise ValueError("Enter one valid recipient email address")
    return recipient


def review_text(paper: dict[str, Any], reviews: list[dict[str, str]]) -> str:
    review_sections = []
    field_labels = [
        ("Score", "score"),
        ("Confidence", "confidence"),
        ("Summary", "summary"),
        ("Strengths", "strengths"),
        ("Weaknesses", "weaknesses"),
        ("Questions", "questions"),
        ("Review", "review"),
    ]
    for index, review in enumerate(reviews, start=1):
        content = "\n\n".join(
            f"{label}:\n{review[key]}" for label, key in field_labels if review.get(key)
        )
        review_sections.append(f"Review {index}\n{'-' * 40}\n{content}")
    return (
        f"Venue: {paper['venue']}\n"
        f"Paper: {paper['title']}\n\n"
        "Official reviews and scores:\n\n"
        + "\n\n".join(review_sections)
        + "\n\nSent directly from OpenReview. No AI service was called."
    )


def send_message(message: EmailMessage) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT") or "587")
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def send_email(paper: dict[str, str], reviews: list[dict[str, str]], recipient: str | None = None) -> None:
    message = EmailMessage()
    message["Subject"] = f"[OpenReview] {paper['title']} — review update"
    message["From"] = os.environ["EMAIL_FROM"]
    message["To"] = validate_email_recipient(recipient) if recipient else email_recipient()
    message.set_content(review_text(paper, reviews))
    send_message(message)


def send_email_batch(papers: list[dict[str, Any]], recipient: str) -> None:
    message = EmailMessage()
    message["Subject"] = "[OpenReview] Current review scores and reviews"
    message["From"] = os.environ["EMAIL_FROM"]
    message["To"] = validate_email_recipient(recipient)
    message.set_content("\n\n".join(review_text(paper, paper["reviews"]) for paper in papers))
    send_message(message)


def load_state() -> dict[str, str]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check_once(client: Any, papers: list[dict[str, str]], state: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    failures: list[str] = []

    for paper in papers:
        key = paper["forum"]
        try:
            reviews = official_reviews(client, key)
            scores_available = any(item.get("score") for item in reviews)
            if not scores_available:
                continue
            fingerprint = hashlib.sha256(
                json.dumps(reviews, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if state.get(key) == fingerprint:
                continue

            send_email(paper, reviews)
            state[key] = fingerprint
            save_state(state)
            print(f"Sent review update for {paper['title']}.")
        except OpenReviewAuthenticationError:
            raise
        except Exception as error:  # Keep other configured papers moving.
            failures.append(f"{paper['title']}: {type(error).__name__}")

    save_state(state)
    return state, failures


def is_extension_origin(origin: str) -> bool:
    parsed = urlsplit(origin)
    return parsed.scheme == "chrome-extension" and bool(parsed.netloc) and not parsed.path


def save_email_settings(email_to: str, email_auto: bool = False) -> None:
    recipient = validate_email_recipient(email_to)
    EMAIL_SETTINGS_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = EMAIL_SETTINGS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"emailTo": recipient, "emailAuto": bool(email_auto)}), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(EMAIL_SETTINGS_PATH)
    os.chmod(EMAIL_SETTINGS_PATH.parent, 0o700)


def validate_email_request(payload: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("Invalid email request")
    recipient = validate_email_recipient(payload.get("recipient", ""))
    papers = payload.get("papers")
    if not isinstance(papers, list) or not papers or len(papers) > 50:
        raise ValueError("Select at least one monitored paper")

    prepared = []
    for paper in papers:
        if not isinstance(paper, dict):
            raise ValueError("Invalid paper data")
        title, venue = paper.get("title"), paper.get("venue")
        reviews = paper.get("reviews")
        if not isinstance(title, str) or not title.strip() or len(title) > 500:
            raise ValueError("Invalid paper title")
        if not isinstance(venue, str) or not venue.strip() or len(venue) > 500:
            raise ValueError("Invalid venue")
        if not isinstance(reviews, list) or not reviews or len(reviews) > 100:
            raise ValueError("No official reviews with scores were found")
        safe_reviews = []
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError("Invalid review data")
            safe_review = {}
            for key in REVIEW_FIELDS:
                value = review.get(key)
                if value is not None:
                    if not isinstance(value, str) or len(value) > 500_000:
                        raise ValueError("Invalid review field")
                    safe_review[key] = value
            if safe_review:
                safe_reviews.append(safe_review)
        if not safe_reviews:
            raise ValueError("No review content was found")
        prepared.append({"title": title.strip(), "venue": venue.strip(), "reviews": safe_reviews})
    return recipient, prepared


def start_email_bridge() -> ThreadingHTTPServer | None:
    token = os.getenv("EMAIL_BRIDGE_TOKEN", "").strip()
    if len(token) < 32:
        print("Email extension bridge disabled: EMAIL_BRIDGE_TOKEN must be at least 32 characters.", file=sys.stderr)
        return None
    port = DEFAULT_EMAIL_BRIDGE_PORT

    class EmailBridgeHandler(BaseHTTPRequestHandler):
        server_version = "OpenReviewEmailBridge"
        sys_version = ""

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def send_json(self, status: int, body: dict[str, Any]) -> None:
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            origin = self.headers.get("Origin", "")
            if is_extension_origin(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            return hmac.compare_digest(supplied, f"Bearer {token}")

        def do_OPTIONS(self) -> None:
            origin = self.headers.get("Origin", "")
            if not is_extension_origin(origin):
                self.send_json(403, {"ok": False, "error": "Extension origin required"})
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

        def do_GET(self) -> None:
            self.send_json(404, {"ok": False, "error": "Not found"})

        def do_POST(self) -> None:
            if not is_extension_origin(self.headers.get("Origin", "")):
                self.send_json(403, {"ok": False, "error": "Extension origin required"})
                return
            if not self.authorized():
                self.send_json(401, {"ok": False, "error": "Bridge token is invalid"})
                return
            if self.headers.get_content_type() != "application/json":
                self.send_json(415, {"ok": False, "error": "JSON is required"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > MAX_EMAIL_REQUEST_BYTES:
                    raise ValueError("Email request is too large or empty")
                payload = json.loads(self.rfile.read(size))
                if self.path == "/settings":
                    if not isinstance(payload, dict):
                        raise ValueError("Invalid email settings")
                    if "emailAuto" in payload and not isinstance(payload["emailAuto"], bool):
                        raise ValueError("Invalid automatic email setting")
                    save_email_settings(payload.get("emailTo", ""), payload.get("emailAuto", False))
                    self.send_json(200, {"ok": True})
                    return
                if self.path != "/send-now":
                    self.send_json(404, {"ok": False, "error": "Not found"})
                    return
                recipient, papers = validate_email_request(payload)
                send_email_batch(papers, recipient)
                self.send_json(200, {"ok": True, "paperCount": len(papers)})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"ok": False, "error": str(error)})
            except Exception as error:
                self.send_json(502, {"ok": False, "error": f"Email send failed ({type(error).__name__})"})

    server = ThreadingHTTPServer(("127.0.0.1", port), EmailBridgeHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    print(f"Email extension bridge listening on 127.0.0.1:{port}.")
    return server


def main() -> None:
    try:
        bridge = start_email_bridge()
    except Exception as error:
        print(f"Email extension bridge failed to start ({type(error).__name__}).", file=sys.stderr)
        bridge = None

    if not os.getenv("OPENREVIEW_PAPERS_JSON", "").strip():
        if bridge is None:
            raise RuntimeError("Configure OPENREVIEW_PAPERS_JSON or enable the email bridge with EMAIL_BRIDGE_TOKEN")
        print("Background OpenReview polling is not configured; the extension email bridge is active.")
        while True:
            time.sleep(3600)

    papers = configured_papers()
    state = load_state()
    interval = max(
        MIN_POLL_INTERVAL_SECONDS,
        int(os.getenv("POLL_INTERVAL_SECONDS") or DEFAULT_POLL_INTERVAL_SECONDS),
    )

    client = None
    while True:
        try:
            if client is None:
                client = openreview_client()
            state, failures = check_once(client, papers, state)
            if failures:
                print("\n".join(failures), file=sys.stderr)
        except OpenReviewAuthenticationError:
            client = None
            print("OpenReview login expired; will retry login on the next check.", file=sys.stderr)
        except Exception as error:
            print(f"Monitor cycle failed: {type(error).__name__}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    main()
