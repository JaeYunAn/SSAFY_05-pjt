from django.db import models


class CommentAnalysis(models.Model):
    """
    F602 / F607 - 한 번의 요청(회사 검색)에 대한 수집·전처리·검수·증강·통합 결과를 저장한다.
    """

    class Status(models.TextChoices):
        REVIEW = "review", "검수 대기"
        DONE = "done", "완료"

    query = models.CharField("검색어", max_length=100)
    stock_name = models.CharField("실제 종목명", max_length=100)
    stock_code = models.CharField("종목 코드", max_length=30, blank=True)
    source_url = models.URLField("수집 페이지", max_length=300, blank=True)

    # 단계별 결과 (JSON 리스트)
    raw_comments = models.JSONField("원본 댓글 목록", default=list)
    candidate_comments = models.JSONField("정규식 정제 결과 (검수 전)", default=list)
    preprocess_removed = models.JSONField("전처리 제거 댓글 (사유 포함)", default=list)
    moderation = models.JSONField("부적절 댓글 판정 정보", default=dict)
    review_removed = models.JSONField("검수에서 제외한 댓글 목록", default=list)
    cleaned_comments = models.JSONField("정제 댓글 목록", default=list)
    augmented_comments = models.JSONField("증강 댓글 목록", default=list)
    final_comments = models.JSONField("통합 결과 (정제 + 증강)", default=list)
    iqr_threshold = models.JSONField("IQR 임계값 정보", default=dict)
    summary = models.TextField("댓글 요약", blank=True)

    status = models.CharField("진행 상태", max_length=10, choices=Status.choices, default=Status.REVIEW)
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "댓글 분석 결과"
        verbose_name_plural = "댓글 분석 결과"

    def __str__(self):
        return f"{self.stock_name} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def is_done(self):
        return self.status == self.Status.DONE

    def review_items(self):
        """검수 화면용: 정제 후보 댓글마다 LLM/키워드 판정 여부를 붙여 반환"""
        llm_flagged = set(self.moderation.get("llm_flagged", []))
        keyword_flagged = set(self.moderation.get("keyword_flagged", []))
        return [
            {
                "index": i,
                "text": text,
                "llm": i in llm_flagged,
                "keyword": i in keyword_flagged,
                "flagged": i in llm_flagged or i in keyword_flagged,
            }
            for i, text in enumerate(self.candidate_comments)
        ]

    def augmentation_pairs(self):
        """결과 화면 비교 보기용: 정제 댓글과 그 댓글로 만든 증강 문장을 짝지어 반환"""
        return list(zip(self.cleaned_comments, self.augmented_comments))
