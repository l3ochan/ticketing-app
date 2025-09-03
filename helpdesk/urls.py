from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView 
from accounts.views import logout_any
from django.conf.urls import handler403

handler403 = 'tickets.views.custom_permission_denied_view'

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/logout/", logout_any, name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),  # login/logout/password views
    path("", RedirectView.as_view(pattern_name="tickets:ticket_list", permanent=False)),
    path("tickets/", include("tickets.urls")),
]


