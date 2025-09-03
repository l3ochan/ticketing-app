from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from .models import Ticket, Project
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django import forms
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Ticket, Comment


User = get_user_model()


class ClientScopedQuerysetMixin:
    def scope_queryset(self, qs):
        u = self.request.user
        if getattr(u, "role", None) == "CLI":
            qs = qs.filter(customer=u)
        return qs

    def get_queryset(self):
        qs = super().get_queryset()
        return self.scope_queryset(qs)
    
class ReporterRequiredMixin(UserPassesTestMixin):
    def test_func(self): return self.request.user.is_authenticated and self.request.user.is_reporter

class DeveloperRequiredMixin(UserPassesTestMixin):
    def test_func(self): return self.request.user.is_authenticated and self.request.user.is_developer

class TicketListView(LoginRequiredMixin, ClientScopedQuerysetMixin, ListView):
    model = Ticket
    paginate_by = 20
    ordering = "-created_at"


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "tickets/ticket_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = CommentForm()
        return context



class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    # on liste 'customer' pour les reporters/devs, mais on le retire pour les clients
    fields = ["title", "description", "reporter", "customer", "project", "priority", "assignee"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user

        if getattr(user, "role", None) == "CLI":
            # 👉 client : on enlève le champ du formulaire (sinon il est requis et non posté)
            form.fields.pop("customer", None)
            form.fields.pop("assignee", None)
            form.fields.pop("reporter", None)
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


class TicketUpdateView(LoginRequiredMixin, ClientScopedQuerysetMixin, UpdateView):
    model = Ticket
    fields = ["title","description","priority","assignee","status"]

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 2, "placeholder": "Écrire un message..."})
        }

@login_required
@require_POST
def add_comment(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        comment.save()
        messages.success(request, "Message envoyé.")
    else:
        messages.error(request, "Erreur lors de l’envoi du message.")
    return redirect("tickets:ticket_detail", pk=pk)


def ticket_close(request, pk):
    t = get_object_or_404(Ticket, pk=pk)
    # Clients : jamais
    if getattr(request.user, "role", None) == "CLI":
        raise PermissionDenied("Vous ne pouvez pas clôturer ce ticket.")
    # Dev/Reporter : autorisés ? à toi de choisir; ici on autorise dev/staff seulement
    if not (getattr(request.user, "is_developer", False) or request.user.is_staff):
        raise PermissionDenied("Action réservée aux développeurs.")
    t.status = t.Status.CLOSED
    t.closed_at = timezone.now()
    t.save()
    return redirect("tickets:ticket_detail", pk=pk)