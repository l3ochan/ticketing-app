from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from .models import Ticket, Project
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django import forms


User = get_user_model()

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

class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    # on liste 'customer' pour les reporters/devs, mais on le retire pour les clients
    fields = ["title", "description", "customer", "project", "priority", "assignee"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user

        if getattr(user, "role", None) == "CLI":
            # 👉 client : on enlève le champ du formulaire (sinon il est requis et non posté)
            form.fields.pop("customer", None)
            # et on fixe la valeur sur l'instance AVANT validation
            form.instance.customer = user
            # restreindre les projets du select
            form.fields["project"].queryset = Project.objects.filter(customer=user)
        else:
            # reporter/dev/staff : choisir un customer (seulement les users rôle CLIENT)
            form.fields["customer"].queryset = User.objects.filter(role="CLI", is_active=True)
            # (optionnel) filtrer project selon le customer choisi (si présent)
            cid = form.data.get("customer") or form.initial.get("customer")
            form.fields["project"].queryset = (
                Project.objects.filter(customer_id=cid) if cid else Project.objects.none()
            )

        # cacher 'assignee' aux non-dev (les clients ne le voient pas)
        if not (getattr(user, "is_developer", False) or user.is_staff):
            form.fields.pop("assignee", None)

        return form

    def form_valid(self, form):
        user = self.request.user
        # ceinture et bretelles : on (re)force les champs pilotés côté serveur
        if getattr(user, "role", None) == "CLI":
            form.instance.customer = user
            form.instance.reporter = None
        elif getattr(user, "role", None) == "REP":
            form.instance.reporter = user
        # sinon dev/staff : on laisse tel quel
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


