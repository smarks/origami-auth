from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
    ProfileEditView,
    ProfileView,
    RegisterView,
    UsersListView,
    delete_user,
    password_reset_enabled,
    profile_update_field,
)

app_name = "origami_auth"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/edit/", ProfileEditView.as_view(), name="profile_edit"),
    path("profile/<int:user_id>/", ProfileView.as_view(), name="user_profile"),
    path("profile/update-field/", profile_update_field, name="profile_update_field"),
    path(
        "profile/<int:user_id>/update-field/",
        profile_update_field,
        name="user_profile_update_field",
    ),
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path(
        "password/change/done/",
        PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("users/", UsersListView.as_view(), name="users_list"),
    path("users/<int:user_id>/delete/", delete_user, name="delete_user"),
]

# The email reset chain is opt-in: it only works when the consuming project has
# outbound email configured, so projects without SMTP (and therefore without
# ORIGAMI_AUTH_ENABLE_PASSWORD_RESET = True) get no reset routes at all rather
# than a form whose emails silently go nowhere.
if password_reset_enabled():
    urlpatterns += [
        path("password/reset/", PasswordResetView.as_view(), name="password_reset"),
        path(
            "password/reset/sent/",
            PasswordResetDoneView.as_view(),
            name="password_reset_done",
        ),
        path(
            "password/reset/<uidb64>/<token>/",
            PasswordResetConfirmView.as_view(),
            name="password_reset_confirm",
        ),
        path(
            "password/reset/done/",
            PasswordResetCompleteView.as_view(),
            name="password_reset_complete",
        ),
    ]
