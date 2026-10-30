"""
GMS(SSAFY 생성형 AI API) 클라이언트

  - F605 부적절한 댓글 판별   : find_inappropriate()
  - F606 텍스트 데이터 증강   : augment_comments()

GMS 는 OpenAI 호환 Chat Completions API 를 제공하므로 requests 로 직접 호출한다.
API 키는 .env 의 GMS_KEY 로 설정한다.
"""
import json
import re

import requests
from django.conf import settings


class LLMError(Exception):
    """GMS API 호출 또는 응답 해석에 실패한 경우"""


def chat(prompt: str, system: str = "", timeout: int = 90) -> str:
    """GMS Chat Completions API 를 호출하여 응답 텍스트를 반환한다."""
    if not settings.GMS_KEY:
        raise LLMError("GMS_KEY 가 설정되지 않았습니다. 프로젝트 루트의 .env 파일을 확인해 주세요.")

    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})

    try:
        response = requests.post(
            f"{settings.GMS_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GMS_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": settings.GMS_MODEL, "messages": messages},
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise LLMError(f"GMS API 요청에 실패했습니다: {e}") from e

    if response.status_code != 200:
        raise LLMError(f"GMS API 오류 ({response.status_code}): {response.text[:200]}")

    try:
        return response.json()["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        raise LLMError("GMS API 응답 형식을 해석할 수 없습니다.") from e


def parse_json(text: str):
    """LLM 응답에서 JSON 부분만 꺼내 파싱한다. (```json 코드 블록, 앞뒤 설명 문장 대응)"""
    match = re.search(r"\[.*\]|\{.*\}", text, re.S)
    if not match:
        raise LLMError(f"LLM 응답에서 JSON 을 찾을 수 없습니다: {text[:100]}")
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM 응답 JSON 파싱 실패: {text[:100]}") from e


def _numbered(comments) -> str:
    return "\n".join(f"{i}. {text}" for i, text in enumerate(comments))


def find_inappropriate(comments) -> list:
    """부적절한 댓글(욕설, 혐오, 비방, 선정성, 과도한 비난 등)의 인덱스 목록을 반환한다."""
    if not comments:
        return []
    prompt = (
        "다음 댓글 목록에서 부적절한 댓글(욕설, 혐오, 비방, 선정성, 과도한 비난 등)의 "
        "번호(0 부터 시작)만 JSON 배열로 알려줘. 다른 설명 없이 JSON 배열만 출력하고, "
        "부적절한 댓글이 없으면 [] 를 출력해.\n\n"
        f"{_numbered(comments)}"
    )
    data = parse_json(chat(prompt))
    if not isinstance(data, list):
        raise LLMError("부적절 댓글 판별 결과가 JSON 배열이 아닙니다.")

    indices = set()
    for value in data:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(comments):
            indices.add(index)
    return sorted(indices)


AUGMENT_SYSTEM = (
    "너는 주식 커뮤니티 댓글 데이터를 증강하는 데이터 엔지니어야. "
    "원문의 의미, 감정(긍정/부정), 핵심 정보(숫자, 종목명, 가격 등)는 그대로 유지하고, "
    "표현만 자연스럽게 바꾸거나 조금 더 풍부하게 풀어 쓴 한국어 문장을 만든다. "
    "새로운 사실을 지어내지 않는다."
)


def augment_comments(comments) -> list:
    """전처리된 댓글마다 의미를 유지한 증강 문장을 1개씩 생성한다. (입력과 같은 순서·개수)"""
    if not comments:
        return []
    prompt = (
        f"아래 댓글 {len(comments)}개를 각각 의미를 유지한 채 다른 표현으로 바꿔 써줘.\n"
        f"입력과 같은 순서로, 문자열 {len(comments)}개로 이루어진 JSON 배열만 출력해.\n\n"
        f"{_numbered(comments)}"
    )
    data = parse_json(chat(prompt, system=AUGMENT_SYSTEM))
    if isinstance(data, list) and len(data) == len(comments):
        return [str(item).strip() for item in data]

    # 개수가 어긋나면 순서가 섞일 수 있으므로 댓글을 하나씩 다시 증강한다.
    return [augment_one(text) for text in comments]


def augment_one(comment: str) -> str:
    prompt = f"다음 댓글을 의미를 유지한 채 다른 표현으로 바꾼 문장 하나만 출력해.\n\n댓글: {comment}"
    return chat(prompt, system=AUGMENT_SYSTEM).strip().strip('"')
