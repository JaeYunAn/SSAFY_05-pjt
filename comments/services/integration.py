"""
F607 데이터 통합 관리

정제(전처리) 데이터와 증강 데이터를 단계(stage) 구분이 가능한 하나의 결과 집합으로 합친다.
증강 문장은 source 필드로 어떤 정제 댓글에서 만들어졌는지 추적할 수 있다.
"""

STAGE_CLEANED = "cleaned"
STAGE_AUGMENTED = "augmented"
STAGE_LABELS = {STAGE_CLEANED: "정제", STAGE_AUGMENTED: "증강"}


def build_final_dataset(cleaned, augmented) -> list:
    """
    [{"stage": "cleaned",   "text": "...", "source": 0},
     {"stage": "augmented", "text": "...", "source": 0}, ...]
    """
    dataset = [
        {"stage": STAGE_CLEANED, "text": text, "source": i}
        for i, text in enumerate(cleaned)
    ]
    dataset += [
        {"stage": STAGE_AUGMENTED, "text": text, "source": i}
        for i, text in enumerate(augmented)
    ]
    return dataset
