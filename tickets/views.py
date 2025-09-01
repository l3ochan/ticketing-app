from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from .models import Ticket

class ReporterRequiredMixin(UserPassesTestMixin):
    def test_func(self): return self.request.user.is_authenticated and self.request.user.is_reporter

class DeveloperRequiredMixin(UserPassesTestMixin):
    def test_func(self): return self.request.user.is_authenticated and self.request.user.is_developer

class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    paginate_by = 20
    ordering = "-created_at"

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket

class TicketCreateView(LoginRequiredMixin, ReporterRequiredMixin, CreateView):
    model = Ticket
    fields = ["title","description","client","project","priority","assignee"]
    def form_valid(self, form):
        form.instance.reporter = self.request.user
        return super().form_valid(form)

class TicketUpdateView(LoginRequiredMixin, UpdateView):
    model = Ticket
    fields = ["title","description","priority","assignee","status"]
    def dispatch(self, request, *args, **kwargs):
        # Exemple de règle : seuls devs ou le reporter peuvent modifier
        obj = self.get_object()
        if not (request.user.is_developer or obj.reporter_id == request.user.id):
            return redirect("tickets:ticket_detail", pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
@login_required
@require_POST
def ticket_close(request, pk):
    t = get_object_or_404(Ticket, pk=pk)
    # Exemple : seuls devs ferment
    if request.user.is_developer:
        t.status = t.Status.CLOSED
        t.closed_at = now()
        t.save()
    return redirect("tickets:ticket_detail", pk=pk)
