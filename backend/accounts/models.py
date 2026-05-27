from django.contrib.auth.models import AbstractUser
from django.db import models


class Organisation(models.Model):
    """
    Top-level tenant. Every piece of data is scoped to an org.
    Multi-tenancy is row-level: org FK on every key model.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Reporting year for grouping — can be calendar or fiscal
    reporting_year_start = models.CharField(
        max_length=5, default='01-01',
        help_text="MM-DD, e.g. '04-01' for April fiscal year start"
    )

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_ANALYST = 'analyst'
    ROLE_ADMIN = 'admin'
    ROLE_AUDITOR = 'auditor'
    ROLE_CHOICES = [
        (ROLE_ANALYST, 'Analyst'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_AUDITOR, 'Auditor (read-only)'),
    ]

    organisation = models.ForeignKey(
        Organisation, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='users'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST)

    def __str__(self):
        return f"{self.username} ({self.organisation})"
