from django.urls import path
from . import views

app_name = "tickets"
urlpatterns = [
    path("", views.TicketListView.as_view(), name="ticket_list"),
    path("new/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("<int:pk>/edit/", views.TicketUpdateView.as_view(), name="ticket_update"),
    path("<int:pk>/close/", views.ticket_close, name="ticket_close"),
    path("<int:pk>/resolve/", views.ticket_resolve, name="ticket_resolve"),
    path("<int:pk>/reopen/", views.ticket_reopen, name="ticket_reopen"),
    path("<int:pk>/comment/", views.add_comment, name="add_comment"),
    path("clients/", views.ClientListView.as_view(), name="client_list"),
    path("clients/new/", views.ClientCreateView.as_view(), name="client_create"),
    path("clients/<int:pk>/", views.ClientDetailView.as_view(), name="client_detail"),
    path("clients/<int:pk>/edit/", views.ClientUpdateView.as_view(), name="client_update"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("projects/", views.ProjectListView.as_view(), name="project_list"),
    path("projects/new/", views.ProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", views.ProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="project_update"),
    path("<int:pk>/assign/", views.ticket_assign, name="ticket_assign"),
]