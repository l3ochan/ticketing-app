from django.contrib import admin
from .models import Project, Ticket, Comment
admin.site.register(Project)
admin.site.register(Ticket)
admin.site.register(Comment)
