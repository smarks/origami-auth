"""The shared login flow: register signs you in; profile needs auth."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
def test_register_creates_a_user_and_signs_them_in(client):
    resp = client.post(reverse("origami_auth:register"), {
        "username": "alice", "email": "a@example.com",
        "password1": "swordfish-99", "password2": "swordfish-99"})
    assert resp.status_code == 302  # -> profile
    assert get_user_model().objects.filter(username="alice").exists()
    profile = client.get(reverse("origami_auth:profile"))
    assert profile.status_code == 200
    assert b"alice" in profile.content


@pytest.mark.django_db
def test_profile_requires_login(client, django_user_model):
    django_user_model.objects.create_user(username="bob", password="hunter2-pass")
    assert client.get(reverse("origami_auth:profile")).status_code == 302  # to login
    assert client.login(username="bob", password="hunter2-pass")
    assert client.get(reverse("origami_auth:profile")).status_code == 200


@pytest.mark.django_db
def test_login_page_renders(client):
    resp = client.get(reverse("origami_auth:login"))
    assert resp.status_code == 200
    assert b"Log in" in resp.content
