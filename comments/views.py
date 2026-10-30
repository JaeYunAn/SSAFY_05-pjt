from django.shortcuts import redirect, render


def index(request):
    """F601 회사명 입력 화면"""
    return render(request, "comments/index.html")


def company(request):
    """F601 회사명 입력 및 검증"""
    company_name = request.GET.get("company_name", "").strip()
    if not company_name:
        # 입력값이 없으면 데이터 수집을 수행하지 않는다.
        return redirect("comments:index")

    print(company_name, flush=True)  # VS Code 터미널에 입력한 회사명 출력
    return redirect("comments:index")
