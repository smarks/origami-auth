"""The shared, abstract Tarmar user.

``AbstractTarmarUser`` carries every field and role a Tarmar app's user needs,
but defines **no** database table of its own (``abstract = True``). This module
deliberately contains no concrete model, so it is safe to import from a project
that does *not* list ``tarmar_auth`` in ``INSTALLED_APPS`` — e.g. a deployed app
(tarmar-studio) that keeps its own ``AUTH_USER_MODEL`` and only wants to point
its existing concrete ``User`` at this base. Because the field definitions match
that app's current ones verbatim, re-parenting onto this base produces no
migration against the live user table.

Greenfield apps instead use the concrete :class:`tarmar_auth.models.User`.
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

# Phone validator: optional +, then 7-15 digits (allows spaces/dashes for readability)
PHONE_VALIDATOR = RegexValidator(
    regex=r"^\+?[\d\s\-]{7,20}$",
    message="Enter a valid phone number (7-20 digits, may include +, spaces, dashes)",
)

# Discord validator: 2-32 alphanumeric chars, underscores, or periods
DISCORD_VALIDATOR = RegexValidator(
    regex=r"^[a-zA-Z0-9_.]{2,32}$",
    message="Enter a valid Discord username (2-32 alphanumeric, underscores, periods)",
)

CONTACT_CHOICES = [
    ("email", "Email"),
    ("phone", "Phone"),
    ("discord", "Discord"),
]


class AbstractTarmarUser(AbstractUser):
    """Abstract user with Tarmar profile fields and roles.

    Concrete subclasses (this library's :class:`~tarmar_auth.models.User`, or a
    consuming app's own ``User``) inherit these fields unchanged. Keep field
    definitions stable: a deployed app re-parents its live ``User`` onto this
    base expecting a migration-neutral change.
    """

    CONTACT_CHOICES = CONTACT_CHOICES

    real_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[PHONE_VALIDATOR])
    discord = models.CharField(
        max_length=50, blank=True, validators=[DISCORD_VALIDATOR]
    )
    preferred_contact = models.CharField(
        max_length=10, choices=CONTACT_CHOICES, blank=True
    )

    # Roles
    is_role_admin = models.BooleanField(default=False)
    is_dm = models.BooleanField(default=False)
    is_player = models.BooleanField(default=True)

    @property
    def can_manage_users(self):
        """Returns True if user can manage other users (admin or DM)."""
        return self.is_role_admin or self.is_dm

    class Meta(AbstractUser.Meta):
        abstract = True
