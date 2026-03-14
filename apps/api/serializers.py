"""
API Serializers
===============

Covers authentication (register / login / token), user profile,
and the base patterns every domain serializer will follow.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  JWT Customisation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CleanableTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extend the default JWT payload with role metadata so the frontend
    can route and render without an extra /me request on every load.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        token["role_slug"] = user.role_slug
        token["full_name"] = user.get_full_name()
        if user.company_id:
            token["company_id"] = user.company_id
        return token


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Auth Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RegisterSerializer(serializers.ModelSerializer):
    """
    Self-service registration.  The caller picks a role from the
    allowed public roles; Platform Admin can only be created by
    another Platform Admin through the admin panel.
    """

    password = serializers.CharField(
        write_only=True, validators=[validate_password],
    )
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=[
            (User.ROLE_RESIDENT, "Resident"),
            (User.ROLE_SERVICE_PRO, "Service Pro"),
            (User.ROLE_AGENCY_OWNER, "Agency Owner"),
        ],
        default=User.ROLE_RESIDENT,
    )

    class Meta:
        model = User
        fields = (
            "email", "password", "password_confirm",
            "first_name", "last_name", "phone", "role",
        )

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."},
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            phone=validated_data.get("phone"),
            role=validated_data.get("role", User.ROLE_RESIDENT),
        )


class LoginSerializer(serializers.Serializer):
    """Email + password authentication returning JWT pair."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            email=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError(
                "Invalid credentials or account is inactive.",
            )
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")
        attrs["user"] = user
        return attrs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  User Profile Serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class UserProfileSerializer(serializers.ModelSerializer):
    """Read-only user profile returned by /api/v1/auth/me/."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "uuid", "email", "first_name", "last_name",
            "phone", "role", "role_display",
            "is_verified", "company",
            "image_small", "image_xsmall",
            "date_joined",
        )
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """Allows users to update their own profile fields."""

    class Meta:
        model = User
        fields = (
            "first_name", "last_name", "phone", "description",
            "image", "is_contact_by_sms", "is_contact_by_email",
        )

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UserAdminSerializer(serializers.ModelSerializer):
    """
    Full user representation for Platform Admin endpoints.
    Includes role assignment and verification status.
    """

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "uuid", "email", "first_name", "last_name",
            "phone", "role", "role_display",
            "is_verified", "is_active", "is_staff", "is_superuser",
            "company", "date_joined", "last_login",
        )
        read_only_fields = ("id", "uuid", "date_joined", "last_login")
