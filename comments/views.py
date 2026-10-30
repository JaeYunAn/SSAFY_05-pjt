import json
import queue
import threading

from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render

from .models import CommentAnalysis
from .services.crawler import crawl_comments


def index(request):
    """F601 회사명 입력 화면"""
    return render(request, "comments/index.html", {"limit": settings.CRAWLER_COMMENT_LIMIT})


def company(request):
    """
    F601 회사명 입력 및 검증 -> F603·F604 크롤링을 실행하며 진행 상황을 스트리밍한다.
    수집한 원본 댓글은 DB 에 저장한다.

    응답은 한 줄에 하나의 JSON 이벤트(NDJSON)이다.
        {"type": "progress", "message": "...", "stage": "collect"}  진행 상황
    """
    company_name = request.GET.get("company_name", "").strip()
    if not company_name:
        # 입력값이 없으면 데이터 수집을 수행하지 않는다.
        return redirect("comments:index")

    print(company_name, flush=True)  # VS Code 터미널에 입력한 회사명 출력

    response = StreamingHttpResponse(_crawl_stream(company_name), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _event(type_, **data):
    return json.dumps({"type": type_, **data}, ensure_ascii=False) + "\n"


def _crawl_stream(company_name):
    # 1) 크롤링 (F603, F604) - 별도 스레드에서 실행하고, 진행 메시지를 큐로 받아 바로 전송한다.
    progress = queue.Queue()
    outcome = {}

    def worker():
        try:
            outcome["result"] = crawl_comments(
                company_name,
                limit=settings.CRAWLER_COMMENT_LIMIT,
                headless=settings.CRAWLER_HEADLESS,
                on_progress=progress.put,
            )
        finally:
            progress.put(None)

    threading.Thread(target=worker, daemon=True).start()
    while (message := progress.get()) is not None:
        yield _event("progress", message=message, stage="collect")

    crawled = outcome["result"]
    CommentAnalysis.objects.create(
        query=company_name,
        stock_name=crawled.stock_name,
        stock_code=crawled.stock_code,
        source_url=crawled.url,
        raw_comments=crawled.comments,
    )
