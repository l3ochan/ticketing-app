from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse

User = settings.AUTH_USER_MODEL


class Project(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["customer", "name"], name="uniq_project_per_customer"),
        ]

    def __str__(self):
        return f"{self.name}"

# tickets/models.py
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse

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

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer_tickets"
    )
    project = models.ForeignKey("tickets.Project", on_delete=models.PROTECT, related_name="tickets")

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_tickets",
        null=True, blank=True
    )

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_tickets"
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

        # le projet doit appartenir au même client
        if self.project_id and self.customer_id and self.project.customer_id != self.customer_id:
            errors["project"] = "Ce projet n'appartient pas à ce client."

        # si reporter est renseigné, il doit être REPORTER et différent du client
        if self.reporter:
            role = getattr(self.reporter, "role", None)
            if role != "REP":
                errors["reporter"] = "Le reporter doit avoir le rôle REPORTER."
            if self.reporter_id == self.customer_id:
                errors["reporter"] = "Le reporter doit être différent du client."

        # si assignee est renseigné, il doit être DEV
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
