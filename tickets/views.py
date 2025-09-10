from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView, DeleteView
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django import forms
from django.contrib import messages
from .models import Ticket, Project, Comment, Client
from django.db.models import Count, Q, Case, When, IntegerField
from django.utils.html import escape
from django.urls import reverse_lazy



def _log_status_change(ticket, user, old_code, new_code):
    # labels lisibles
    old_label = Ticket.Status(old_code).label if old_code else "—"
    new_label = Ticket.Status(new_code).label if new_code else "—"
    msg = f"🛈 Statut changé : {escape(old_label)} → {escape(new_label)} par {escape(user.get_username())}"
    Comment.objects.create(ticket=ticket, author=user, body=msg, is_system=True)

def _log_assignment(ticket, user, assignee):
    who = escape(assignee.get_username()) if assignee else "—"
    by  = escape(user.get_username())
    msg = f"🛠️ Assigné à {who} par {by}"
    Comment.objects.create(ticket=ticket, author=user, body=msg, is_system=True)


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


        priority_counts = tickets.values("priority").annotate(count=Count("id"))


        mapped = [
            {"code": item["priority"], "label": Ticket.Priority(item["priority"]).label, "count": item["count"]}
            for item in priority_counts
        ]

   
        priority_order = {"URG": 1, "HIG": 2, "MED": 3, "LOW": 4}
        mapped_sorted = sorted(mapped, key=lambda x: priority_order.get(x["code"], 99))

        context["tickets_by_priority"] = mapped_sorted

 
        status_counts = tickets.values("status").annotate(count=Count("id"))
        context["tickets_by_status"] = [
            {"code": item["status"], "label": Ticket.Status(item["status"]).label, "count": item["count"]}
            for item in status_counts
        ]

        return context


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    paginate_by = 20
    ordering = "name"
    template_name = "projects/project_list.html"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q)
            )
        return qs


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



# views.py
from django.db.models import Case, When, IntegerField, Q

class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    paginate_by = 20
    template_name = "tickets/ticket_list.html"

    def _with_ranks(self, qs):
        return qs.annotate(
            status_rank=Case(
                When(status="OPEN", then=0),
                When(status="WIP",  then=1),
                When(status="RES",  then=2),
                When(status="CLO",  then=3),
                default=99, output_field=IntegerField(),
            ),
            priority_rank=Case(
                When(priority="URG", then=0),
                When(priority="HIG", then=1),
                When(priority="MED", then=2),
                When(priority="LOW", then=3),
                default=99, output_field=IntegerField(),
            ),
        )

    def get_queryset(self):
        qs = (super().get_queryset()
              .select_related("client", "project", "reporter", "assignee"))

        # --- recherche & filtres (comme chez toi) ---
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(client__name__icontains=q) |
                Q(client__company__icontains=q) |
                Q(project__name__icontains=q) |
                Q(reporter__username__icontains=q) |
                Q(assignee__username__icontains=q)
            )

        status_list   = [s for s in self.request.GET.getlist("status")   if s in dict(Ticket.Status.choices)]
        priority_list = [p for p in self.request.GET.getlist("priority") if p in dict(Ticket.Priority.choices)]

        def to_ints(xs):
            out=[]
            for x in xs:
                try: out.append(int(x))
                except: pass
            return out
        client_ids  = to_ints(self.request.GET.getlist("client"))
        project_ids = to_ints(self.request.GET.getlist("project"))

        if status_list:   qs = qs.filter(status__in=status_list)
        if priority_list: qs = qs.filter(priority__in=priority_list)
        if client_ids:    qs = qs.filter(client_id__in=client_ids)
        if project_ids:   qs = qs.filter(project_id__in=project_ids)

        # --- TRI ---
        sort = (self.request.GET.get("sort") or "").strip()

        if not sort:
            # ✅ TRI PAR DÉFAUT combiné : Statut ↑, Priorité ↑, Date ↓
            qs = self._with_ranks(qs).order_by("status_rank", "priority_rank", "-created_at")
            return qs

        # Sinon : on respecte tes boutons existants
        if sort in ("-created", "created"):
            return qs.order_by(sort.replace("created", "created_at"))

        if sort in ("priority", "-priority"):
            qs = self._with_ranks(qs)
            return qs.order_by("priority_rank", "created_at") if sort == "priority" else qs.order_by("-priority_rank", "-created_at")

        if sort in ("status", "-status"):
            qs = self._with_ranks(qs)
            return qs.order_by("status_rank", "created_at") if sort == "status" else qs.order_by("-status_rank", "-created_at")

        if sort in ("client", "-client"):
            return qs.order_by(sort.replace("client", "client__company"))

        if sort in ("project", "-project"):
            return qs.order_by(sort.replace("project", "project__name"))

        # fallback
        return self._with_ranks(qs).order_by("status_rank", "-priority_rank", "-created_at")


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        GET = self.request.GET

        ctx["status_choices"]   = Ticket.Status.choices
        ctx["priority_choices"] = Ticket.Priority.choices
        ctx["clients"]  = Client.objects.order_by("company", "name")
        ctx["projects"] = Project.objects.order_by("name")

        ctx["current"] = {
            "q":        GET.get("q", ""),
            "status":   GET.getlist("status"),
            "priority": GET.getlist("priority"),
            "client":   GET.getlist("client"),
            "project":  GET.getlist("project"),
            "sort":     GET.get("sort", "-created"),
        }

        # conserver les filtres sans "sort"
        from django.utils.http import urlencode
        pairs = []
        for k, vals in GET.lists():
            if k in ("sort", "page"):
                continue
            for v in vals:
                if v != "":
                    pairs.append((k, v))
        ctx["qs_without_sort"] = urlencode(pairs, doseq=True)
        return ctx





# --- Vues Clients ---
class ClientListView(LoginRequiredMixin, ReporterRequiredMixin, ListView):
    model = Client
    paginate_by = 20
    ordering = "name"
    template_name = "clients/client_list.html"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(company__icontains=q) |
                Q(phone_number__icontains=q)
            )
        return qs


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


@login_required
def ticket_close(request, pk):
    t = get_object_or_404(Ticket, pk=pk)
    if not (getattr(request.user, "is_developer", False) or request.user.is_staff):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée aux développeurs.")
    old = t.status
    t.status = t.Status.CLOSED
    t.closed_at = timezone.now()
    t.save()
    _log_status_change(t, request.user, old, t.status)  # 👈
    return redirect("tickets:ticket_detail", pk=pk)



class AssignTicketForm(forms.Form):
    assignee = forms.ModelChoiceField(
        queryset=User.objects.filter(role="DEV", is_active=True),
        label="Développeur",
    )

@login_required
def ticket_assign(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if ticket.status != Ticket.Status.OPEN:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Ce ticket n'est pas ouvert et ne peut plus être assigné.")

    if request.method == "POST":
        form = AssignTicketForm(request.POST)
        if form.is_valid():
            old = ticket.status
            ticket.assignee = form.cleaned_data["assignee"]
            ticket.status = Ticket.Status.IN_PROGRESS
            ticket.save()
            _log_assignment(ticket, request.user, ticket.assignee)         # 👈 log assign
            _log_status_change(ticket, request.user, old, ticket.status)   # 👈 log statut
            messages.success(request, f"Ticket assigné à {ticket.assignee}.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
    else:
        form = AssignTicketForm()

    return render(request, "tickets/ticket_assign.html", {"ticket": ticket, "form": form})


@login_required
def ticket_resolve(request, pk):
    t = get_object_or_404(Ticket, pk=pk)
    if not (getattr(request.user, "is_developer", False) or request.user.is_staff):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée aux développeurs.")
    old = t.status
    t.status = t.Status.RESOLVED
    t.save()
    _log_status_change(t, request.user, old, t.status)  # 👈
    return redirect("tickets:ticket_detail", pk=pk)



@login_required
def ticket_reopen(request, pk):
    t = get_object_or_404(Ticket, pk=pk)
    if not (getattr(request.user, "is_reporter", False) or request.user.is_staff):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée aux rapporteurs.")
    old = t.status
    t.status = t.Status.IN_PROGRESS
    t.save()
    _log_status_change(t, request.user, old, t.status)  # 👈
    return redirect("tickets:ticket_detail", pk=pk)




class TicketDeleteView(LoginRequiredMixin, ReporterRequiredMixin, DeleteView):
    model = Ticket
    template_name = "tickets/ticket_confirm_delete.html"
    success_url = reverse_lazy("tickets:ticket_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Ticket supprimé avec succès.")
        return super().delete(request, *args, **kwargs)
    

class ClientDeleteView(LoginRequiredMixin, ReporterRequiredMixin, DeleteView):
    model = Client
    template_name = "clients/client_confirm_delete.html"
    success_url = reverse_lazy("tickets:client_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Client supprimé avec succès.")
        return super().delete(request, *args, **kwargs)
    
class ProjectDeleteView(LoginRequiredMixin, ReporterRequiredMixin, DeleteView):
    model = Project
    template_name = "projects/project_confirm_delete.html"
    success_url = reverse_lazy("tickets:project_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Projet supprimé avec succès.")
        return super().delete(request, *args, **kwargs)