from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        DEVELOPER = "DEV", "Développeur"
        REPORTER  = "REP", "Rapporteur"
    role = models.CharField(max_length=3, choices=Role.choices, default=Role.REPORTER)

    @property
    def is_developer(self): return self.role == self.Role.DEVELOPER
    @property
    def is_reporter(self):  return self.role == self.Role.REPORTER
