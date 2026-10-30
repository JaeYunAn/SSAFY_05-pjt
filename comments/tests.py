"""
네트워크(토스증권, GMS) 없이 실행 가능한 단위 테스트
    python manage.py test comments
"""

from django.test import TestCase
from django.urls import reverse


class ViewTests(TestCase):
    def test_empty_company_name_does_nothing(self):
        response = self.client.get(reverse("comments:company"), {"company_name": "   "})
        self.assertRedirects(response, reverse("comments:index"))
