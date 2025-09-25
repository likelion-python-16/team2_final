from django.shortcuts import render


def landing(request):
    return render(request, "landing.html")


def example_view(request):
    return render(request, "example.html")
