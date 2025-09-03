from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse

User = settings.AUTH_USER_MODEL


class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name}"
    

class Client(models.Model):
    name = models.CharField(max_length=200)          # Nom du contact
    phone_number = models.CharField(max_length=200)  # Téléphone
    company = models.CharField(max_length=200)       # Société

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["company", "name"]

    def __str__(self):
        return f"{self.name} ({self.company})"


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouvert"
        IN_PROGRESS = "WIP", "En cours"
        RESOLVED = "RES", "Résolu"
        CLOSED = "CLO", "Fermé"

    class Priority(models.TextChoices):
        LOW = "LOW", "Basse"
        MEDIUM = "MED", "Moyenne"
        HIGH = "HIG", "Haute"
        URGENT = "URG", "Urgente"

    title = models.CharField(max_length=200)
    description = models.TextField()

    # 👇 Client externe (modèle local à l'app tickets)
    client = models.ForeignKey("tickets.Client", on_delete=models.PROTECT, related_name="tickets")

    # 👇 Logiciel/produit (indépendant des clients)
    project = models.ForeignKey("tickets.Project", on_delete=models.PROTECT, related_name="tickets")

    # 👇 Utilisateur interne (rôle REPORTER) qui ouvre le ticket
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_tickets",
    )

    # 👇 Développeur assigné (optionnel)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    status = models.CharField(max_length=4, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=3, choices=Priority.choices, default=Priority.MEDIUM)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title}"

    def get_absolute_url(self):
        return reverse("tickets:ticket_detail", args=[self.pk])

    def clean(self):
        errors = {}

        # Reporter doit être un REPORTER
        if self.reporter and getattr(self.reporter, "role", None) != "REP":
            errors["reporter"] = "Le reporter doit avoir le rôle REPORTER."

        # Assignee (si présent) doit être un DEV
        if self.assignee and getattr(self.assignee, "role", None) != "DEV":
            errors["assignee"] = "L’intervenant assigné doit être un développeur."

        if errors:
            raise ValidationError(errors)



class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment #{self.pk} on Ticket #{self.ticket_id}"
