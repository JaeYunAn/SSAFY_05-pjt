"""
F603 회사 검색 및 선택 / F604 커뮤니티 댓글 데이터 수집

토스증권(https://www.tossinvest.com)에서 Selenium 으로
  1) 우측 상단 검색창을 열어 회사명을 입력하고
  2) 검색 결과 최상단(자동 포커싱된) 종목으로 이동한 뒤
  3) '커뮤니티' 탭에 게시된 댓글 텍스트를 수집한다.

Django 에 의존하지 않는 순수 함수로 작성하여 단독으로도 재사용할 수 있다.
    >>> result = crawl_comments("삼성")
    >>> result.stock_name, len(result.comments)
    ('삼성전자', 20)
"""
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

TOSS_HOME_URL = "https://www.tossinvest.com/"

# 토스증권 DOM 셀렉터
# 클래스명(tw1n-xxxx 등)은 배포 때마다 바뀌므로 가능한 data-* 속성을 기준으로 찾는다.
SEARCH_BUTTON_XPATH = "//button[contains(., '검색하세요')]"
SEARCH_INPUT = "input[type='search']"
SEARCH_RESULT_ROW = "[data-section-name='종목'] a[data-parent-name='ProductListRow']"
SEARCH_ALL_SECTION = "[data-section-name='전체']"
NO_RESULT_TEXT = "검색결과가 없어요"

# 검색창 상태(결과 목록 / 결과 없음 / 아직 로딩 중)를 한 번에 확인하는 스크립트
SEARCH_STATE_JS = """
const rows = document.querySelectorAll(arguments[0]);
if (rows.length) {
    return {name: rows[0].getAttribute('data-content-value'), href: rows[0].getAttribute('href')};
}
const all = document.querySelector(arguments[1]);
if (all && all.innerText.includes(arguments[2])) return {empty: true};
return null;
"""

ProgressCallback = Callable[[str], None]


class CrawlError(Exception):
    """크롤링 중 사용자에게 안내해야 하는 오류"""


@dataclass
class CrawlResult:
    query: str                     # 사용자가 입력한 검색어
    stock_name: str                # 실제 매칭된 종목의 공식 명칭
    stock_code: str                # 종목 코드 (예: 005930)
    url: str                       # 수집한 커뮤니티 페이지 주소
    comments: list = field(default_factory=list)


def create_driver(headless: bool = True) -> webdriver.Chrome:
    """webdriver-manager 로 ChromeDriver 를 자동 설치/관리하여 크롬을 실행한다."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")  # 창이 좁으면 검색창이 아이콘으로 바뀌므로 넉넉하게
    options.add_argument("--lang=ko-KR")
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    # 헤드리스 모드의 User-Agent 에는 'HeadlessChrome' 이 포함되므로 일반 크롬처럼 보이도록 변경
    user_agent = driver.execute_script("return navigator.userAgent")
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {"userAgent": user_agent.replace("HeadlessChrome", "Chrome")},
    )
    return driver


def _to_stock_code(href: str) -> str:
    """'/stocks/A005930/order' -> '005930', '/stocks/US19801212001/order' -> 'US19801212001'"""
    match = re.search(r"/stocks/([^/?#]+)", href or "")
    if not match:
        return ""
    code = match.group(1)
    domestic = re.fullmatch(r"A(\d{6})", code)
    return domestic.group(1) if domestic else code


def search_company(driver, company_name: str, timeout: int = 15) -> dict:
    """
    토스증권 검색창에 회사명을 입력하고, 검색 결과 최상단 종목 정보를 반환한다.
    결과가 없으면 CompanyNotFoundError 를 발생시킨다.
    """
    driver.get(TOSS_HOME_URL)
    wait = WebDriverWait(driver, timeout)

    # 1) 우측 상단 검색창 클릭 -> 검색 모달 열기
    search_button = wait.until(EC.presence_of_element_located((By.XPATH, SEARCH_BUTTON_XPATH)))
    driver.execute_script("arguments[0].click();", search_button)

    # 2) 모달의 입력창에 회사명 입력
    search_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, SEARCH_INPUT)))
    search_input.send_keys(company_name)

    # 3) 검색 결과가 갱신될 때까지 대기
    #    글자를 입력하는 도중의 중간 결과를 잡지 않도록, 같은 결과가 연속 두 번 나올 때를 확정으로 본다.
    deadline = time.time() + timeout
    previous = None
    while time.time() < deadline:
        state = driver.execute_script(SEARCH_STATE_JS, SEARCH_RESULT_ROW, SEARCH_ALL_SECTION, NO_RESULT_TEXT)
        if state is not None and state == previous:
            break
        previous = state
        time.sleep(0.6)
    else:
        raise CrawlError("토스증권 검색 결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")

    if state.get("empty"):
        raise CrawlError(f"'{company_name}'에 대한 검색 결과가 없습니다. 회사명을 다시 확인해 주세요.")

    # 4) 최상단 종목은 자동으로 포커싱되어 있으므로 Enter 로 선택한다.
    search_input.send_keys(Keys.ENTER)
    try:
        WebDriverWait(driver, 10).until(EC.url_contains("/stocks/"))
    except TimeoutException:
        driver.get(urljoin(TOSS_HOME_URL, state["href"]))

    return {
        "stock_name": state["name"],
        "stock_code": _to_stock_code(state["href"]),
        "href": state["href"],
    }


def crawl_comments(company_name: str, limit: int = 20, headless: bool = True,
                   on_progress: Optional[ProgressCallback] = None) -> CrawlResult:
    """회사 검색 -> 최상단 종목 선택 과정을 수행한다."""
    def report(message):
        if on_progress:
            on_progress(message)

    report("크롬 브라우저를 실행하는 중...")
    try:
        driver = create_driver(headless=headless)
    except WebDriverException as e:
        raise CrawlError(f"크롬 브라우저를 실행할 수 없습니다. Chrome 설치 여부를 확인해 주세요. ({e.msg})") from e

    try:
        report(f"토스증권에서 '{company_name}' 검색 중...")
        stock = search_company(driver, company_name)
        report(f"검색 결과 최상단 종목 '{stock['stock_name']}' 선택")

        return CrawlResult(
            query=company_name,
            stock_name=stock["stock_name"],
            stock_code=stock["stock_code"],
            url=driver.current_url,
        )
    except TimeoutException as e:
        raise CrawlError("토스증권 페이지 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.") from e
    finally:
        driver.quit()
