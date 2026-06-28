# Integrating `origami-auth` into tarmar-studio — handoff

_Written for the tarmar-studio Claude. Context: `origami-auth` is the reusable
Django login app that **melee** already uses; the question is whether/how
**tarmar-studio** should share it._

---

## §-1. Treat origami-auth (and origami-common) as versioned libraries — read first

These packages are **libraries**. Consume them as **pinned, non-editable git
dependencies**, each project in its **own environment**. Never `@main`, never
`pip install -e`.

**Why this is not optional.** melee and tarmar-studio can share one global
Python. An editable install (`pip install -e ../origami-auth`) makes a consumer
ride the *live working tree*, so one project's in-progress edits leak into the
others. This already bit us: while origami-auth was being rebuilt into the rich
shared library, melee — which had it editable-installed — crashed with
`ModuleNotFoundError: No module named 'origami_common'` the moment the new import
landed in the working tree. The fix was to pin melee to a release tag and install
it non-editable.

**The version situation (it has shifted — mind the divergence):**

| Version | What it is | Who uses it |
|---|---|---|
| **`v0.1.0`** (commit `64635899`) | the **old, minimal** `User(AbstractUser)` + register/login/logout/profile app | **melee** pins this today |
| the working tree / future **`main`** | the **rich** shared library — `AbstractOrigamiUser` (studio-grade user: roles + profile fields), split `base.py`/`models.py`, full views, and a new dependency on the sibling package **`origami-common`** | tarmar-studio (target), not yet tagged |

So:

1. **tarmar-studio consumes both `origami-auth` and `origami-common` as pinned,
   non-editable deps** (`@vX.Y.Z`), installed into **its own environment**
   (venv / project-local). Never `@main`, never `-e`. Same rule for melee.
2. **When the rich origami-auth is committed/pushed, tag it `v0.2.0`** — and tag
   **`origami-common`** too (it's a real dependency; pin it by tag as well).
   Don't let consumers pick up the rich version implicitly via `@main`.
3. **melee's eventual move to the rich version is a deliberate `v0.1.0 → v0.2.0`
   bump** (the planned additive-migration step in §3 Option B), reviewed and
   tested — never an accident from `@main` or a stray editable install.
4. **Developing origami-auth itself** is the *one* place `-e` is fine — but only
   inside origami-auth's **own** isolated venv. Cut a release + tag, then bump each
   consumer's pin. Never editable-install it into an env that other projects use.

Recovery, if a shared env gets clobbered back to an editable/WIP install:

```bash
pip install --force-reinstall --no-deps \
  "origami-auth @ git+https://github.com/smarks/origami-auth.git@v0.1.0"   # or the consumer's pinned tag
```

---

## 0. The one constraint that drives every decision

**tarmar-studio is already deployed with its own custom user model.** Its
`settings.py` has `AUTH_USER_MODEL = "accounts.User"` — an `AbstractUser`
subclass with roles (`is_dm`, `is_player`, `is_role_admin`), `real_name`,
`phone`, `discord`, `preferred_contact`, plus profile editing, a users list, and
audit logging.

> ⛔️ **Do NOT set `AUTH_USER_MODEL = "origami_auth.User"` in tarmar-studio.**
> Changing a live app's `AUTH_USER_MODEL` is a destructive migration — Django
> cannot migrate existing rows from one user model to another; in practice it
> means dropping and recreating the user table (and everything FK'd to it). On a
> deployed app with real accounts that is data loss. This is *the* reason
> tarmar-studio was deliberately left untouched when melee adopted origami-auth.

So tarmar-studio **keeps `accounts.User`**. The only thing that can be shared is
the **auth *flow*** (views / forms / templates), which is user-model-agnostic.

**Also be honest about value:** tarmar-studio's `accounts` app is *richer* than
origami-auth (roles, profile fields, user management, audit log). Adopting
origami-auth wholesale would be a **downgrade**. Treat this as "share the generic
bits only if you specifically want one codebase for them" — not an obvious win.
**Recommendation: read §3, then decide with Spencer.** The safe default is
Option 0 (don't structurally adopt).

---

## 1. What `origami-auth` actually is

Repo: `github.com/smarks/origami-auth` (public), sibling checkout at
`~/dev/origami-auth`. A small, pure-Django reusable app:

| File | What it provides |
|---|---|
| `origami_auth/models.py` | `class User(AbstractUser)` — a **concrete**, minimal user. This is what a *greenfield* project points `AUTH_USER_MODEL` at. |
| `origami_auth/forms.py` | `RegisterForm(UserCreationForm)` with `Meta.model = get_user_model()` — **model-agnostic** (it binds to whatever the project's user model is). Fields: `username`, `email`. |
| `origami_auth/views.py` | `RegisterView` (creates + logs in, redirects to `settings.LOGIN_REDIRECT_URL`), `ProfileView` (login-required). Login/logout use Django's built-in `LoginView`/`LogoutView`. |
| `origami_auth/urls.py` | `app_name = "origami_auth"`; routes `login/ logout/ register/ profile/`. |
| `origami_auth/templates/origami_auth/` | `base.html` (skeleton you override), `login.html`, `register.html`, `profile.html`. |
| `migrations/0001_initial.py` (+ `__init__.py`) | the `User` table migration (only relevant if you adopt the concrete model). |

Key point: **the views and forms never hard-code a user model** — they go
through `get_user_model()` and Django's built-in auth views. So they run fine
against `accounts.User`. The **only** model-coupled piece is the concrete
`origami_auth.User`, which tarmar-studio will *not* use.

Install (for any consumer): `pip install -e ../origami-auth` locally, or
`origami-auth @ git+https://github.com/smarks/origami-auth.git@main` in
requirements (matches how melee/hexarena/tarmar-rules are pinned).

---

## 2. Reference: how melee adopted it (the clean, greenfield case)

melee had **no auth and no user model**, so it took the concrete model. This is
the easy path and is here only as a reference — **tarmar-studio cannot do step
(b).**

- (a) `requirements.txt`: add `origami-auth @ git+https://…@main`.
- (b) `settings.py`: `AUTH_USER_MODEL = "origami_auth.User"`. ← tarmar-studio must NOT do this.
- (c) `INSTALLED_APPS`: `django.contrib.auth`, `contenttypes`, `sessions`,
  `messages`, `origami_auth`. (tarmar-studio already has these.)
- (d) `MIDDLEWARE`: session → common → csrf → auth → messages.
- (e) `TEMPLATES` `context_processors`: `request`, `auth`, `messages`.
- (f) `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL`.
- (g) root `urls.py`: `path("accounts/", include("origami_auth.urls"))`.
- (h) `python manage.py migrate`.
- (i) template header link gated on `{% if request.user.is_authenticated %}`.
- Project-specific data (melee's saved characters) lives in melee's **own**
  model with a `ForeignKey(settings.AUTH_USER_MODEL, …)` — never inside
  origami-auth. (This FK pattern is what tarmar-studio would keep doing too.)

melee's accounts are **optional**: the app is fully usable logged-out; login
just unlocks saving. tarmar-studio's accounts are mandatory, so that part
differs.

---

## 3. Options for tarmar-studio

### Option 0 — Don't structurally adopt; align patterns only (recommended default)

tarmar-studio's `accounts` app already does everything origami-auth does and
more. The lowest-risk, highest-honesty choice is to **not** take a code
dependency, and instead just keep the two consistent by convention (URL names,
template block names, redirect behaviour). Zero migration/deploy risk. Pick this
unless Spencer specifically wants a shared dependency.

### Option A — Share the view/form/template layer, keep `accounts.User`

If you want tarmar-studio to *use* origami-auth's flow (so the generic
login/register/logout lives in one place):

1. Add the dependency (requirements + `pip`/`uv`).
2. Add `"origami_auth"` to `INSTALLED_APPS`. **Do not** change `AUTH_USER_MODEL`.
   origami-auth's own `User` model + its `0001_initial` migration will be
   *registered but unused*; to avoid creating a stray `origami_auth_user` table,
   either (i) don't worry about it (an empty table is harmless) or (ii) keep
   origami_auth out of INSTALLED_APPS and instead `include()` its urls + add its
   template dir to `TEMPLATES['DIRS']` so only the views/templates load, not the
   model/migration. Option (ii) is cleaner for tarmar-studio.
3. Wire only the routes you actually want, e.g. keep tarmar-studio's richer
   register/profile (which capture `real_name`/roles) and borrow only
   `login`/`logout` — or subclass `origami_auth.views.RegisterView` to add the
   extra fields. Because the forms use `get_user_model()`, a origami-auth
   register against `accounts.User` works but only sets `username`/`email`, so
   you'd **lose** the extra-field capture unless you subclass.
4. Override `templates/origami_auth/base.html` (and any of
   `login/register/profile.html`) in tarmar-studio's template dir to match its
   look.

**Honest caveat:** because tarmar-studio's auth is richer, Option A mostly buys
consistency for the *generic* parts and risks regressing the *rich* parts. Only
worth it if the duplication genuinely bothers you.

### Option B — Share a common abstract base user (`AbstractOrigamiUser`)

If the goal is "both apps' user models share a base class," origami-auth could add
an **abstract** base (it doesn't have one yet):

```python
# origami_auth/models.py (would need adding to the library)
class AbstractOrigamiUser(AbstractUser):
    class Meta:
        abstract = True
class User(AbstractOrigamiUser):   # the concrete one melee uses
    pass
```

Then tarmar-studio changes `class User(AbstractUser)` → `class User(AbstractOrigamiUser)`.
**If `AbstractOrigamiUser` adds no new fields**, this is a *migration-neutral*
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
- `python manage.py migrate` applies cleanly; no `accounts`/`origami_auth` user
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
