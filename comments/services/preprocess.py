"""
F605 댓글 데이터 정제 (정규표현식 기반)

  - 결측치(빈 댓글) 제거
  - URL, 자음/모음만으로 된 표현(ㅋㅋㅋ, ㅎㅎ, ㅠㅠ 등), 특수문자·이모지 제거
  - 같은 글자의 과도한 반복 축약, 불필요한 공백 제거
  - 길이 기준 필터링 (5자 이상 ~ 76자 이하) + IQR 임계값 계산
  - 중복 댓글 제거
  - 욕설 키워드 감지 (LLM 판정과 함께 사용자가 직접 검수할 때 참고용)

부적절한 댓글의 LLM 판정은 services/llm.py 의 find_inappropriate() 에서 수행한다.
"""
import re
import statistics
from dataclasses import dataclass, field

MIN_LENGTH = 5
MAX_LENGTH = 76

URL_PATTERN = re.compile(r"(https?://|www\.)\S+")
JAMO_PATTERN = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]+")             # ㅋㅋㅋ, ㅎㅎ, ㅠㅠ, ㅜㅜ, ㄱㄱ 등
SPECIAL_CHAR_PATTERN = re.compile(r"[^0-9a-zA-Z가-힣\s]")  # 한글·영문·숫자·공백을 제외한 특수문자, 이모지
REPEAT_PATTERN = re.compile(r"([가-힣a-zA-Z])\1{2,}")       # 같은 글자 3번 이상 반복 (깔깔깔깔 -> 깔깔, 숫자는 제외)
WHITESPACE_PATTERN = re.compile(r"\s+")

# 사용자가 직접 검수할 때 참고할 수 있도록 표시해 주는 욕설/비속어 키워드
PROFANITY_PATTERN = re.compile(
    r"시발|씨발|씨바|씨팔|시팔|병신|븅신|빙신|좆|존나|졸라|지랄|개새|새끼|생키|"
    r"닥쳐|꺼져|미친놈|미친년|썅|염병|엠창|느금|애미|애비|등신|찐따|개잡주|개같"
)


@dataclass
class PreprocessResult:
    cleaned: list = field(default_factory=list)   # 정제가 끝난 댓글 목록
    removed: list = field(default_factory=list)   # [{"text": 원본, "reason": 제거 사유}]
    iqr: dict = field(default_factory=dict)       # 길이 분포의 IQR 임계값 정보


def clean_text(text) -> str:
    """댓글 한 개에서 불필요한 패턴·특수문자·공백을 제거한다."""
    if not text:
        return ""
    text = URL_PATTERN.sub(" ", str(text))
    text = JAMO_PATTERN.sub(" ", text)
    text = SPECIAL_CHAR_PATTERN.sub(" ", text)
    text = REPEAT_PATTERN.sub(r"\1\1", text)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def compute_iqr_threshold(lengths, min_length=MIN_LENGTH, max_length=MAX_LENGTH) -> dict:
    """
    댓글 길이 분포의 사분위수(Q1, Q3)와 IQR 기반 이상치 경계(Q1 - 1.5*IQR, Q3 + 1.5*IQR)를 계산한다.
    실제 필터링에는 명세의 고정 범위(min_length ~ max_length)를 사용하고, 계산값은 함께 저장한다.
    """
    info = {
        "count": len(lengths),
        "q1": None, "q3": None, "iqr": None,
        "lower_fence": None, "upper_fence": None,
        "min_length": min_length, "max_length": max_length,
    }
    if len(lengths) >= 2:
        q1, _, q3 = statistics.quantiles(lengths, n=4, method="inclusive")
        iqr = q3 - q1
        info.update(
            q1=round(q1, 2), q3=round(q3, 2), iqr=round(iqr, 2),
            lower_fence=round(q1 - 1.5 * iqr, 2), upper_fence=round(q3 + 1.5 * iqr, 2),
        )
    elif lengths:
        info.update(q1=lengths[0], q3=lengths[0], iqr=0, lower_fence=lengths[0], upper_fence=lengths[0])
    return info


def preprocess_comments(comments, min_length=MIN_LENGTH, max_length=MAX_LENGTH) -> PreprocessResult:
    """원본 댓글 목록을 정제하고, 제거된 댓글과 제거 사유를 함께 반환한다."""
    result = PreprocessResult()
    candidates = []  # (원본, 정제문)

    for original in comments:
        cleaned = clean_text(original)
        if not cleaned:
            reason = "결측치" if not (original or "").strip() else "특수문자/불필요 패턴만 존재"
            result.removed.append({"text": original or "", "reason": reason})
            continue
        candidates.append((original, cleaned))

    result.iqr = compute_iqr_threshold([len(c) for _, c in candidates], min_length, max_length)

    seen = set()
    for original, cleaned in candidates:
        if len(cleaned) < min_length:
            result.removed.append({"text": original, "reason": f"길이 {len(cleaned)}자 (< {min_length})"})
        elif len(cleaned) > max_length:
            result.removed.append({"text": original, "reason": f"길이 {len(cleaned)}자 (> {max_length})"})
        elif cleaned in seen:
            result.removed.append({"text": original, "reason": "중복"})
        else:
            seen.add(cleaned)
            result.cleaned.append(cleaned)

    return result


def find_profanity(comments) -> list:
    """욕설 키워드가 포함된 댓글의 인덱스 목록을 반환한다."""
    return [i for i, text in enumerate(comments) if PROFANITY_PATTERN.search(text.replace(" ", ""))]
