from .models import CommentAnalysis


def sidebar(request):
    """모든 화면의 사이드바에 최근 분석 페이지 목록을 보여준다."""
    return {
        "sidebar_analyses": CommentAnalysis.objects.only("pk", "query", "stock_name", "status", "created_at")[:12],
    }
