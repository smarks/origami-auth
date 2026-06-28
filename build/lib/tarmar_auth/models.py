from .base import AbstractTarmarUser


class User(AbstractTarmarUser):
    """Concrete shared user for greenfield projects.

    Apps with no existing user model set ``AUTH_USER_MODEL = "tarmar_auth.User"``
    and get the full Tarmar profile/role set out of the box. Apps that already
    have a deployed ``AUTH_USER_MODEL`` should instead subclass
    :class:`tarmar_auth.base.AbstractTarmarUser` in their own app and leave this
    model unused (keep ``tarmar_auth`` out of their ``INSTALLED_APPS``).
    """
