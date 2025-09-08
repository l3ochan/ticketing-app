from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django import forms
from django.contrib import messages
from .models import Ticket, Project, Comment, Client
from django.db.models import Count

def custom_permission_denied_view(request, exception=None):
    return render(request, '403.html', status=403)


class ReporterRequiredMixin(UserPassesTestMixin):
    def test_func(self): return self.request.user.is_authenticated and (self.request.user.is_reporter or self.request.user.is_staff or self.request.user.is_superuser)

class DeveloperRequiredMixin(UserPassesTestMixin):
    def test_func(self): return self.request.user.is_authenticated and (self.request.user.is_developer or self.request.user.is_staff or self.request.user.is_superuser)



User = get_user_model()

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "tickets/dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tickets = Ticket.objects.all()

        context["total_tickets"] = tickets.count()
        context["processed_tickets"] = tickets.filter(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]
        ).count()

        # Agrégats par priorité
        priority_counts = tickets.values("priority").annotate(count=Count("id"))

        # Mapping code -> label
        mapped = [
            {"code": item["priority"], "label": Ticket.Priority(item["priority"]).label, "count": item["count"]}
            for item in priority_counts
        ]

        # Ordre voulu : URG > HIG > MED > LOW
        priority_order = {"URG": 1, "HIG": 2, "MED": 3, "LOW": 4}
        mapped_sorted = sorted(mapped, key=lambda x: priority_order.get(x["code"], 99))

        context["tickets_by_priority"] = mapped_sorted

        # Statuts (même logique si tu veux un ordre personnalisé)
        status_counts = tickets.values("status").annotate(count=Count("id"))
        context["tickets_by_status"] = [
            {"code": item["status"], "label": Ticket.Status(item["status"]).label, "count": item["count"]}
            for item in status_counts
        ]

        return context


# --- Vu des projets ---
class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"


class ProjectCreateView(LoginRequiredMixin, DeveloperRequiredMixin, CreateView):
    model = Project
    fields = ["name", "description"]
    template_name = "projects/project_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Projet créé avec succès")
        return super().form_valid(form)


class ProjectUpdateView(LoginRequiredMixin, DeveloperRequiredMixin, UpdateView):
    model = Project
    fields = ["name", "description"]
    template_name = "projects/project_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Projet mis à jour")
        return super().form_valid(form)



# --- Vues Tickets ---
class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    paginate_by = 20
    ordering = "-created_at"


# --- Vues Clients ---
class ClientListView(LoginRequiredMixin, ReporterRequiredMixin, ListView):
    model = Client
    paginate_by = 20
    ordering = "name"
    template_name = "clients/client_list.html"


class ClientDetailView(LoginRequiredMixin, ReporterRequiredMixin,DetailView):
    model = Client
    template_name = "clients/client_detail.html"


class ClientCreateView(LoginRequiredMixin, ReporterRequiredMixin,CreateView):
    model = Client
    fields = ["name", "phone_number", "company"]
    template_name = "clients/client_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Client créé avec succès")
        return super().form_valid(form)


class ClientUpdateView(LoginRequiredMixin, ReporterRequiredMixin,  UpdateView):
    model = Client
    fields = ["name", "phone_number", "company"]
    template_name = "clients/client_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Client mis à jour")
        return super().form_valid(form)
    

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "tickets/ticket_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = CommentForm()
        return context


class TicketCreateView(LoginRequiredMixin, ReporterRequiredMixin,  CreateView):
    model = Ticket
    fields = ["title", "description", "client", "project", "priority", "assignee"]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user

        # Récupère tous les clients en base
        form.fields["client"].queryset = Client.objects.all()

        # récupère tous les projets en base
        form.fields["project"].queryset = Project.objects.all()

        form.fields["assignee"].queryset = User.objects.filter(role="DEV", is_active=True)

        # Masquer "assignee" si l'utilisateur n'est pas développeur ni staff
        if not (getattr(user, "is_reporter", False) or user.is_staff):
            form.fields.pop("assignee", None)

        return form

    def form_valid(self, form):
        # Forcer le reporter = utilisateur connecté
        form.instance.reporter = self.request.user
        return super().form_valid(form)


class TicketUpdateView(LoginRequiredMixin, ReporterRequiredMixin, UpdateView):
    model = Ticket
    fields = ["title", "description", "project", "priority", "assignee"]


# --- Commentaires ---
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


# --- Clôture d’un ticket ---
@login_required
def ticket_close(request, pk):
    t = get_object_or_404(Ticket, pk=pk)

    # Seuls devs ou staff peuvent clôturer
    if not (getattr(request.user, "is_developer", False) or request.user.is_staff):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée aux développeurs.")

    t.status = t.Status.CLOSED
    t.closed_at = timezone.now()
    t.save()
    return redirect("tickets:ticket_detail", pk=pk)


class AssignTicketForm(forms.Form):
    assignee = forms.ModelChoiceField(
        queryset=User.objects.filter(role="DEV", is_active=True),
        label="Développeur",
    )

@login_required
def ticket_assign(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)

    # On n'assigne que si le ticket est encore ouvert
    if ticket.status != Ticket.Status.OPEN:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Ce ticket n'est pas ouvert et ne peut plus être assigné.")

    if request.method == "POST":
        form = AssignTicketForm(request.POST)
        if form.is_valid():
            ticket.assignee = form.cleaned_data["assignee"]
            ticket.status = Ticket.Status.IN_PROGRESS
            ticket.save()
            messages.success(request, f"Ticket assigné à {ticket.assignee}.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
    else:
        form = AssignTicketForm()

    return render(request, "tickets/ticket_assign.html", {"ticket": ticket, "form": form})


@login_required
def ticket_resolve(request, pk):
    t = get_object_or_404(Ticket, pk=pk)

    # Seuls devs ou staff peuvent clôturer
    if not (getattr(request.user, "is_developer", False) or request.user.is_staff):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée aux développeurs.")

    t.status = t.Status.RESOLVED
    t.save()
    return redirect("tickets:ticket_detail", pk=pk)


@login_required
def ticket_reopen(request, pk):
    t = get_object_or_404(Ticket, pk=pk)

    # Seuls devs ou staff peuvent clôturer
    if not (getattr(request.user, "is_reporter", False) or request.user.is_staff):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée aux rapporteurs.")

    t.status = t.Status.IN_PROGRESS
    t.save()
    return redirect("tickets:ticket_detail", pk=pk)