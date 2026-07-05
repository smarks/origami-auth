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


@pytest.mark.django_db
def test_dm_cannot_edit_a_privileged_account(client):
    # #260: can_manage_users is (is_role_admin or is_dm), so a DM reaches the admin
    # write endpoint. It must NOT let a DM rewrite a role-admin's (or superuser's)
    # profile — rewriting the email would enable an account-takeover via reset.
    dm = User.objects.create_user(
        username="dm", password="GalleonMist7q", is_dm=True
    )
    role_admin = User.objects.create_user(
        username="boss", password="GalleonMist7q",
        is_role_admin=True, email="boss@origin.test",
    )
    superuser = User.objects.create_superuser(
        username="root", password="GalleonMist7q", email="root@origin.test"
    )
    client.login(username="dm", password="GalleonMist7q")

    for target in (role_admin, superuser):
        url = reverse("origami_auth:user_profile_update_field", args=[target.pk])
        resp = _post_json(client, url, {"field": "email", "value": "pwned@evil.test"})
        assert resp.status_code == 403
        target.refresh_from_db()
        assert target.email != "pwned@evil.test"        # the rewrite was refused

    assert dm  # silence unused


@pytest.mark.django_db
def test_dm_cannot_delete_a_privileged_account(client):
    # #260: the same DM must not delete a role-admin or a superuser.
    User.objects.create_user(username="dm", password="GalleonMist7q", is_dm=True)
    role_admin = User.objects.create_user(
        username="boss", password="GalleonMist7q", is_role_admin=True
    )
    superuser = User.objects.create_superuser(
        username="root", password="GalleonMist7q", email="root@origin.test"
    )
    client.login(username="dm", password="GalleonMist7q")

    for target in (role_admin, superuser):
        url = reverse("origami_auth:delete_user", args=[target.pk])
        assert _post_json(client, url, {}).status_code == 403
        assert User.objects.filter(pk=target.pk).exists()   # still there


@pytest.mark.django_db
def test_role_admin_cannot_edit_or_delete_a_superuser(client):
    # #311: a non-superuser role_admin outranks DMs and plain players, but NOT the
    # site superuser. Flattening role_admin and superuser into one tier let a mere
    # role_admin rewrite a superuser's email (reset takeover) or delete it. The
    # superuser tier is manageable only by another superuser.
    role_admin = User.objects.create_user(
        username="boss", password="GalleonMist7q", is_role_admin=True
    )
    superuser = User.objects.create_superuser(
        username="root", password="GalleonMist7q", email="root@origin.test"
    )
    client.login(username="boss", password="GalleonMist7q")

    edit_url = reverse("origami_auth:user_profile_update_field", args=[superuser.pk])
    resp = _post_json(client, edit_url, {"field": "email", "value": "pwned@evil.test"})
    assert resp.status_code == 403
    superuser.refresh_from_db()
    assert superuser.email != "pwned@evil.test"

    delete_url = reverse("origami_auth:delete_user", args=[superuser.pk])
    assert _post_json(client, delete_url, {}).status_code == 403
    assert User.objects.filter(pk=superuser.pk).exists()
    assert role_admin  # silence unused


@pytest.mark.django_db
def test_superuser_can_manage_another_superuser(client):
    # The tier is not a lockout: a superuser still manages its peers, so the site
    # is never left unable to administer a superuser account (#311). The acting
    # superuser is also a role_admin, since can_manage_users (role_admin or DM) is
    # the gate that even reaches these endpoints.
    actor = User.objects.create_superuser(
        username="root", password="GalleonMist7q", email="root@origin.test"
    )
    actor.is_role_admin = True
    actor.save(update_fields=["is_role_admin"])
    peer = User.objects.create_superuser(
        username="root2", password="GalleonMist7q", email="root2@origin.test"
    )
    client.login(username="root", password="GalleonMist7q")

    edit_url = reverse("origami_auth:user_profile_update_field", args=[peer.pk])
    assert _post_json(
        client, edit_url, {"field": "real_name", "value": "Peer"}).status_code == 200
    peer.refresh_from_db()
    assert peer.real_name == "Peer"


@pytest.mark.django_db
def test_dm_can_still_manage_a_plain_player(client):
    # The fix is scoped: a DM keeps its normal power over ordinary (non-privileged)
    # accounts — it may edit and delete a plain player.
    User.objects.create_user(username="dm", password="GalleonMist7q", is_dm=True)
    player = User.objects.create_user(username="pleb", password="GalleonMist7q")
    client.login(username="dm", password="GalleonMist7q")

    edit_url = reverse("origami_auth:user_profile_update_field", args=[player.pk])
    assert _post_json(
        client, edit_url, {"field": "real_name", "value": "Nobody"}).status_code == 200
    player.refresh_from_db()
    assert player.real_name == "Nobody"

    delete_url = reverse("origami_auth:delete_user", args=[player.pk])
    assert _post_json(client, delete_url, {}).status_code == 200
    assert not User.objects.filter(pk=player.pk).exists()


@pytest.mark.django_db
def test_role_admin_can_still_manage_a_privileged_account(client):
    # A role admin (the app's top admin) keeps power over other privileged accounts.
    User.objects.create_user(
        username="boss", password="GalleonMist7q", is_role_admin=True
    )
    other_admin = User.objects.create_user(
        username="boss2", password="GalleonMist7q",
        is_role_admin=True, email="boss2@origin.test",
    )
    client.login(username="boss", password="GalleonMist7q")

    url = reverse("origami_auth:user_profile_update_field", args=[other_admin.pk])
    resp = _post_json(client, url, {"field": "email", "value": "new@origin.test"})
    assert resp.status_code == 200
    other_admin.refresh_from_db()
    assert other_admin.email == "new@origin.test"
