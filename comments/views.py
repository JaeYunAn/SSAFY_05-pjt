import json
import queue
import threading

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .models import CommentAnalysis
from .services.crawler import CrawlError, crawl_comments
from .services.integration import build_final_dataset
from .services.llm import LLMError, augment_comments, find_inappropriate, summarize_comments
from .services.preprocess import find_profanity, preprocess_comments


def index(request):
    """F601 회사명 입력 화면"""
    return render(request, "comments/index.html", {"limit": settings.CRAWLER_COMMENT_LIMIT})


def company(request):
    """
    F601 회사명 입력 및 검증 -> F603~F605 크롤링·전처리를 실행하며 진행 상황을 스트리밍한다.

    응답은 한 줄에 하나의 JSON 이벤트(NDJSON)이다.
        {"type": "progress", "message": "...", "stage": "..."}  진행 상황 (stage: collect / preprocess / review)
        {"type": "error",    "message": "..."}  예외 상황 안내 (F611)
        {"type": "done",     "redirect": "..."} 완료 -> 검수 화면으로 이동
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
        except CrawlError as e:
            outcome["error"] = str(e)
        except Exception as e:  # 예상하지 못한 셀레니움 오류 등
            outcome["error"] = f"댓글 수집 중 오류가 발생했습니다: {e}"
        finally:
            progress.put(None)

    threading.Thread(target=worker, daemon=True).start()
    while (message := progress.get()) is not None:
        yield _event("progress", message=message, stage="collect")

    if "error" in outcome:
        yield _event("error", message=outcome["error"])
        return
    crawled = outcome["result"]

    # 2) 정규식 기반 전처리 (F605)
    yield _event("progress", message="전처리 중... (특수문자·불필요 패턴 제거, 길이 필터링)", stage="preprocess")
    pre = preprocess_comments(crawled.comments)
    if not pre.cleaned:
        yield _event("error", message=(
            f"'{crawled.stock_name}' 댓글 {len(crawled.comments)}개를 수집했지만 "
            "전처리 후 남은 댓글이 없습니다. 다른 회사로 다시 시도해 주세요."
        ))
        return

    # 3) 부적절 댓글 판정 (F605) - LLM 판정 + 욕설 키워드 감지, 최종 제외 여부는 사용자가 검수 화면에서 결정
    yield _event("progress", message="GMS로 부적절한 댓글을 검사하는 중...", stage="review")
    llm_flagged, llm_error = [], ""
    try:
        llm_flagged = find_inappropriate(pre.cleaned)
    except LLMError as e:
        llm_error = str(e)
        yield _event("progress", message=f"⚠ LLM 검사 실패 - 검수 화면에서 직접 확인해 주세요. ({e})", stage="review")

    analysis = CommentAnalysis.objects.create(
        query=company_name,
        stock_name=crawled.stock_name,
        stock_code=crawled.stock_code,
        source_url=crawled.url,
        raw_comments=crawled.comments,
        candidate_comments=pre.cleaned,
        preprocess_removed=pre.removed,
        moderation={
            "llm_flagged": llm_flagged,
            "keyword_flagged": find_profanity(pre.cleaned),
            "llm_error": llm_error,
        },
        iqr_threshold=pre.iqr,
    )
    yield _event("progress", message="수집·전처리 완료! 부적절 댓글 검수 화면으로 이동합니다.", stage="review")
    yield _event("done", redirect=reverse("comments:review", args=[analysis.pk]))


@require_http_methods(["GET", "POST"])
def review(request, pk):
    """
    부적절 댓글 직접 검수 -> 제외할 댓글을 확정하면 증강(F606)·통합(F607) 후 DB 에 저장한다.
    """
    analysis = get_object_or_404(CommentAnalysis, pk=pk)

    if request.method == "POST":
        excluded = set()
        for value in request.POST.getlist("exclude"):
            if value.isdigit() and int(value) < len(analysis.candidate_comments):
                excluded.add(int(value))

        cleaned = [t for i, t in enumerate(analysis.candidate_comments) if i not in excluded]
        if not cleaned:
            messages.error(request, "모든 댓글을 제외하면 증강할 데이터가 없습니다. 최소 1개 이상의 댓글을 남겨 주세요.")
            return redirect("comments:review", pk=pk)

        try:
            augmented = augment_comments(cleaned)
        except LLMError as e:
            messages.error(request, f"데이터 증강에 실패했습니다. {e}")
            return redirect("comments:review", pk=pk)

        analysis.review_removed = [t for i, t in enumerate(analysis.candidate_comments) if i in excluded]
        analysis.cleaned_comments = cleaned
        analysis.augmented_comments = augmented
        analysis.final_comments = build_final_dataset(cleaned, augmented)
        analysis.status = CommentAnalysis.Status.DONE
        analysis.save()
        return redirect("comments:result", pk=pk)

    items = analysis.review_items()
    return render(request, "comments/review.html", {
        "analysis": analysis,
        "items": items,
        "flagged_count": sum(item["flagged"] for item in items),
    })


def result(request, pk):
    """F607 원본 / 전처리 / 증강 / 최종 결과 통합 출력"""
    analysis = get_object_or_404(CommentAnalysis, pk=pk)
    if not analysis.is_done:
        return redirect("comments:review", pk=pk)
    return render(request, "comments/result.html", {"analysis": analysis})


@require_POST
def summary(request, pk):
    """F610 수집된 전체 댓글 요약 (요약 버튼 클릭 시 비동기 호출, 결과는 DB 에 저장)"""
    analysis = get_object_or_404(CommentAnalysis, pk=pk)
    try:
        analysis.summary = summarize_comments(analysis.stock_name, analysis.raw_comments)
    except LLMError as e:
        return JsonResponse({"error": str(e)}, status=502)
    analysis.save(update_fields=["summary"])
    return JsonResponse({"summary": analysis.summary})


def export_json(request, pk):
    """F607 통합 결과 집합(단계별 데이터 포함)을 JSON 으로 내려준다."""
    analysis = get_object_or_404(CommentAnalysis, pk=pk)
    return JsonResponse(analysis.to_dict(), json_dumps_params={"ensure_ascii": False, "indent": 2})
