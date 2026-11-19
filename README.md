# OpenReview Score Check

**English** | [한국어](README.ko.md)

A small Chrome Manifest V3 extension that monitors review scores and confidence for papers listed on an OpenReview Authors page.

## Quick start

1. Sign in to OpenReview in Chrome.
2. Open your venue's Authors page (for example, `ICLR.cc/2027/Conference/Authors`).
3. Open `chrome://extensions` and enable **Developer mode**.
4. Select **Load unpacked** and choose this repository folder.
5. Open the extension on the Authors page and select **Add papers from the current Authors page** (`현재 Authors 페이지 논문 추가`).
6. The Authors page can be closed after setup. The extension checks every 15 minutes and sends a Chrome notification when a score or confidence changes.

To track multiple venues (for example ICLR and the October ARR cycle), repeat step 5 on each venue's Authors page. New papers are merged into the existing list by forum ID. Registering the same page again updates existing entries without duplicates or resetting their delivery history. All venues appear in the popup and share the 15-minute checks and selected notification settings.

Chrome must remain running for scheduled checks. If your OpenReview session expires, sign in again and start monitoring from the Authors page.

See [Notification setup](#notification-setup) below to choose and configure a delivery method.

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
- Host access to `127.0.0.1:8765`: send notification requests to the local Python bridge. The bridge requires a private token and binds only to localhost.

## Notes

Review form field names vary by venue. The extension recognizes common score fields such as `rating`, `score`, and `overall assessment`, plus `confidence`. If your venue uses other field names, update the matchers in `service-worker.js`.

This project is not affiliated with OpenReview.

## Notification setup

The popup currently uses Korean labels. English descriptions below include the exact labels you will see.

### Choose a delivery method

| Popup selection | Browser notifications | Python monitor | Local service token | Additional settings |
| --- | --- | --- | --- | --- |
| Browser only (`브라우저 알림만`) | Enabled | Not needed | Not needed | None |
| Email (`이메일`) | Enabled | Required | Required | SMTP settings and recipient address |
| Telegram | Enabled | Required | Required | Telegram bot token and chat ID |
| Email + Telegram (`이메일 + Telegram`) | Enabled | Required | Required | Both SMTP and Telegram settings |

New installations default to **Browser only**. Email or Telegram delivery failures do not prevent paper registration, score updates or browser notifications. Chrome must remain running, and your operating system must allow Chrome notifications.

### Use browser notifications only

1. Sign in to OpenReview and open your venue's Authors page.
2. In the popup, choose **Delivery method → Browser only → Save notification settings** (`알림 보낼 곳 → 브라우저 알림만 → 알림 설정 저장`).
3. Select **Add papers from the current Authors page** (`현재 Authors 페이지 논문 추가`).
4. You can close the Authors page afterward. The extension checks every 15 minutes while Chrome is running.

No Python process, email address, SMTP configuration, Telegram configuration or local service token is needed. Sign in to OpenReview again if your session expires.

### Track multiple venues

Add papers from the ICLR Authors page, then use **Add papers from the current Authors page** (`현재 Authors 페이지 논문 추가`) on the ARR October Authors page too. The extension adds the new papers while keeping existing venues. For ARR, choose the Authors page for the year and month you want to track.

Registering the same page again does not duplicate forum IDs or reset delivery history. All registered venues appear in one popup and use the same notification settings.

### Why Telegram also needs a local service token

When using the extension, requests follow this path:

```text
Chrome extension ── EMAIL_BRIDGE_TOKEN ──> Local Python monitor
                                           ├─ SMTP settings ──> Email
                                           └─ TELEGRAM_BOT_TOKEN + CHAT_ID ──> Telegram
```

| Setting | Purpose | Where to configure it |
| --- | --- | --- |
| `EMAIL_BRIDGE_TOKEN` | Authenticates requests from the extension to the local Python monitor | Set the Python environment variable and paste the same value into **Local service token** (`로컬 알림 서비스 토큰`) in the popup |
| `TELEGRAM_BOT_TOKEN` | Authenticates the Python monitor to Telegram as your bot | Python environment variable only |
| `TELEGRAM_CHAT_ID` | Selects the destination Telegram chat, group or channel | Python environment variable only |
| `SMTP_USERNAME`, `SMTP_PASSWORD`, etc. | Connect the Python monitor to your mail server | Python environment variables only |

`EMAIL_BRIDGE_TOKEN` is a **shared local connection token** whose name is retained for compatibility. Telegram-only delivery through the extension still requires it. Do not paste your Telegram bot token into the popup's local service token field. The extension does not store the bot token or SMTP password.

### Common setup for email and Telegram

Activate a Python 3.10 or newer environment in the project directory and install the dependencies. If you already created the Conda environment:

```sh
conda activate openreview_checker
python -m pip install -r requirements.txt
```

Generate a local service token in the terminal that will run the monitor:

```sh
export EMAIL_BRIDGE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '%s\n' "$EMAIL_BRIDGE_TOKEN"
```

Keep the printed value for the popup's **Local service token** (`로컬 알림 서비스 토큰`) field. A token you choose yourself must contain at least 32 characters. If you generate a new token, save the new value in the popup too.

Set the delivery-specific variables below in the **same terminal**, then run `python monitor.py`. Restart the monitor after changing environment variables; an already running process does not receive the new values. Terminal exports apply only to the current shell session and must be set again in a new terminal. Run the monitor from the project directory.

### Use Telegram

1. Create a bot with [@BotFather](https://t.me/BotFather) and obtain its bot token.
2. Open a chat with the new bot and send `/start`. For a group, add the bot and give it permission to send messages.
3. Set the bot token in the terminal where you completed the common setup:

```sh
export TELEGRAM_BOT_TOKEN='your-bot-token'
```

Find the destination chat ID in the Telegram Bot API's [getUpdates](https://core.telegram.org/bots/api#getupdates) response. After sending your bot a message, this command prints only chat IDs from received messages:

```sh
python - <<'PYTHON'
import json
import os
from urllib.request import urlopen

url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/getUpdates"
with urlopen(url, timeout=30) as response:
    updates = json.load(response)
for update in updates.get("result", []):
    message = update.get("message") or update.get("channel_post") or {}
    chat = message.get("chat", {})
    if "id" in chat:
        print("Chat ID:", chat["id"])
PYTHON
```

If nothing is printed, send a new message to the bot and try again. The command reads that bot's incoming updates, so a bot dedicated to these notifications is easier to configure than one already used by another application.

```sh
export TELEGRAM_CHAT_ID='your-chat-id'
python monitor.py
```

With the monitor running, select **Telegram** in the popup, enter the **Local service token** (`로컬 알림 서비스 토큰`) from the common setup, then select **Save notification settings** (`알림 설정 저장`). Use **Send current review notifications** (`현재 리뷰 알림 보내기`) for a manual send. To enable automatic sends, check **Send additional notifications when new reviews or scores change** (`새 리뷰나 점수가 바뀌면 추가 알림 보내기`) and save.

Telegram-only delivery requires no SMTP settings or recipient email address.

### Use email

Set your mail server details in the terminal where you completed the common setup. This example uses Gmail SMTP. Use an app password or another SMTP credential issued by your mail provider for `SMTP_PASSWORD`.

```sh
export SMTP_HOST='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USERNAME='you@gmail.com'
export SMTP_PASSWORD='your-mail-provider-app-password'
export EMAIL_FROM='you@gmail.com'
python monitor.py
```

`SMTP_PORT` defaults to `587`, using STARTTLS. In the popup, choose **Email** (`이메일`), enter the **Recipient email address** (`받는 이메일 주소`) and **Local service token** (`로컬 알림 서비스 토큰`), then save. Manual and automatic sends work as described for Telegram. Email-only delivery requires no Telegram settings.

### Use both email and Telegram

Set `EMAIL_BRIDGE_TOKEN`, the SMTP variables, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the same terminal, then run `python monitor.py`. In the popup, select **Email + Telegram** (`이메일 + Telegram`) and save the recipient address and local service token.

If only one channel fails, automatic checks retry the failed channel. Manual sends always send again; retrying manually after a partial success can duplicate delivery through the channel that already succeeded.

### Notification contents and runtime status

Email and Telegram messages collect **scores and confidence for all papers first**, followed by links to each paper and original OpenReview review. They omit long review bodies; the original links include the full weaknesses. Private reviews require an OpenReview account with access. Reviews are numbered by note ID, so score changes do not reorder them.

When Chrome fetches reviews and Python only forwards notifications, both Chrome and Python must remain running. The local service accepts connections only on `127.0.0.1:8765` on the same computer. Allow Chrome's local network permission if prompted.

This message is normal:

```text
Background OpenReview polling is not configured; the extension notification bridge is active.
```

It means independent Python polling is not configured and the monitor is waiting for extension requests. This mode does not require `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD` or `OPENREVIEW_PAPERS_JSON`.

After updating the code, reload the extension at `chrome://extensions`. Restart `monitor.py` too if you use email or Telegram.

### Optional Python polling without Chrome

This mode follows `Python → OpenReview checks → Email / Telegram`. Unlike extension-driven checks, it requires OpenReview login credentials in the Python environment.

| Environment variable | Purpose |
| --- | --- |
| `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD` | OpenReview login for Python |
| `OPENREVIEW_PAPERS_JSON` | A JSON array of papers with `venue`, `title` and `forum`; see `papers.example.json`. Multiple venues can share the same array |
| `OPENREVIEW_TOTP_SECRET` | Needed only when unattended login requires authenticator-app MFA |
| `NOTIFICATION_CHANNEL` | `email` (default), `telegram` or `both`; `browser` disables Python's external delivery |
| `EMAIL_TO` | Email recipient; an address saved through the extension takes precedence |
| `POLL_INTERVAL_SECONDS` | Check interval: default 900 seconds, minimum 60 seconds |

Set the SMTP or Telegram variables for your chosen delivery method too. Independent Python polling alone does not require `EMAIL_BRIDGE_TOKEN`. That token is needed when you also connect the extension's settings and send actions.

For example, `export NOTIFICATION_CHANNEL=telegram` selects Telegram for Python polling. If notification settings have been saved through the extension, the settings in `.state/email-settings.json` take precedence over `NOTIFICATION_CHANNEL`. Python checks immediately on startup, then at the configured interval.

The extension's automatic notification checkbox controls only Chrome's sends. Python polls whenever `OPENREVIEW_PAPERS_JSON` is configured. To prevent duplicate messages, enable **either extension automatic sends or independent Python polling**. To run only the extension bridge, stop the monitor, run `unset OPENREVIEW_PAPERS_JSON` in the same terminal, then restart it.

Selecting browser-only attempts to sync the choice to a running local service, but saving browser settings completes even if the service cannot be reached. Python may retain its previous settings in that case, so stop independent Python polling when using only browser notifications. Python alone cannot create Chrome notifications.

### Troubleshooting and stored settings

| Symptom | What to check |
| --- | --- |
| `Missing environment variable: ...` | Set the variable in the terminal running the monitor, then restart it |
| Cannot connect to the local notification service | Check that `monitor.py` is running on the same computer and Chrome has local network permission |
| `Bridge token is invalid` | The popup's local service token must match the monitor's `EMAIL_BRIDGE_TOKEN` |
| Telegram API error | Check the bot token, chat ID, whether you started a chat with the bot, and its permission to send to the destination |
| Browser notifications do not appear | Check that Chrome is running and operating system notifications are enabled for Chrome |
| Duplicate notifications | Check whether both independent Python polling and extension automatic sends are enabled |

Python stores delivery fingerprints per channel in `.state/last-seen.json`. Review text changes are also detected, and unchanged content is not automatically sent again. Long Telegram messages are split to fit the [sendMessage limit](https://core.telegram.org/bots/api#sendmessage). If a batch fails partway through, earlier chunks may be repeated on retry.

Do not commit credentials or `.state/` files. The extension stores the local connection token, recipient address, delivery method and automatic-send preference. SMTP credentials and the Telegram bot token are read only from Python environment variables. Your mail provider or Telegram receives paper titles, venues, scores, confidence and original-review links. This notification feature does not call an AI service.

## Local extension and ChatGPT web handoff

The extension can send a changed official review to a new ChatGPT web chat without an OpenAI API key:

1. Sign in to ChatGPT in Chrome.
2. In the extension popup, enter your analysis instructions and save them.
3. Check the box that allows automatic review transfer and save it.
4. When a score or review changes, the extension opens a background ChatGPT tab, inserts the instructions and review in one user message, and submits it.

The instructions are prepended to the user message; the regular ChatGPT website does not let this extension set a true system-role message. The extension does not read ChatGPT's response back. This optional web handoff is separate from the notification monitor described above, which sends scores, confidence and review links by email or Telegram.

The extension stores the prompt, consent toggle, paper list, score/confidence and last-seen review signatures locally in Chrome. Those signatures contain the extracted review text used to detect changes. Review text is sent to OpenAI when the automatic-transfer box is enabled. Uncheck it to stop automatic transfer. The “send now” button also requires the box to be checked.

Load this directory as an unpacked extension from `chrome://extensions`; scheduled checks run while Chrome is running. ChatGPT must be signed in. If the ChatGPT page changes its composer UI, automatic insertion may stop working and require an extension update.
