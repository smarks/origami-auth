# Integrating `tarmar-auth` into tarmar-studio — handoff

_Written for the tarmar-studio Claude. Context: `tarmar-auth` is the reusable
Django login app that **melee** already uses; the question is whether/how
**tarmar-studio** should share it._

---

## 0. The one constraint that drives every decision

**tarmar-studio is already deployed with its own custom user model.** Its
`settings.py` has `AUTH_USER_MODEL = "accounts.User"` — an `AbstractUser`
subclass with roles (`is_dm`, `is_player`, `is_role_admin`), `real_name`,
`phone`, `discord`, `preferred_contact`, plus profile editing, a users list, and
audit logging.

> ⛔️ **Do NOT set `AUTH_USER_MODEL = "tarmar_auth.User"` in tarmar-studio.**
> Changing a live app's `AUTH_USER_MODEL` is a destructive migration — Django
> cannot migrate existing rows from one user model to another; in practice it
> means dropping and recreating the user table (and everything FK'd to it). On a
> deployed app with real accounts that is data loss. This is *the* reason
> tarmar-studio was deliberately left untouched when melee adopted tarmar-auth.

So tarmar-studio **keeps `accounts.User`**. The only thing that can be shared is
the **auth *flow*** (views / forms / templates), which is user-model-agnostic.

**Also be honest about value:** tarmar-studio's `accounts` app is *richer* than
tarmar-auth (roles, profile fields, user management, audit log). Adopting
tarmar-auth wholesale would be a **downgrade**. Treat this as "share the generic
bits only if you specifically want one codebase for them" — not an obvious win.
**Recommendation: read §3, then decide with Spencer.** The safe default is
Option 0 (don't structurally adopt).

---

## 1. What `tarmar-auth` actually is

Repo: `github.com/smarks/tarmar-auth` (public), sibling checkout at
`~/dev/tarmar-auth`. A small, pure-Django reusable app:

| File | What it provides |
|---|---|
| `tarmar_auth/models.py` | `class User(AbstractUser)` — a **concrete**, minimal user. This is what a *greenfield* project points `AUTH_USER_MODEL` at. |
| `tarmar_auth/forms.py` | `RegisterForm(UserCreationForm)` with `Meta.model = get_user_model()` — **model-agnostic** (it binds to whatever the project's user model is). Fields: `username`, `email`. |
| `tarmar_auth/views.py` | `RegisterView` (creates + logs in, redirects to `settings.LOGIN_REDIRECT_URL`), `ProfileView` (login-required). Login/logout use Django's built-in `LoginView`/`LogoutView`. |
| `tarmar_auth/urls.py` | `app_name = "tarmar_auth"`; routes `login/ logout/ register/ profile/`. |
| `tarmar_auth/templates/tarmar_auth/` | `base.html` (skeleton you override), `login.html`, `register.html`, `profile.html`. |
| `migrations/0001_initial.py` (+ `__init__.py`) | the `User` table migration (only relevant if you adopt the concrete model). |

Key point: **the views and forms never hard-code a user model** — they go
through `get_user_model()` and Django's built-in auth views. So they run fine
against `accounts.User`. The **only** model-coupled piece is the concrete
`tarmar_auth.User`, which tarmar-studio will *not* use.

Install (for any consumer): `pip install -e ../tarmar-auth` locally, or
`tarmar-auth @ git+https://github.com/smarks/tarmar-auth.git@main` in
requirements (matches how melee/hexarena/tarmar-rules are pinned).

---

## 2. Reference: how melee adopted it (the clean, greenfield case)

melee had **no auth and no user model**, so it took the concrete model. This is
the easy path and is here only as a reference — **tarmar-studio cannot do step
(b).**

- (a) `requirements.txt`: add `tarmar-auth @ git+https://…@main`.
- (b) `settings.py`: `AUTH_USER_MODEL = "tarmar_auth.User"`. ← tarmar-studio must NOT do this.
- (c) `INSTALLED_APPS`: `django.contrib.auth`, `contenttypes`, `sessions`,
  `messages`, `tarmar_auth`. (tarmar-studio already has these.)
- (d) `MIDDLEWARE`: session → common → csrf → auth → messages.
- (e) `TEMPLATES` `context_processors`: `request`, `auth`, `messages`.
- (f) `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL`.
- (g) root `urls.py`: `path("accounts/", include("tarmar_auth.urls"))`.
- (h) `python manage.py migrate`.
- (i) template header link gated on `{% if request.user.is_authenticated %}`.
- Project-specific data (melee's saved characters) lives in melee's **own**
  model with a `ForeignKey(settings.AUTH_USER_MODEL, …)` — never inside
  tarmar-auth. (This FK pattern is what tarmar-studio would keep doing too.)

melee's accounts are **optional**: the app is fully usable logged-out; login
just unlocks saving. tarmar-studio's accounts are mandatory, so that part
differs.

---

## 3. Options for tarmar-studio

### Option 0 — Don't structurally adopt; align patterns only (recommended default)

tarmar-studio's `accounts` app already does everything tarmar-auth does and
more. The lowest-risk, highest-honesty choice is to **not** take a code
dependency, and instead just keep the two consistent by convention (URL names,
template block names, redirect behaviour). Zero migration/deploy risk. Pick this
unless Spencer specifically wants a shared dependency.

### Option A — Share the view/form/template layer, keep `accounts.User`

If you want tarmar-studio to *use* tarmar-auth's flow (so the generic
login/register/logout lives in one place):

1. Add the dependency (requirements + `pip`/`uv`).
2. Add `"tarmar_auth"` to `INSTALLED_APPS`. **Do not** change `AUTH_USER_MODEL`.
   tarmar-auth's own `User` model + its `0001_initial` migration will be
   *registered but unused*; to avoid creating a stray `tarmar_auth_user` table,
   either (i) don't worry about it (an empty table is harmless) or (ii) keep
   tarmar_auth out of INSTALLED_APPS and instead `include()` its urls + add its
   template dir to `TEMPLATES['DIRS']` so only the views/templates load, not the
   model/migration. Option (ii) is cleaner for tarmar-studio.
3. Wire only the routes you actually want, e.g. keep tarmar-studio's richer
   register/profile (which capture `real_name`/roles) and borrow only
   `login`/`logout` — or subclass `tarmar_auth.views.RegisterView` to add the
   extra fields. Because the forms use `get_user_model()`, a tarmar-auth
   register against `accounts.User` works but only sets `username`/`email`, so
   you'd **lose** the extra-field capture unless you subclass.
4. Override `templates/tarmar_auth/base.html` (and any of
   `login/register/profile.html`) in tarmar-studio's template dir to match its
   look.

**Honest caveat:** because tarmar-studio's auth is richer, Option A mostly buys
consistency for the *generic* parts and risks regressing the *rich* parts. Only
worth it if the duplication genuinely bothers you.

### Option B — Share a common abstract base user (`AbstractTarmarUser`)

If the goal is "both apps' user models share a base class," tarmar-auth could add
an **abstract** base (it doesn't have one yet):

```python
# tarmar_auth/models.py (would need adding to the library)
class AbstractTarmarUser(AbstractUser):
    class Meta:
        abstract = True
class User(AbstractTarmarUser):   # the concrete one melee uses
    pass
```

Then tarmar-studio changes `class User(AbstractUser)` → `class User(AbstractTarmarUser)`.
**If `AbstractTarmarUser` adds no new fields**, this is a *migration-neutral*
change (Django sees no field changes → `makemigrations` produces nothing, the
live table is untouched). But it buys almost nothing on its own (no shared
behaviour yet), so only do this if you're about to put real shared fields/methods
on the base. Low value today; noted for completeness.

---

## 4. tarmar-studio deploy gotchas (from its own CLAUDE.md — don't skip)

Whatever you do, respect tarmar-studio's house rules:

- **Worktree for commit-producing work** — don't edit the main checkout in place;
  `git worktree add … -b <branch>`, PR, let Spencer merge. Stage explicit files;
  never `git add -A/-u`.
- Provision a fresh worktree with **`uv sync --group cli`** (the `cli` group's
  `rich` is needed or pyright fails on `cli/gm.py`) + `manage.py migrate`, dev
  server on **:8001**, and `SKIP=playwright-e2e` on local commits.
- Task tracking is **GitHub Issues** (`gh issue …`), not `bd`.
- **Deploy is blue-green via GH Actions** and has a known "CI-green-but-deploy-
  fails" trap tied to the `cli` group / `rich` / pyright. Any auth change touches
  login = the most sensitive surface; verify the deploy, not just CI.
- Anything touching `AUTH_USER_MODEL`/migrations on the live DB is **high-risk** —
  see §0. The safe options here (0 and A-via-include) need **no** user-model
  migration.

---

## 5. Verification checklist

- `python manage.py makemigrations --check --dry-run` → **no new migrations**
  (proves you didn't perturb the live user model).
- `python manage.py migrate` applies cleanly; no `accounts`/`tarmar_auth` user
  table surprises.
- Existing users can still log in; profile/roles/audit still work.
- Login → `LOGIN_REDIRECT_URL`, logout, register all behave.
- Full test suite + the e2e (Playwright) login flow.
- Deploy to a non-prod/blue slot and confirm login before promoting.

---

## 6. Recommendation in one line

Default to **Option 0** (keep tarmar-studio's superior `accounts` app, don't take
a dependency). Choose **Option A (include-urls variant)** only if Spencer
explicitly wants the generic login flow centralised, and then keep
tarmar-studio's richer register/profile. Never touch `AUTH_USER_MODEL`.
