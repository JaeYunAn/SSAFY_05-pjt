"""
네트워크(토스증권, GMS) 없이 실행 가능한 단위 테스트
    python manage.py test comments
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .services.crawler import _to_stock_code


class CrawlerHelperTests(TestCase):
    def test_stock_code(self):
        self.assertEqual(_to_stock_code("/stocks/A005930/order"), "005930")
        self.assertEqual(_to_stock_code("/stocks/US19801212001/order"), "US19801212001")
        self.assertEqual(_to_stock_code(""), "")


class ViewTests(TestCase):
    def test_empty_company_name_does_nothing(self):
        with patch("comments.views.crawl_comments") as crawl:
            response = self.client.get(reverse("comments:company"), {"company_name": "   "})
        self.assertRedirects(response, reverse("comments:index"))
        crawl.assert_not_called()
