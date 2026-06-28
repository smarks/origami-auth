# origami-auth

The **shared Tarmar authentication app**. Provides the Tarmar user model and the
full login surface (register / login / logout / profile / user-admin) shared
across projects. Domain-agnostic plumbing it builds on (rate limiting, audit
logging, JSON helpers, `ActivePageMixin`) lives in the companion
[`origami-common`](https://github.com/smarks/origami-common) package.

It provides:
- **`AbstractOrigamiUser`** (`origami_auth.base`) — an abstract user with profile
  fields (`real_name`, `phone`, `discord`, `preferred_contact`) and roles
  (`is_role_admin`, `is_dm`, `is_player`) plus a `can_manage_users` property.
- **`User`** (`origami_auth.models`) — a concrete subclass for greenfield apps.
- **register / login (rate-limited) / logout / profile / users-admin** views, a
  rich registration form bound to `get_user_model()`, URLs, and override-friendly
  templates (each extends `origami_auth/base.html`).
- `AdminOrDMRequiredMixin` for role-gated views.

## Greenfield project (no existing user model)

```python
# settings.py
INSTALLED_APPS += ["django.contrib.auth", "django.contrib.contenttypes",
                   "django.contrib.sessions", "django.contrib.messages",
                   "origami_auth"]
AUTH_USER_MODEL = "origami_auth.User"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
```

```python
# urls.py
path("accounts/", include("origami_auth.urls")),
```

Then `python manage.py migrate`. Restyle by overriding `origami_auth/base.html`
(or any of `login.html` / `register.html` / `profile.html` / `users_list.html`)
in your project's templates. Keep project-specific data in your **own** models
with a FK to the user — don't fork this app.

## App with an existing, deployed user model

A project already deployed with its own `AUTH_USER_MODEL` (e.g. tarmar-studio)
must **not** swap its user model — that breaks existing data. Instead it
re-parents its concrete `User` onto `AbstractOrigamiUser`:

```python
# the app's own models.py — NOT origami_auth in INSTALLED_APPS
from origami_auth.base import AbstractOrigamiUser

class User(AbstractOrigamiUser):
    class Meta(AbstractOrigamiUser.Meta):
        db_table = "accounts_user"   # keep the existing table
```

Because the abstract base's fields match the app's current ones verbatim, this is
**migration-neutral** (`makemigrations --check` reports nothing). The app imports
the views/forms/mixins directly and keeps its own URLs/templates. See
**[docs/tarmar-studio-integration.md](docs/tarmar-studio-integration.md)** for the
full guide and verification checklist.

## Develop

```bash
pip install -e ../origami-common      # sibling dependency, editable
pip install -e '.[test]'
pytest
```
