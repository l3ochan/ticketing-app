# accounts/views.py
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def logout_any(request):
    logout(request)
    return redirect("login")
