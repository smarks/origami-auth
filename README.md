# tarmar-auth

A small **reusable Django login app** shared across projects (melee, and
optionally others). Pure Django, no project-specific assumptions.

It provides:
- a minimal concrete **`User`** model (`tarmar_auth.User`, a plain `AbstractUser`),
- **register / login / logout / profile** views, a registration form, URLs, and
  override-friendly templates (each extends `tarmar_auth/base.html`).

## Use it in a project

```python
# settings.py
INSTALLED_APPS += ["django.contrib.auth", "django.contrib.contenttypes",
                   "django.contrib.sessions", "django.contrib.messages",
                   "tarmar_auth"]
AUTH_USER_MODEL = "tarmar_auth.User"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
```

```python
# urls.py
path("accounts/", include("tarmar_auth.urls")),
```

Then `python manage.py migrate`. Restyle by overriding `tarmar_auth/base.html`
(or any of `login.html` / `register.html` / `profile.html`) in your project's
templates.

Keep project-specific data (e.g. saved characters) in your **own** models with a
FK to the user — don't fork this app.

## Develop

```bash
pip install -e '.[test]'
pytest
```

> Note: a deployed project that already has its own custom `AUTH_USER_MODEL`
> (e.g. tarmar-studio) can share this app's *views/forms/templates* via a careful
> refactor, but should not swap its live user model — that breaks existing data.
> See **[docs/tarmar-studio-integration.md](docs/tarmar-studio-integration.md)**
> for the full adoption guide, options, and constraints.
