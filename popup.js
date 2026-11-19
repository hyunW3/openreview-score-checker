const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const tableBody = $("papers");

function showStatus(message, error = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", error);
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text || "—";
  return td;
}

function render(state = {}) {
  tableBody.replaceChildren();
  const papers = state.papers || [];
  const venues = [...new Set(papers.map(paper => paper.venue))];
  $("venue").textContent = venues.length ? venues.join(" · ") : "Authors 페이지에서 venue를 추가하세요.";
  $("checked").textContent = state.lastChecked
    ? `마지막 확인: ${new Date(state.lastChecked).toLocaleString()}`
    : "";
  for (const paper of papers) {
    const row = document.createElement("tr");
    row.append(cell(paper.venue), cell(paper.title), cell(paper.scores), cell(paper.confidences));
    const actions = document.createElement("td");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-paper";
    remove.textContent = "삭제";
    remove.setAttribute("aria-label", `${paper.title} 감시 목록에서 삭제`);
    remove.addEventListener("click", () => removePaper(paper, remove));
    actions.append(remove);
    row.append(actions);
    tableBody.append(row);
  }
  if (state.error) showStatus(papers.length ? `감시 중 · ${papers.length}편 · ${state.error}` : state.error, true);
  else if (papers.length) showStatus(`감시 중 · ${venues.length}개 venue · ${papers.length}편 · 15분마다 자동 확인`);
  else showStatus("Authors 페이지에서 한 번 감시를 시작하세요.");
}

async function removePaper(paper, button) {
  button.disabled = true;
  try {
    const result = await chrome.runtime.sendMessage({ type: "REMOVE_PAPER", forum: paper.forum });
    if (!result?.ok) throw new Error(result?.error || "논문을 삭제하지 못했습니다.");
    render(result.state);
    showStatus(`감시 목록에서 삭제했습니다: ${paper.title}`);
  } catch (error) {
    button.disabled = false;
    showStatus(error.message, true);
  }
}

async function getState() {
  const [result, emailSettings] = await Promise.all([
    chrome.runtime.sendMessage({ type: "GET_STATE" }),
    chrome.runtime.sendMessage({ type: "GET_EMAIL_SETTINGS" })
  ]);
  $("ai-prompt").value = result?.aiPrompt || "";
  $("ai-consent").checked = Boolean(result?.aiConsent);
  $("email-to").value = emailSettings?.emailTo || result?.emailTo || "";
  $("email-bridge-token").value = emailSettings?.emailBridgeToken || "";
  $("email-auto").checked = Boolean(emailSettings?.emailAuto);
  $("notification-channel").value = emailSettings?.notificationChannel || (emailSettings?.emailTo ? "email" : "browser");
  updateNotificationFields();
  render(result || {});
}

async function saveAiSettings() {
  const result = await chrome.runtime.sendMessage({
    type: "SAVE_AI_SETTINGS",
    aiPrompt: $("ai-prompt").value,
    aiConsent: $("ai-consent").checked
  });
  render(result || {});
  showStatus("분석 지침과 자동 전송 설정을 저장했습니다.");
}

async function startMonitoring() {
  try {
    showStatus("현재 Authors 페이지의 논문을 등록하는 중…");
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !tab.url?.startsWith("https://openreview.net/")) {
      throw new Error("OpenReview Authors 페이지를 먼저 여세요.");
    }
    const [injected] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const params = new URLSearchParams(location.search);
        const groupId = params.get("id") || "";
        if (!/\/Authors\/?$/.test(groupId)) return { error: "Authors 페이지에서 실행해 주세요." };
        const venue = groupId.replace(/\/Authors\/?$/, "");
        const papers = [];
        const seen = new Set();
        const links = document.querySelectorAll('table tbody tr a[href*="/forum?"], .note h4 a[href*="/forum?"], .note .note_content_title a[href*="/forum?"]');
        for (const link of links) {
          const forum = new URL(link.href, location.href).searchParams.get("id");
          const title = link.textContent.trim();
          if (forum && title && !seen.has(forum)) {
            seen.add(forum);
            papers.push({ forum, title, venue });
          }
        }
        return { venue, papers };
      }
    });
    const page = injected?.result;
    if (page?.error) throw new Error(page.error);
    if (!page?.papers?.length) throw new Error("논문 목록을 찾지 못했습니다. Authors 페이지의 논문 목록이 로딩됐는지 확인하세요.");
    const result = await chrome.runtime.sendMessage({ type: "SET_PAPERS", papers: page.papers });
    if (!result?.ok) throw new Error(result?.error || "감시를 시작하지 못했습니다.");
    render(result.state);
    if (result.error) showStatus(`감시를 시작했습니다. 추가 알림 오류: ${result.error}`, true);
    else showStatus(`${page.papers.length}편을 추가했습니다. 기존 venue의 감시도 계속됩니다.`);
  } catch (error) {
    showStatus(error.message, true);
  }
}

async function checkNow() {
  showStatus("OpenReview API를 확인하는 중…");
  const result = await chrome.runtime.sendMessage({ type: "POLL_NOW" });
  if (result?.state) render(result.state);
  else showStatus(result?.error || "확인에 실패했습니다.", true);
}

async function analyzeNow() {
  showStatus("저장된 리뷰를 ChatGPT에 보내는 중…");
  const result = await chrome.runtime.sendMessage({ type: "SEND_TO_CHATGPT_NOW" });
  if (result?.state) render(result.state);
  if (!result?.ok) showStatus(result?.error || "전송하지 못했습니다.", true);
  else showStatus(result.message || "ChatGPT 탭에 리뷰를 전송했습니다.");
}

function updateNotificationFields() {
  const channel = $("notification-channel").value;
  const needsEmail = ["email", "both"].includes(channel);
  $("bridge-settings").hidden = channel === "browser";
  $("email-recipient-settings").hidden = !needsEmail;
  $("email-to").required = needsEmail;
}

async function saveEmailSettings() {
  showStatus("알림 설정을 저장하는 중…");
  const emailTo = $("email-to").value.trim();
  const emailBridgeToken = $("email-bridge-token").value.trim();
  const notificationChannel = $("notification-channel").value;
  if (["email", "both"].includes(notificationChannel) && !emailTo) {
    showStatus("받는 이메일 주소를 입력하세요.", true);
    return false;
  }
  if (notificationChannel !== "browser" && emailBridgeToken.length < 32) {
    showStatus("서비스 토큰은 32자 이상이어야 합니다.", true);
    return false;
  }
  try {
    const emailAuto = notificationChannel !== "browser" && $("email-auto").checked;
    const syncBridgeSettings = async () => {
      const response = await fetch("http://127.0.0.1:8765/settings", {
        method: "POST",
        headers: { "Authorization": `Bearer ${emailBridgeToken}`, "Content-Type": "application/json" },
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
        body: JSON.stringify({ emailTo, notificationChannel, emailAuto })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || `알림 서비스 오류 (${response.status})`);
    };
    if (notificationChannel !== "browser") {
      await syncBridgeSettings();
    } else if (emailBridgeToken.length >= 32) {
      // Sync a running monitor when possible; browser settings never wait on it.
      void syncBridgeSettings().catch(() => {});
    }
    const stored = await chrome.runtime.sendMessage({
      type: "STORE_EMAIL_SETTINGS",
      emailTo,
      notificationChannel,
      emailBridgeToken,
      emailAuto
    });
    if (!stored?.ok) throw new Error(stored?.error || "확장 프로그램에 설정을 저장하지 못했습니다.");
    showStatus("알림 설정을 저장했습니다.");
    return true;
  } catch (error) {
    const message = error.message === "Failed to fetch"
      ? "Python 모니터 실행과 Chrome의 로컬 네트워크 권한을 확인하세요."
      : error.message;
    showStatus(message || "알림 설정을 저장하지 못했습니다.", true);
    return false;
  }
}

async function sendEmailNow() {
  showStatus("현재 공식 리뷰 알림을 보내는 중…");
  if (!(await saveEmailSettings())) return;
  const result = await chrome.runtime.sendMessage({ type: "SEND_EMAIL_NOW" });
  if (!result?.ok) showStatus(result?.error || "알림을 보내지 못했습니다.", true);
  else showStatus(result.message || "리뷰 알림을 보냈습니다.");
}

$("connect").addEventListener("click", startMonitoring);
$("refresh").addEventListener("click", checkNow);
$("save-prompt").addEventListener("click", saveAiSettings);
$("analyze-now").addEventListener("click", analyzeNow);
$("save-email").addEventListener("click", saveEmailSettings);
$("send-email-now").addEventListener("click", sendEmailNow);
$("notification-channel").addEventListener("change", updateNotificationFields);
getState();

chrome.storage.onChanged.addListener((_changes, area) => {
  if (area === "local") {
    chrome.runtime.sendMessage({ type: "GET_STATE" }).then((state) => render(state || {}));
  }
});
