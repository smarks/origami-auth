"""Profile editing and password change/reset (the accounts-polish surface)."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse

from origami_auth.views import password_reset_enabled

User = get_user_model()

PASSWORD = "GalleonMist7q"
NEW_PASSWORD = "HarborLantern4x"


@pytest.fixture
def user() -> "User":
    return User.objects.create_user(
        username="edith", password=PASSWORD, email="edith@example.com"
    )


@pytest.fixture
def logged_in_client(user: "User") -> Client:
    client = Client()
    client.login(username="edith", password=PASSWORD)
    return client


# --- Profile editing -------------------------------------------------------


@pytest.mark.django_db
def test_profile_edit_requires_login(client: Client) -> None:
    response = client.get(reverse("origami_auth:profile_edit"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_profile_edit_form_is_prefilled(logged_in_client: Client) -> None:
    response = logged_in_client.get(reverse("origami_auth:profile_edit"))
    assert response.status_code == 200
    assert b"edith@example.com" in response.content


@pytest.mark.django_db
def test_profile_edit_updates_name_and_email(
    logged_in_client: Client, user: "User"
) -> None:
    response = logged_in_client.post(
        reverse("origami_auth:profile_edit"),
        {
            "real_name": "Edith Wharton",
            "email": "edith@innocence.example.com",
            "phone": "",
            "discord": "",
            "preferred_contact": "",
        },
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("origami_auth:profile")
    user.refresh_from_db()
    assert user.real_name == "Edith Wharton"
    assert user.email == "edith@innocence.example.com"


@pytest.mark.django_db
def test_profile_edit_rejects_bad_email(logged_in_client: Client, user: "User") -> None:
    response = logged_in_client.post(
        reverse("origami_auth:profile_edit"),
        {
            "real_name": "",
            "email": "not-an-email",
            "phone": "",
            "discord": "",
            "preferred_contact": "",
        },
    )
    assert response.status_code == 200  # re-renders with errors
    assert response.context["form"].errors["email"]
    user.refresh_from_db()
    assert user.email == "edith@example.com"


@pytest.mark.django_db
def test_profile_edit_rejects_bad_phone(logged_in_client: Client) -> None:
    response = logged_in_client.post(
        reverse("origami_auth:profile_edit"),
        {
            "real_name": "",
            "email": "",
            "phone": "abc",
            "discord": "",
            "preferred_contact": "",
        },
    )
    assert response.status_code == 200
    assert response.context["form"].errors["phone"]


@pytest.mark.django_db
def test_profile_page_links_to_edit_and_password_change(
    logged_in_client: Client,
) -> None:
    response = logged_in_client.get(reverse("origami_auth:profile"))
    content = response.content.decode()
    assert reverse("origami_auth:profile_edit") in content
    assert reverse("origami_auth:password_change") in content


# --- Password change -------------------------------------------------------


@pytest.mark.django_db
def test_password_change_requires_login(client: Client) -> None:
    response = client.get(reverse("origami_auth:password_change"))
    assert response.status_code == 302
    assert "login" in response["Location"]


@pytest.mark.django_db
def test_password_change_happy_path(logged_in_client: Client) -> None:
    response = logged_in_client.post(
        reverse("origami_auth:password_change"),
        {
            "old_password": PASSWORD,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("origami_auth:password_change_done")
    fresh_client = Client()
    assert fresh_client.login(username="edith", password=NEW_PASSWORD)


@pytest.mark.django_db
def test_password_change_rejects_wrong_old_password(
    logged_in_client: Client,
) -> None:
    response = logged_in_client.post(
        reverse("origami_auth:password_change"),
        {
            "old_password": "wrong-password",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert response.status_code == 200
    assert response.context["form"].errors["old_password"]
    assert Client().login(username="edith", password=PASSWORD)


# --- Password reset (email chain, opt-in) ----------------------------------


def test_password_reset_is_off_by_default(settings) -> None:
    del settings.ORIGAMI_AUTH_ENABLE_PASSWORD_RESET
    assert password_reset_enabled() is False


@pytest.mark.django_db
def test_login_page_shows_forgot_password_link_when_enabled(client: Client) -> None:
    response = client.get(reverse("origami_auth:login"))
    assert reverse("origami_auth:password_reset").encode() in response.content


@pytest.mark.django_db
def test_password_reset_full_chain(user: "User") -> None:
    client = Client()
    response = client.post(
        reverse("origami_auth:password_reset"), {"email": "edith@example.com"}
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("origami_auth:password_reset_done")
    assert len(mail.outbox) == 1
    assert "edith" in mail.outbox[0].body

    reset_link_match = re.search(
        r"(/password/reset/[^/\s]+/[^/\s]+/)", mail.outbox[0].body
    )
    assert reset_link_match, mail.outbox[0].body
    confirm_url = reset_link_match.group(1)

    # Django redirects the tokened URL to a session-backed set-password URL.
    response = client.get(confirm_url)
    assert response.status_code == 302
    set_password_url = response["Location"]

    response = client.post(
        set_password_url,
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("origami_auth:password_reset_complete")
    assert Client().login(username="edith", password=NEW_PASSWORD)


@pytest.mark.django_db
def test_password_reset_for_unknown_email_does_not_leak(client: Client) -> None:
    response = client.post(
        reverse("origami_auth:password_reset"), {"email": "nobody@example.com"}
    )
    # Same redirect as a real address — no account enumeration.
    assert response.status_code == 302
    assert response["Location"] == reverse("origami_auth:password_reset_done")
    assert len(mail.outbox) == 0
