from django.contrib.auth.mixins import UserPassesTestMixin


class AdminOrDMRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be an admin or DM.

    Relies on ``user.can_manage_users`` from
    :class:`origami_auth.base.AbstractOrigamiUser`, so it belongs with the auth
    layer rather than the domain-agnostic ``origami_common`` mixins.
    """

    def test_func(self):
        return self.request.user.can_manage_users
