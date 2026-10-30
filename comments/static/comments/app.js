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
// F601 회사명 입력
// ---------------------------------------------------------------------------
const searchForm = document.getElementById("search-form");
if (searchForm) {
  const searchInput = document.getElementById("company_name");
  const searchButton = document.getElementById("search-btn");

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

  searchForm.addEventListener("submit", (e) => {
    if (!searchInput.value.trim()) {
      e.preventDefault(); // 입력값이 없으면 아무 동작도 수행하지 않는다.
    }
  });
}
