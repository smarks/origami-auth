"""origami-auth — the shared Tarmar authentication app.

Provides the Tarmar user model and the full login surface shared across
projects:

- :class:`origami_auth.base.AbstractOrigamiUser` — an abstract user with profile
  fields (``real_name``, ``phone``, ``discord``, ``preferred_contact``) and roles
  (``is_role_admin``, ``is_dm``, ``is_player``). Apps with an existing deployed
  ``AUTH_USER_MODEL`` subclass this in place (migration-neutral) rather than
  swapping their user model.
- :class:`origami_auth.models.User` — a concrete subclass for greenfield apps that
  set ``AUTH_USER_MODEL = "origami_auth.User"``.
- Register / login (rate-limited) / logout / profile / users-admin views, a rich
  registration form bound to ``get_user_model()``, URLs, and override-friendly
  templates.

Domain-agnostic plumbing (rate limiting, audit logging, JSON helpers,
``ActivePageMixin``) lives in the companion ``origami-common`` package; only
user/role-aware pieces live here.
"""
