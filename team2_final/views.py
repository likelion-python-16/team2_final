from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse

# example_view가 있을 때만 등록
def example_view(_request):
    return HttpResponse("Example OK")

def landing(request):
    # 로그인 상태라면 곧바로 대시보드로
    if request.user.is_authenticated:
        return redirect("tasks:dashboard")
    # 아니면 랜딩 화면 보여주기
    return render(request, "landing.html")