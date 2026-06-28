"""The rich Tarmar auth surface: roles, profile editing, user admin."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


def _post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


@pytest.mark.django_db
def test_new_user_defaults_to_player_role():
    user = User.objects.create_user(username="newbie", password="GalleonMist7q")
    assert user.is_player is True
    assert user.is_dm is False
    assert user.is_role_admin is False
    assert user.can_manage_users is False


@pytest.mark.django_db
def test_register_captures_profile_fields_and_signs_in():
    resp = client_register()
    assert resp.status_code == 302
    user = User.objects.get(username="alice")
    assert user.real_name == "Alice Liddell"
    assert user.discord == "alice.liddell"


def client_register():
    from django.test import Client

    return Client().post(
        reverse("origami_auth:register"),
        {
            "username": "alice",
            "password1": "swordfish-99",
            "password2": "swordfish-99",
            "real_name": "Alice Liddell",
            "email": "a@example.com",
            "discord": "alice.liddell",
            "preferred_contact": "discord",
        },
    )


@pytest.mark.django_db
def test_user_can_edit_own_profile_field(client):
    User.objects.create_user(username="bob", password="GalleonMist7q")
    client.login(username="bob", password="GalleonMist7q")
    resp = _post_json(
        client, reverse("origami_auth:profile_update_field"),
        {"field": "real_name", "value": "Bob Bobson"},
    )
    assert resp.status_code == 200
    assert User.objects.get(username="bob").real_name == "Bob Bobson"


@pytest.mark.django_db
def test_invalid_phone_is_rejected(client):
    User.objects.create_user(username="bob", password="GalleonMist7q")
    client.login(username="bob", password="GalleonMist7q")
    resp = _post_json(
        client, reverse("origami_auth:profile_update_field"),
        {"field": "phone", "value": "nope"},
    )
    assert resp.status_code == 400
    assert "phone" in json.loads(resp.content)["error"].lower()


@pytest.mark.django_db
def test_non_admin_cannot_change_roles_on_others(client):
    User.objects.create_user(username="bob", password="GalleonMist7q")
    victim = User.objects.create_user(username="vic", password="GalleonMist7q")
    client.login(username="bob", password="GalleonMist7q")
    url = reverse("origami_auth:user_profile_update_field", args=[victim.pk])
    resp = _post_json(client, url, {"field": "is_role_admin", "value": True})
    assert resp.status_code == 403
    victim.refresh_from_db()
    assert victim.is_role_admin is False


@pytest.mark.django_db
def test_admin_can_grant_roles(client):
    admin = User.objects.create_user(
        username="admin", password="GalleonMist7q", is_role_admin=True
    )
    victim = User.objects.create_user(username="vic", password="GalleonMist7q")
    client.login(username="admin", password="GalleonMist7q")
    url = reverse("origami_auth:user_profile_update_field", args=[victim.pk])
    resp = _post_json(client, url, {"field": "is_dm", "value": True})
    assert resp.status_code == 200
    victim.refresh_from_db()
    assert victim.is_dm is True
    assert admin  # silence unused


@pytest.mark.django_db
def test_users_list_requires_admin_or_dm(client):
    User.objects.create_user(username="bob", password="GalleonMist7q")
    client.login(username="bob", password="GalleonMist7q")
    assert client.get(reverse("origami_auth:users_list")).status_code == 403

    User.objects.create_user(
        username="dm", password="GalleonMist7q", is_dm=True
    )
    client.login(username="dm", password="GalleonMist7q")
    assert client.get(reverse("origami_auth:users_list")).status_code == 200


@pytest.mark.django_db
def test_delete_user_blocks_self_and_allows_admin(client):
    admin = User.objects.create_user(
        username="admin", password="GalleonMist7q", is_role_admin=True
    )
    victim = User.objects.create_user(username="vic", password="GalleonMist7q")
    client.login(username="admin", password="GalleonMist7q")

    self_url = reverse("origami_auth:delete_user", args=[admin.pk])
    assert _post_json(client, self_url, {}).status_code == 400  # cannot delete self

    victim_url = reverse("origami_auth:delete_user", args=[victim.pk])
    assert _post_json(client, victim_url, {}).status_code == 200
    assert not User.objects.filter(pk=victim.pk).exists()
