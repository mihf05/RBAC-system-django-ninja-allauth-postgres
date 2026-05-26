from django.shortcuts import render


def login_view(request):
    """Render the login page."""
    return render(request, 'dashboard/login.html')


def dashboard_view(request):
    """Render the main dashboard SPA."""
    return render(request, 'dashboard/index.html')
