# OpenReview Score Check

A small Chrome Manifest V3 extension that monitors review scores and confidence for papers listed on an OpenReview Authors page.

## Quick start

1. Sign in to OpenReview in Chrome.
2. Open your venue's Authors page (for example, `ICLR.cc/2027/Conference/Authors`).
3. Open `chrome://extensions` and enable **Developer mode**.
4. Select **Load unpacked** and choose this repository folder.
5. Open the extension on the Authors page and select **현재 Authors 페이지 논문 추가**.
6. The Authors page can be closed after setup. The extension checks every 15 minutes and sends a Chrome notification when a score or confidence changes.

To track multiple venues (for example ICLR and the October ARR cycle), repeat step 5 on each venue's Authors page. New papers are merged into the existing list by forum ID. Registering the same page again updates existing entries without duplicates or resetting their delivery history. All venues appear in the popup and share the 15-minute checks and selected notification settings.

Chrome must remain running for scheduled checks. If your OpenReview session expires, sign in again and start monitoring from the Authors page.

알림 방식별 설정은 아래 [알림 설정 안내](#알림-설정-안내)를 참고하세요.

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

## 알림 설정 안내

### 어떤 방식으로 받을 수 있나요?

| 팝업의 알림 보낼 곳 | 브라우저 알림 | Python 모니터 | 로컬 서비스 토큰 | 추가 설정 |
| --- | --- | --- | --- | --- |
| 브라우저 알림만 | 사용 | 불필요 | 불필요 | 없음 |
| 이메일 | 사용 | 필요 | 필요 | SMTP 설정, 받는 이메일 주소 |
| Telegram | 사용 | 필요 | 필요 | Telegram 봇 토큰, Chat ID |
| 이메일 + Telegram | 사용 | 필요 | 필요 | SMTP와 Telegram 설정 모두 |

새로 설치하면 **브라우저 알림만**이 기본입니다. 이메일·Telegram 전송이 실패해도 논문 등록, 점수 갱신과 브라우저 알림은 계속됩니다. 브라우저 알림을 받으려면 Chrome이 실행 중이어야 하며, 운영체제에서 Chrome 알림을 허용해야 합니다.

### 브라우저 알림만 사용하기

1. OpenReview에 로그인하고 원하는 venue의 Authors 페이지를 엽니다.
2. 확장 팝업에서 **알림 보낼 곳 → 브라우저 알림만 → 알림 설정 저장**을 누릅니다.
3. **현재 Authors 페이지 논문 추가**를 누릅니다.
4. 이후 Authors 페이지를 닫아도 Chrome이 실행 중이면 15분마다 확인합니다.

Python 실행, 이메일 주소, SMTP 설정, Telegram 설정, 로컬 서비스 토큰은 필요하지 않습니다. OpenReview 로그인이 만료되면 다시 로그인하세요.

### 여러 venue 함께 감시하기

ICLR Authors 페이지에서 논문을 추가한 뒤, ARR October Authors 페이지에서도 **현재 Authors 페이지 논문 추가**를 누르세요. 기존 venue를 유지하면서 새 논문을 추가합니다. ARR은 원하는 연도와 월의 Authors 페이지를 사용하세요.

같은 페이지를 다시 등록해도 forum ID가 같은 논문은 중복되지 않고 발송 기록도 유지됩니다. 등록한 모든 venue를 같은 팝업에서 확인하며, 같은 알림 설정으로 감시합니다.

### Telegram에도 로컬 서비스 토큰이 필요한 이유

확장 프로그램을 사용할 때의 전송 경로는 다음과 같습니다.

```text
Chrome 확장 프로그램 ── EMAIL_BRIDGE_TOKEN ──> 로컬 Python 모니터
                                                ├─ SMTP 설정 ──> 이메일
                                                └─ TELEGRAM_BOT_TOKEN + CHAT_ID ──> Telegram
```

| 설정 | 역할 | 설정하는 곳 |
| --- | --- | --- |
| `EMAIL_BRIDGE_TOKEN` | 확장 프로그램이 로컬 Python 모니터에 요청할 때 인증 | Python 환경 변수와 팝업의 **로컬 알림 서비스 토큰**에 같은 값 입력 |
| `TELEGRAM_BOT_TOKEN` | Python 모니터가 Telegram 봇으로 메시지를 전송할 때 인증 | Python 환경 변수에만 설정 |
| `TELEGRAM_CHAT_ID` | Telegram 메시지를 받을 개인 채팅·그룹·채널 지정 | Python 환경 변수에만 설정 |
| `SMTP_USERNAME`, `SMTP_PASSWORD` 등 | Python 모니터가 메일 서버에 연결할 때 사용 | Python 환경 변수에만 설정 |

`EMAIL_BRIDGE_TOKEN`은 기존 설정과의 호환성을 위해 이름을 유지한 **공통 연결 토큰**입니다. Telegram만 사용해도 필요합니다. Telegram 봇 토큰을 팝업의 로컬 서비스 토큰 칸에 넣으면 안 됩니다. 봇 토큰과 SMTP 비밀번호는 확장 프로그램에 저장하지 않습니다.

### 이메일·Telegram 공통 준비

프로젝트 폴더에서 Python 3.10 이상 환경을 활성화하고 의존성을 설치합니다. Conda 환경을 만든 경우 다음과 같이 실행할 수 있습니다.

```sh
conda activate openreview_checker
python -m pip install -r requirements.txt
```

모니터를 실행할 터미널에서 로컬 서비스 토큰을 생성합니다.

```sh
export EMAIL_BRIDGE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '%s\n' "$EMAIL_BRIDGE_TOKEN"
```

출력된 값을 팝업의 **로컬 알림 서비스 토큰**에 입력할 수 있도록 보관하세요. 직접 정한다면 32자 이상이어야 합니다. 토큰을 새로 생성하면 팝업에도 새 값을 저장해야 합니다.

아래에서 사용할 방식의 환경 변수를 **같은 터미널에** 설정한 다음 `python monitor.py`를 실행하세요. 환경 변수는 실행 중인 프로세스에 자동 반영되지 않으므로, 설정을 바꾸면 모니터를 재시작해야 합니다. `export`는 현재 터미널 세션에만 적용되며 새 터미널에서는 다시 설정해야 합니다. 모니터는 프로젝트 폴더에서 실행하세요.

### Telegram 사용하기

1. Telegram의 [@BotFather](https://t.me/BotFather)에서 봇을 만들고 봇 토큰을 발급받습니다.
2. 만든 봇과의 채팅을 열고 `/start`를 보냅니다. 그룹을 사용한다면 봇을 추가하고 메시지를 보낼 수 있도록 권한을 설정합니다.
3. 공통 준비를 마친 터미널에서 봇 토큰을 설정합니다.

```sh
export TELEGRAM_BOT_TOKEN='발급받은-봇-토큰'
```

Chat ID는 Telegram Bot API의 [getUpdates](https://core.telegram.org/bots/api#getupdates) 응답에서 확인합니다. 봇에 메시지를 보낸 뒤 다음 명령으로 수신한 메시지의 Chat ID만 출력할 수 있습니다.

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

출력이 없으면 봇에 새 메시지를 보내고 다시 확인하세요. 이 명령은 해당 봇의 수신 업데이트를 조회하므로 다른 앱에서 이미 사용 중인 봇보다는 이 알림용으로 만든 봇을 사용하면 설정하기 쉽습니다.

```sh
export TELEGRAM_CHAT_ID='확인한-Chat-ID'
python monitor.py
```

모니터가 실행되면 팝업에서 **Telegram**을 선택하고, 공통 준비에서 만든 **로컬 알림 서비스 토큰**을 입력한 뒤 **알림 설정 저장**을 누릅니다. **현재 리뷰 알림 보내기**로 수동 전송할 수 있습니다. 자동 전송도 원하면 **새 리뷰나 점수가 바뀌면 추가 알림 보내기**를 켜고 저장하세요.

Telegram만 선택하면 SMTP 설정과 받는 이메일 주소는 필요하지 않습니다.

### 이메일 사용하기

공통 준비를 마친 터미널에서 메일 서버 정보를 설정합니다. 아래는 Gmail SMTP 설정 예시입니다. `SMTP_PASSWORD`에는 메일 제공업체에서 발급한 앱 비밀번호 등 SMTP 인증 정보를 사용하세요.

```sh
export SMTP_HOST='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USERNAME='you@gmail.com'
export SMTP_PASSWORD='메일-제공업체의-앱-비밀번호'
export EMAIL_FROM='you@gmail.com'
python monitor.py
```

`SMTP_PORT`의 기본값은 `587`이며 STARTTLS를 사용합니다. 팝업에서 **이메일**을 선택하고 **받는 이메일 주소**, **로컬 알림 서비스 토큰**을 입력한 뒤 **알림 설정 저장**을 누르세요. 수동 전송과 자동 전송 방법은 Telegram과 같습니다. 이메일만 선택하면 Telegram 설정은 필요하지 않습니다.

### 이메일과 Telegram 둘 다 사용하기

같은 터미널에 `EMAIL_BRIDGE_TOKEN`, SMTP 설정, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 모두 설정하고 `python monitor.py`를 실행합니다. 팝업에서는 **이메일 + Telegram**을 선택하고 받는 이메일 주소와 로컬 서비스 토큰을 저장하세요.

한쪽 전송만 실패하면 자동 확인 때 실패한 쪽만 재시도합니다. 수동 전송은 매번 다시 보내므로, 일부 성공 안내가 나온 뒤 수동으로 재전송하면 성공했던 쪽에도 중복 발송될 수 있습니다.

### 알림 내용과 실행 상태

이메일·Telegram에는 전체 논문의 **score / confidence를 먼저 모아서** 보내고, 뒤에 논문과 리뷰별 OpenReview 원문 링크를 붙입니다. 긴 리뷰 본문은 전송하지 않으며 weakness 전체도 원문에서 확인할 수 있습니다. 비공개 리뷰는 링크를 열 때 권한이 있는 OpenReview 계정으로 로그인해야 합니다. 리뷰 번호는 note ID 순서로 정하므로 점수가 바뀌어도 순서가 바뀌지 않습니다.

확장 프로그램이 OpenReview를 조회하고 Python이 전달만 하는 모드에서는 Chrome과 Python이 모두 실행 중이어야 합니다. 로컬 서비스는 같은 컴퓨터의 `127.0.0.1:8765`에서만 연결을 받습니다. Chrome에서 로컬 네트워크 접근 허용을 요청하면 허용하세요.

다음 메시지는 오류가 아닙니다.

```text
Background OpenReview polling is not configured; the extension notification bridge is active.
```

Python 자체 감시를 설정하지 않았고, 확장 프로그램이 보내는 요청을 기다리는 정상 상태입니다. 이 방식에서는 `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD`, `OPENREVIEW_PAPERS_JSON`을 설정할 필요가 없습니다.

코드를 업데이트한 뒤에는 `chrome://extensions`에서 확장 프로그램을 새로고침하고, 이메일·Telegram을 사용한다면 실행 중인 `monitor.py`도 재시작하세요.

### Chrome 없이 Python이 직접 감시하게 하기 — 선택 사항

이 모드의 흐름은 `Python → OpenReview 조회 → 이메일 / Telegram`입니다. Chrome이 리뷰를 가져오는 위의 방식과 다르게 OpenReview 로그인 정보를 Python에도 설정해야 합니다.

| 환경 변수 | 용도 |
| --- | --- |
| `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD` | Python의 OpenReview 로그인 |
| `OPENREVIEW_PAPERS_JSON` | 논문별 `venue`, `title`, `forum`을 담은 JSON 배열. `papers.example.json` 참고. 여러 venue를 한 배열에 넣을 수 있음 |
| `OPENREVIEW_TOTP_SECRET` | 무인 로그인에 인증 앱 MFA가 필요한 경우에만 설정 |
| `NOTIFICATION_CHANNEL` | `email`(기본값), `telegram`, `both`. `browser`는 Python의 외부 전송을 끔 |
| `EMAIL_TO` | 이메일 수신 주소. 확장 프로그램에서 저장한 주소가 있으면 저장된 주소가 우선 |
| `POLL_INTERVAL_SECONDS` | 확인 간격. 기본 900초, 최소 60초 |

사용할 SMTP·Telegram 환경 변수도 설정해야 합니다. Python 자체 감시만 실행하면 `EMAIL_BRIDGE_TOKEN`은 필요하지 않습니다. 이 토큰은 확장 프로그램의 설정 저장·전송 기능도 연결할 때 필요합니다.

예를 들어 `export NOTIFICATION_CHANNEL=telegram`은 Python 자체 감시의 Telegram 전송을 선택합니다. 다만 확장 프로그램에서 알림 방식을 저장했다면 `.state/email-settings.json`에 저장된 설정이 `NOTIFICATION_CHANNEL`보다 우선합니다. 실행하면 즉시 확인하고 이후 설정한 간격으로 반복합니다.

확장 프로그램의 자동 알림 체크박스는 Chrome의 자동 전송만 제어합니다. Python은 `OPENREVIEW_PAPERS_JSON`이 설정되어 있으면 자체 감시를 실행하므로, 중복 발송을 피하려면 **확장 자동 전송 또는 Python 자체 감시 중 하나**를 사용하세요. 확장 전달 전용으로 실행하려면 모니터를 중지한 다음 같은 터미널에서 `unset OPENREVIEW_PAPERS_JSON` 후 재시작합니다.

브라우저 알림만 선택하면 실행 중인 로컬 서비스에 설정을 동기화하려고 시도하지만, 연결되지 않아도 브라우저 설정 저장은 완료됩니다. 이때 Python에는 이전 설정이 남을 수 있으므로 브라우저 알림만 사용할 때는 Python 자체 감시를 중지하세요. Python만으로는 Chrome 알림을 만들지 않습니다.

### 문제 해결과 설정 보관

| 증상 | 확인할 내용 |
| --- | --- |
| `Missing environment variable: ...` | 모니터를 실행한 터미널에 해당 변수를 설정했는지 확인하고 재시작 |
| 로컬 알림 서비스 연결 실패 | `monitor.py` 실행 여부, 같은 컴퓨터인지, Chrome 로컬 네트워크 권한 확인 |
| `Bridge token is invalid` | 팝업의 로컬 서비스 토큰과 모니터의 `EMAIL_BRIDGE_TOKEN`이 같은지 확인 |
| Telegram API 오류 | 봇 토큰, Chat ID, 봇과의 대화 시작 여부, 대상 채팅에서의 발송 권한 확인 |
| 브라우저 알림이 안 보임 | Chrome 실행 여부와 운영체제의 Chrome 알림 허용 여부 확인 |
| 알림이 두 번 옴 | Python 자체 감시와 확장 자동 전송을 동시에 켰는지 확인 |

발송 내역의 fingerprint는 `.state/last-seen.json`에 채널별로 저장합니다. 원문 변경도 감지하며, 같은 내용은 자동으로 다시 보내지 않습니다. Telegram 메시지가 길면 [sendMessage 길이 제한](https://core.telegram.org/bots/api#sendmessage)에 맞춰 나눠 보냅니다. 여러 조각 중간에 전송이 실패하면 재시도 시 앞선 조각이 중복될 수 있습니다.

인증 정보나 `.state/` 파일을 저장소에 커밋하지 마세요. 확장 프로그램에는 로컬 연결 토큰, 받는 주소, 알림 방식과 자동 전송 여부를 저장하며, SMTP 인증 정보와 Telegram 봇 토큰은 Python 환경 변수에서만 읽습니다. 메일 제공업체나 Telegram에는 제목·venue·score·confidence·원문 링크가 전달됩니다. 이 알림 기능은 AI 서비스를 호출하지 않습니다.

## Local extension and ChatGPT web handoff

The extension can send a changed official review to a new ChatGPT web chat without an OpenAI API key:

1. Sign in to ChatGPT in Chrome.
2. In the extension popup, enter your analysis instructions and save them.
3. Check the box that allows automatic review transfer and save it.
4. When a score or review changes, the extension opens a background ChatGPT tab, inserts the instructions and review in one user message, and submits it.

The instructions are prepended to the user message; the regular ChatGPT website does not let this extension set a true system-role message. The extension does not read ChatGPT's response back. This optional web handoff is separate from the notification monitor described above, which sends scores, confidence and review links by email or Telegram.

The extension stores the prompt, consent toggle, paper list, score/confidence and last-seen review signatures locally in Chrome. Those signatures contain the extracted review text used to detect changes. Review text is sent to OpenAI when the automatic-transfer box is enabled. Uncheck it to stop automatic transfer. The “send now” button also requires the box to be checked.

Load this directory as an unpacked extension from `chrome://extensions`; scheduled checks run while Chrome is running. ChatGPT must be signed in. If the ChatGPT page changes its composer UI, automatic insertion may stop working and require an extension update.
