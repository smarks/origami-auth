import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .base import CONTACT_CHOICES, DISCORD_VALIDATOR, PHONE_VALIDATOR

# Username must be 1-25 alphanumeric characters, underscores, or hyphens
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,25}$")


class RegistrationForm(UserCreationForm):
    """Rich registration: username/password plus optional Tarmar profile fields.

    Binds to whatever user model the project configures (``get_user_model()``),
    so it works against this library's concrete ``User`` or a consuming app's own
    ``AbstractTarmarUser`` subclass.
    """

    real_name = forms.CharField(max_length=100, required=False)
    email = forms.EmailField(max_length=254, required=False)
    phone = forms.CharField(max_length=20, required=False, validators=[PHONE_VALIDATOR])
    discord = forms.CharField(
        max_length=50, required=False, validators=[DISCORD_VALIDATOR]
    )
    preferred_contact = forms.ChoiceField(
        choices=[("", "---")] + CONTACT_CHOICES,
        required=False,
    )

    class Meta:
        model = get_user_model()
        fields = [
            "username",
            "password1",
            "password2",
            "real_name",
            "email",
            "phone",
            "discord",
            "preferred_contact",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].max_length = 25
        self.fields["username"].help_text = "Required. 25 characters or fewer."
        # Remove password help text (validation done in clean methods)
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""
        # Set maxlength on password input widgets
        self.fields["password1"].widget.attrs["maxlength"] = 128
        self.fields["password2"].widget.attrs["maxlength"] = 128

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username:
            if len(username) > 25:
                raise forms.ValidationError("Username must be 25 characters or fewer.")
            if not USERNAME_REGEX.match(username):
                raise forms.ValidationError(
                    "Username must contain only letters, numbers, underscores, or hyphens."
                )
        return username

    def _validate_password_length(self, password):
        """Validate password is not too long."""
        if password and len(password) > 128:
            raise forms.ValidationError("Password must be 128 characters or fewer.")
        return password

    def clean_password1(self):
        return self._validate_password_length(self.cleaned_data.get("password1"))

    def clean_password2(self):
        return self._validate_password_length(self.cleaned_data.get("password2"))
