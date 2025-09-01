from django.contrib import admin
from .models import Client, Project, Ticket, Comment
admin.site.register(Client)
admin.site.register(Project)
admin.site.register(Ticket)
admin.site.register(Comment)
