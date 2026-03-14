"""
API Views
=========

Auth endpoints (register, login, refresh, me) and user management.
All views use strict RBAC via the permission classes in ``permissions.py``.
"""

from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.models import User
from .permissions import IsPlatformAdmin, IsOwnerOrAdmin
from .serializers import (
    CleanableTokenObtainPairSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserAdminSerializer,
    UserProfileSerializer,
    UserUpdateSerializer,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Auth Views
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/

    Public endpoint.  Creates a user and returns a JWT pair so the
    frontend can redirect straight to the correct dashboard.
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        # Inject custom claims
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["role_slug"] = user.role_slug
        refresh["full_name"] = user.get_full_name()

        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/v1/auth/login/

    Email + password login returning JWT pair.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["role_slug"] = user.role_slug
        refresh["full_name"] = user.get_full_name()

        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/v1/auth/token/

    Standard simplejwt endpoint with custom claims.
    """
    serializer_class = CleanableTokenObtainPairSerializer


class CustomTokenRefreshView(TokenRefreshView):
    """
    POST /api/v1/auth/token/refresh/

    Standard simplejwt refresh — rotates the refresh token and
    returns a new access token.
    """
    pass


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Blacklists the provided refresh token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/auth/me/   → read profile
    PATCH /api/v1/auth/me/  → update profile
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return UserUpdateSerializer
        return UserProfileSerializer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  User Admin ViewSet
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class UserAdminViewSet(viewsets.ModelViewSet):
    """
    /api/v1/admin/users/

    Full CRUD for Platform Admins only.  Supports filtering by role
    via ``?role=10`` query param.
    """

    serializer_class = UserAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]
    queryset = User.objects.all().order_by("-date_joined")

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        if role is not None:
            qs = qs.filter(role=role)
        return qs

    @action(detail=True, methods=["post"])
    def assign_role(self, request, pk=None):
        """POST /api/v1/admin/users/{id}/assign_role/  {role: 60}"""
        user = self.get_object()
        new_role = request.data.get("role")
        valid_roles = dict(User.ROLES)
        if new_role not in valid_roles:
            return Response(
                {"detail": f"Invalid role. Choose from: {list(valid_roles.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.role = new_role
        if new_role == User.ROLE_PLATFORM_ADMIN:
            user.is_staff = True
            user.is_superuser = True
        user.save(update_fields=["role", "is_staff", "is_superuser"])
        return Response(UserAdminSerializer(user).data)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """POST /api/v1/admin/users/{id}/verify/"""
        user = self.get_object()
        user.is_verified = True
        user.save(update_fields=["is_verified"])
        return Response({"detail": "User verified.", "is_verified": True})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Health Check
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class HealthCheckView(APIView):
    """GET /api/v1/health/ — unauthenticated liveness probe."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok", "version": "1.0.0"})
