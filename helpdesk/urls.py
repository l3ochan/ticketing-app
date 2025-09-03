from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView 
from django.contrib.auth.views import LogoutView
from accounts.views import logout_any


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/logout/", logout_any, name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),  # login/logout/password views
    path("", RedirectView.as_view(pattern_name="tickets:ticket_list", permanent=False)),
    path("tickets/", include("tickets.urls")),
]


