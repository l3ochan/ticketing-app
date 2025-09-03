from django.contrib import admin
from .models import Project, Ticket, Comment, Client
admin.site.register(Project)
admin.site.register(Ticket)
admin.site.register(Comment)
admin.site.register(Client)
