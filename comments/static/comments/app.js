// ---------------------------------------------------------------------------
// 사이드바 접기/펼치기 (데스크톱: 접힘 상태 저장, 모바일: 서랍처럼 열고 닫기)
// ---------------------------------------------------------------------------
const root = document.documentElement;
const mobileQuery = window.matchMedia("(max-width: 960px)");

document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    if (mobileQuery.matches) {
      root.classList.toggle("sidebar-open");
      return;
    }
    const collapsed = root.classList.toggle("sidebar-collapsed");
    try {
      localStorage.setItem("chaeum:sidebar", collapsed ? "collapsed" : "expanded");
    } catch (e) { /* 저장소를 쓸 수 없으면 이번 화면에만 반영 */ }
  });
});
document.querySelector("[data-sidebar-close]")?.addEventListener("click", () => root.classList.remove("sidebar-open"));

// ---------------------------------------------------------------------------
// F601 회사명 입력 / F603 크롤링 진행 상황 스트리밍 / F611 예외 안내
// ---------------------------------------------------------------------------
const searchForm = document.getElementById("search-form");
if (searchForm) {
  const searchInput = document.getElementById("company_name");
  const searchButton = document.getElementById("search-btn");
  const progressBox = document.getElementById("progress");
  const progressCurrent = document.getElementById("progress-current");
  const progressPercent = document.getElementById("progress-percent");
  const progressBar = document.getElementById("progress-bar");
  const progressLog = document.getElementById("progress-log");
  const searchError = document.getElementById("search-error");
  const flowSteps = [...document.querySelectorAll("#flow-steps .step")];

  let percent = 0;

  const syncReady = () => searchForm.classList.toggle("is-ready", searchInput.value.trim() !== "");
  searchInput.addEventListener("input", syncReady);

  // 예시 회사 칩: 입력창만 채우고, 검색은 사용자가 직접 실행한다.
  searchForm.querySelectorAll("[data-fill]").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (searchButton.disabled) return;
      searchInput.value = chip.dataset.fill;
      syncReady();
      searchInput.focus();
    });
  });

  // 사이드바의 '새 분석'(#search)으로 들어오면 입력창에 바로 커서를 둔다.
  const focusIfRequested = () => {
    if (location.hash === "#search") searchInput.focus({ preventScroll: true });
  };
  window.addEventListener("hashchange", focusIfRequested);
  focusIfRequested();

  const setSearching = (searching) => {
    searchInput.readOnly = searching;
    searchButton.disabled = searching;
    searchButton.classList.toggle("is-loading", searching);
    searchButton.setAttribute("aria-label", searching ? "수집 중..." : "검색");
  };

  const setPercent = (value) => {
    percent = Math.max(percent, Math.min(100, Math.round(value)));
    progressBar.style.width = `${percent}%`;
    progressPercent.textContent = `${percent}%`;
  };

  // 홈 화면의 '데이터가 채워지는 과정' 단계를 진행 상황에 맞춰 표시한다.
  const markStep = (stage, state = "active") => {
    const current = flowSteps.findIndex((li) => li.dataset.step === stage);
    if (current < 0) return;
    flowSteps.forEach((li, i) => {
      li.classList.toggle("is-done", i < current);
      li.classList.toggle("is-active", i === current && state === "active");
      li.classList.toggle("is-error", i === current && state === "error");
    });
  };
  const resetSteps = () => flowSteps.forEach((li) => li.classList.remove("is-done", "is-active", "is-error"));
  let currentStage = "collect";

  const addProgress = (message) => {
    progressCurrent.textContent = message;
    // '댓글 수집 중... (3/20)' 처럼 개수만 바뀌는 메시지는 한 줄로 갱신한다.
    const key = message.replace(/\s*\(\d+\/\d+\)\s*$/, "");
    const last = progressLog.lastElementChild;
    if (last && last.dataset.key === key) {
      last.querySelector(".log-text").textContent = message;
      return;
    }
    last?.classList.add("is-done");
    const item = document.createElement("li");
    item.className = "log-item";
    item.dataset.key = key;
    const icon = document.createElement("span");
    icon.className = "log-icon";
    const text = document.createElement("span");
    text.className = "log-text";
    text.textContent = message;
    item.append(icon, text);
    progressLog.appendChild(item);
    progressLog.scrollTop = progressLog.scrollHeight;
  };

  const updatePercent = (event) => {
    if (event.stage === "collect") {
      const count = /\((\d+)\/(\d+)\)/.exec(event.message);
      setPercent(count ? 20 + 50 * (Number(count[1]) / Number(count[2])) : Math.min(percent + 5, 20));
    } else if (event.stage === "preprocess") {
      setPercent(80);
    } else if (event.stage === "review") {
      setPercent(90);
    }
  };

  const showSearchError = (message) => {
    progressBox.hidden = true;
    markStep(currentStage, "error");
    searchError.textContent = message;
    searchError.hidden = false;
  };

  const handleEvent = (event) => {
    if (event.type === "progress") {
      if (event.stage) {
        currentStage = event.stage;
        markStep(event.stage);
      }
      addProgress(event.message);
      updatePercent(event);
    } else if (event.type === "error") {
      showSearchError(event.message);
    } else if (event.type === "done") {
      progressLog.lastElementChild?.classList.add("is-done");
      setPercent(100);
      // 100% 가 채워지는 모습을 잠깐 보여준 뒤 검수 화면으로 이동한다.
      setTimeout(() => { window.location.href = event.redirect; }, 450);
    }
  };

  searchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const companyName = searchInput.value.trim();
    if (!companyName || searchButton.disabled) {
      return; // 입력값이 없으면 아무 동작도 수행하지 않는다.
    }

    setSearching(true);
    searchError.hidden = true;
    progressLog.replaceChildren();
    progressBox.hidden = false;
    progressCurrent.textContent = "댓글 수집 중...";
    percent = 0;
    setPercent(2);
    resetSteps();
    currentStage = "collect";
    markStep(currentStage);

    let finished = false;
    try {
      const url = `${searchForm.action}?${new URLSearchParams({ company_name: companyName })}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      // 서버가 한 줄에 하나씩 보내는 JSON 이벤트(NDJSON)를 도착하는 대로 읽는다.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.type === "done" || event.type === "error") finished = true;
          handleEvent(event);
        }
      }
      if (!finished) showSearchError("서버 응답이 중간에 끊겼습니다. 서버 터미널의 오류 메시지를 확인해 주세요.");
    } catch (err) {
      showSearchError(`서버와 통신 중 오류가 발생했습니다. (${err.message})`);
    } finally {
      setSearching(false);
    }
  });
}

// ---------------------------------------------------------------------------
// 검수 화면: 제외할 댓글 선택 도우미
// ---------------------------------------------------------------------------
const reviewForm = document.getElementById("review-form");
if (reviewForm) {
  const checkboxes = reviewForm.querySelectorAll("input[name='exclude']");
  const excludeCount = document.getElementById("exclude-count");

  const updateCount = () => {
    const excluded = [...checkboxes].filter((cb) => cb.checked).length;
    excludeCount.innerHTML = `제외 <b>${excluded}</b>개 · 사용 <b>${checkboxes.length - excluded}</b>개`;
    checkboxes.forEach((cb) => cb.closest(".todo").classList.toggle("is-excluded", cb.checked));
  };

  checkboxes.forEach((cb) => cb.addEventListener("change", updateCount));
  reviewForm.querySelectorAll("[data-select]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.select;
      checkboxes.forEach((cb) => {
        cb.checked = mode === "flagged" && cb.dataset.flagged === "1";
      });
      updateCount();
    });
  });
  updateCount();
}

// ---------------------------------------------------------------------------
// 오래 걸리는 POST 요청(증강) 동안 로딩 화면 표시
// ---------------------------------------------------------------------------
document.querySelectorAll("button[data-loading]").forEach((button) => {
  button.form.addEventListener("submit", () => {
    document.getElementById("loading-text").textContent = button.dataset.loading;
    document.getElementById("loading-overlay").hidden = false;
    button.disabled = true;
  });
});

// ---------------------------------------------------------------------------
// 결과 화면: 보드 / 비교 보기 전환
// ---------------------------------------------------------------------------
const viewTabs = document.querySelectorAll("[data-view]");
viewTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    viewTabs.forEach((other) => {
      const active = other === tab;
      other.classList.toggle("is-active", active);
      other.setAttribute("aria-selected", String(active));
      document.querySelector(`[data-view-panel="${other.dataset.view}"]`).hidden = !active;
    });
  });
});

// ---------------------------------------------------------------------------
// F610 댓글 요약 버튼
// ---------------------------------------------------------------------------
const summaryButton = document.getElementById("summary-btn");
if (summaryButton) {
  const summaryBox = document.getElementById("summary-box");
  const summaryError = document.getElementById("summary-error");
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;
  let summaryText = summaryBox.textContent.trim();

  // '- ' 로 시작하는 줄은 목록으로, '한줄 요약:' 줄은 강조해서 보여준다.
  const renderSummary = (text) => {
    summaryBox.classList.remove("is-loading");
    summaryBox.replaceChildren();
    let list = null;
    for (const line of text.split("\n").map((l) => l.trim()).filter(Boolean)) {
      const bullet = /^[-•*]\s+/.exec(line);
      if (bullet) {
        if (!list) list = summaryBox.appendChild(document.createElement("ul"));
        list.appendChild(document.createElement("li")).textContent = line.slice(bullet[0].length);
        continue;
      }
      list = null;
      const p = summaryBox.appendChild(document.createElement("p"));
      if (/^(\d+[.)]\s*)?한줄\s*요약/.test(line)) p.className = "summary-oneline";
      p.textContent = line;
    }
    summaryBox.hidden = !text;
  };

  const showSkeleton = () => {
    summaryBox.classList.add("is-loading");
    summaryBox.replaceChildren(...["92%", "76%", "84%", "58%"].map((width) => {
      const line = document.createElement("span");
      line.className = "skeleton";
      line.style.width = width;
      return line;
    }));
    summaryBox.hidden = false;
  };

  if (summaryText) renderSummary(summaryText);

  summaryButton.addEventListener("click", async () => {
    summaryButton.disabled = true;
    summaryButton.textContent = "요약 생성 중...";
    summaryError.hidden = true;
    showSkeleton();
    try {
      const response = await fetch(summaryButton.dataset.url, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      summaryText = data.summary;
    } catch (err) {
      summaryError.textContent = `요약 생성에 실패했습니다. ${err.message}`;
      summaryError.hidden = false;
    } finally {
      renderSummary(summaryText);
      summaryButton.textContent = summaryText ? "요약 다시 생성" : "댓글 요약 보기";
      summaryButton.disabled = false;
    }
  });
}
