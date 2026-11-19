# OpenReview Score Check

A small Chrome Manifest V3 extension that monitors review scores and confidence for papers listed on an OpenReview Authors page.

## Quick start

1. Sign in to OpenReview in Chrome.
2. Open your venue's Authors page (for example, `ICLR.cc/2027/Conference/Authors`).
3. Open `chrome://extensions` and enable **Developer mode**.
4. Select **Load unpacked** and choose this repository folder.
5. Open the extension on the Authors page and select **Start monitoring papers on this Authors page**.
6. The Authors page can be closed after setup. The extension checks every 15 minutes and sends a Chrome notification when a score or confidence changes.

Chrome must remain running for scheduled checks. If your OpenReview session expires, sign in again and start monitoring from the Authors page.

## What it reads

- Paper title and forum ID from the currently open Authors page during setup.
- Review notes and their score and confidence fields through the OpenReview API.
- The extension only receives information that the signed-in OpenReview account is allowed to access.

The extension does not ask for or store your OpenReview password or API token. It stores the configured paper list and last-seen review values in Chrome local extension storage. It contacts `api2.openreview.net` to check the reviews.

## Permissions

- `activeTab` and `scripting`: read paper links from the Authors page when you start monitoring.
- `storage`: keep the monitored paper list and last-seen values between browser sessions.
- `alarms`: schedule the 15-minute check.
- `notifications`: alert when review values change.
- Host access to `openreview.net` and `api2.openreview.net`: read the Authors page and query the OpenReview API.
- Host access to `127.0.0.1:8765`: send email requests to the local Python bridge. The bridge requires a private token and binds only to localhost.

## Notes

Review form field names vary by venue. The extension recognizes common score fields such as `rating`, `score`, and `overall assessment`, plus `confidence`. If your venue uses other field names, update the matchers in `service-worker.js`.

This project is not affiliated with OpenReview.

## 한국어 안내

Authors 페이지를 연 상태에서 확장 프로그램을 한 번 설정하면, 이후 페이지를 닫아도 Chrome이 실행 중인 동안 15분마다 리뷰 점수와 confidence를 확인합니다. 새 값이 생기거나 바뀌면 Chrome 알림을 보냅니다. 로그인 세션이 만료되면 OpenReview에 다시 로그인하고 Authors 페이지에서 감시를 다시 시작하세요.

## AI-free email monitor

`monitor.py` checks the configured OpenReview forums every 15 minutes and emails the review scores and official review text when the review data first appears or changes. It sends no review content to OpenAI, Anthropic, or another AI API. No GitHub Actions workflow is included; run this process on a computer or server that stays on.

### Setup

Install Python 3.10 or newer and the pinned dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Set these variables in the Python service environment. OpenReview credentials and paper JSON are needed for the Python process to poll on its own; the extension's manual email action uses its existing Chrome OpenReview login instead.

- `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD` — for Python background polling
- `OPENREVIEW_PAPERS_JSON` — a JSON array of papers with `venue`, `title`, and `forum`; see `papers.example.json`; for Python background polling
- `OPENREVIEW_TOTP_SECRET` only if unattended OpenReview login requires authenticator-app MFA
- `SMTP_HOST` — for Gmail, `smtp.gmail.com`
- `SMTP_PORT` — optional; defaults to `587` with STARTTLS
- `SMTP_USERNAME` and `SMTP_PASSWORD` — use an app password or mail-provider credential
- `EMAIL_FROM`
- `EMAIL_TO` — optional fallback recipient; an address saved in the extension takes precedence
- `EMAIL_BRIDGE_TOKEN` — a private random token of at least 32 characters; the extension uses it to authenticate to the local mail service
- `POLL_INTERVAL_SECONDS` — optional; defaults to `900` (15 minutes), with a 60-second minimum

Generate a bridge token in the same terminal or service environment used to start the monitor:

```sh
export EMAIL_BRIDGE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '%s\n' "$EMAIL_BRIDGE_TOKEN"
```

Copy the printed token into the extension's **로컬 이메일 서비스 토큰** field. Keep it private. The monitor's email bridge listens only on `127.0.0.1`; the extension and monitor must run on the same computer. If Chrome asks to let the extension connect to the local network or loopback address, allow it for this local mail bridge.

Start the monitor with:

```sh
python monitor.py
```

If `OPENREVIEW_PAPERS_JSON` is set, it checks immediately on startup, then repeats at the configured interval. Keep the process running under your operating system's service manager for unattended monitoring. On the first run, if scores are already available, it emails the current official reviews; later emails are sent only when the extracted review fields change. The local `.state/last-seen.json` file stores SHA-256 fingerprints for change detection, not review text. Without `OPENREVIEW_PAPERS_JSON`, it runs only the local bridge used by the extension.

In the Chrome extension popup, enter the recipient address and bridge token, then select **이메일 설정 저장**. The saved recipient is used by both the periodic monitor and the extension's **현재 리뷰를 이메일로 보내기** button. That button sends one email containing the current scored official reviews for all monitored papers. You can also enable **새 리뷰나 점수가 바뀌면 자동 이메일 보내기**; when enabled, the extension emails each changed paper during its 15-minute checks. This option is off by default. To avoid duplicate messages, use either the extension's automatic email option with bridge-only mode (leave `OPENREVIEW_PAPERS_JSON` unset), or Python background polling with the extension option off. SMTP credentials stay in the Python monitor's environment; the extension stores only the local bridge token, recipient, and automatic-email preference in Chrome's local extension storage. If the bridge is unavailable, the extension cannot send or change the monitor's recipient.

OpenReview credentials and SMTP credentials are read from environment variables. Do not commit them to the repository. The monitor sends review text and scores to the configured email address over SMTP with TLS; your mail provider processes that message. It does not call an AI service.

The Chrome extension's optional ChatGPT web handoff described below is separate from this email monitor and remains opt-in.

## Local extension and ChatGPT web handoff

The extension can send a changed official review to a new ChatGPT web chat without an OpenAI API key:

1. Sign in to ChatGPT in Chrome.
2. In the extension popup, enter your analysis instructions and save them.
3. Check the box that allows automatic review transfer and save it.
4. When a score or review changes, the extension opens a background ChatGPT tab, inserts the instructions and review in one user message, and submits it.

The instructions are prepended to the user message; the regular ChatGPT website does not let this extension set a true system-role message. The extension does not read ChatGPT's response back. This optional web handoff is separate from the AI-free email monitor above, which sends review text and scores directly by email.

The extension stores the prompt, consent toggle, paper list, and last-seen score/confidence locally in Chrome. It does not persist review text after sending. Review text is sent to OpenAI when the automatic-transfer box is enabled. Uncheck it to stop automatic transfer. The “send now” button also requires the box to be checked.

Load this directory as an unpacked extension from `chrome://extensions`; scheduled checks run while Chrome is running. ChatGPT must be signed in. If the ChatGPT page changes its composer UI, automatic insertion may stop working and require an extension update.
