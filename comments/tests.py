"""
네트워크(토스증권, GMS) 없이 실행 가능한 단위 테스트
    python manage.py test comments
"""
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CommentAnalysis
from .services import llm
from .services.crawler import CrawlResult, _to_stock_code
from .services.preprocess import clean_text, compute_iqr_threshold, find_profanity, preprocess_comments


def make_text(length):
    """같은 글자 반복 축약 규칙에 걸리지 않는 지정 길이의 문자열"""
    return ("가나다라마바사아자차" * 10)[:length]


class PreprocessTests(TestCase):
    def test_clean_text_removes_patterns_and_special_chars(self):
        self.assertEqual(clean_text("좋아요ㅋㅋㅋㅋ!!"), "좋아요")
        self.assertEqual(clean_text("마인드💛 급할거   전혀 없어보임!!"), "마인드 급할거 전혀 없어보임")
        self.assertEqual(clean_text("링크 https://tossinvest.com/u/abc 참고"), "링크 참고")
        self.assertEqual(clean_text("깔깔깔깔 1000만원"), "깔깔 1000만원")
        self.assertEqual(clean_text(None), "")

    def test_length_filter_and_duplicates(self):
        comments = ["", "ㅋㅋㅋ", "5주", "정상적인 댓글입니다", "정상적인 댓글입니다!!", make_text(77)]
        result = preprocess_comments(comments)
        self.assertEqual(result.cleaned, ["정상적인 댓글입니다"])
        reasons = [r["reason"] for r in result.removed]
        self.assertIn("결측치", reasons)
        self.assertIn("중복", reasons)
        self.assertTrue(any(r.startswith("길이 2자") for r in reasons))
        self.assertTrue(any("> 76" in r for r in reasons))

    def test_boundary_lengths_are_kept(self):
        result = preprocess_comments([make_text(5), make_text(76), make_text(4)])
        self.assertEqual(len(result.cleaned), 2)

    def test_iqr_threshold(self):
        info = compute_iqr_threshold([10, 20, 30, 40, 50])
        self.assertEqual((info["q1"], info["q3"], info["iqr"]), (20, 40, 20))
        self.assertEqual((info["lower_fence"], info["upper_fence"]), (-10, 70))
        self.assertEqual((info["min_length"], info["max_length"]), (5, 76))

    def test_find_profanity(self):
        self.assertEqual(find_profanity(["좋은 회사", "이런 병 신 같은", "존나 오르네"]), [1, 2])


class CrawlerHelperTests(TestCase):
    def test_stock_code(self):
        self.assertEqual(_to_stock_code("/stocks/A005930/order"), "005930")
        self.assertEqual(_to_stock_code("/stocks/US19801212001/order"), "US19801212001")
        self.assertEqual(_to_stock_code(""), "")


def fake_gms_response(content, status=200):
    response = MagicMock(status_code=status, text=content)
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return response


@override_settings(GMS_KEY="test-key")
class LLMTests(TestCase):
    def test_parse_json_with_code_block(self):
        self.assertEqual(llm.parse_json("```json\n[1, 3]\n```"), [1, 3])

    @patch("comments.services.llm.requests.post")
    def test_find_inappropriate_filters_invalid_indices(self, post):
        post.return_value = fake_gms_response('[0, "2", 9, "x"]')
        self.assertEqual(llm.find_inappropriate(["a", "b", "c"]), [0, 2])
        body = post.call_args.kwargs["json"]
        self.assertIn("JSON 배열", body["messages"][-1]["content"])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    @override_settings(GMS_KEY="")
    def test_missing_key(self):
        with self.assertRaisesMessage(llm.LLMError, "GMS_KEY"):
            llm.chat("hi")


def read_events(response):
    body = b"".join(response.streaming_content).decode()
    return [json.loads(line) for line in body.splitlines() if line.strip()]


class ViewTests(TestCase):
    def test_empty_company_name_does_nothing(self):
        with patch("comments.views.crawl_comments") as crawl:
            response = self.client.get(reverse("comments:company"), {"company_name": "   "})
        self.assertRedirects(response, reverse("comments:index"))
        crawl.assert_not_called()

    @patch("comments.views.find_inappropriate", return_value=[1])
    @patch("comments.views.crawl_comments")
    def test_stream_creates_analysis_for_review(self, crawl, _find):
        crawl.return_value = CrawlResult(
            query="삼성", stock_name="삼성전자", stock_code="005930", url="https://example.com",
            comments=["20만 갈 것 같아요!!", "이런 존나 같은 주식", "ㅋㅋㅋ", "364주"],
        )
        response = self.client.get(reverse("comments:company"), {"company_name": "삼성"})
        events = read_events(response)

        self.assertEqual(events[-1]["type"], "done")
        analysis = CommentAnalysis.objects.get()
        self.assertEqual(analysis.stock_name, "삼성전자")
        self.assertEqual(analysis.candidate_comments, ["20만 갈 것 같아요", "이런 존나 같은 주식"])
        self.assertEqual(analysis.moderation["llm_flagged"], [1])
        self.assertEqual(analysis.moderation["keyword_flagged"], [1])
        self.assertEqual(analysis.status, CommentAnalysis.Status.REVIEW)
        self.assertEqual(events[-1]["redirect"], reverse("comments:review", args=[analysis.pk]))

    def _make_analysis(self):
        return CommentAnalysis.objects.create(
            query="삼성", stock_name="삼성전자", raw_comments=["원본1", "원본2", "원본3"],
            candidate_comments=["댓글 하나", "욕설 댓글", "댓글 셋"], moderation={"llm_flagged": [1]},
            iqr_threshold=compute_iqr_threshold([5, 5, 4]),
        )

    def test_review_page_prechecks_flagged(self):
        analysis = self._make_analysis()
        response = self.client.get(reverse("comments:review", args=[analysis.pk]))
        self.assertContains(response, 'value="1"\n                       data-flagged="1" checked')
        self.assertContains(response, "LLM 판정")
