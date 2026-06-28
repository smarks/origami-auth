from .base import AbstractOrigamiUser


class User(AbstractOrigamiUser):
    """Concrete shared user for greenfield projects.

    Apps with no existing user model set ``AUTH_USER_MODEL = "origami_auth.User"``
    and get the full Tarmar profile/role set out of the box. Apps that already
    have a deployed ``AUTH_USER_MODEL`` should instead subclass
    :class:`origami_auth.base.AbstractOrigamiUser` in their own app and leave this
    model unused (keep ``origami_auth`` out of their ``INSTALLED_APPS``).
    """
