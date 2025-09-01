from django.conf import settings
from django.db import models

class Client(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    def __str__(self): return self.name

class Project(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    class Meta:
        unique_together = ("client", "name")
    def __str__(self): return f"{self.client} · {self.name}"

class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouvert"
        IN_PROGRESS = "WIP", "En cours"
        RESOLVED = "RES", "Résolu"
        CLOSED = "CLO", "Fermé"

    class Priority(models.TextChoices):
        LOW="LOW","Basse"; MEDIUM="MED","Moyenne"; HIGH="HIG","Haute"; URGENT="URG","Urgente"

    title = models.CharField(max_length=200)
    description = models.TextField()
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="tickets")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="tickets")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_tickets")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets")
    status = models.CharField(max_length=4, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=3, choices=Priority.choices, default=Priority.MEDIUM)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at  = models.DateTimeField(null=True, blank=True)

    def __str__(self): return f"[{self.get_status_display()}] {self.title}"

class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
