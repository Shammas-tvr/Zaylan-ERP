import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.validators import normalize_email


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        username = extra_fields.pop("username", None)
        user = self.model(
            email=normalize_email(email),
            username=(username or "").strip() or None,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        value = (username or "").strip()
        if "@" in value:
            return self.get(email=normalize_email(value))
        return self.get(username__iexact=value)


class User(AbstractBaseUser, PermissionsMixin):
    """A global identity. Tenant access is granted only through organization memberships."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    # Optional login name for brand staff (Brand Admins typically use email).
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    # Grants Django admin access only; it never implies platform or tenant permissions.
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.UniqueConstraint(
                Lower("username"),
                condition=~models.Q(username=None) & ~models.Q(username=""),
                name="accounts_user_username_ci_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.username or self.email

    def save(self, *args, **kwargs):
        self.email = normalize_email(self.email)
        if self.username is not None:
            self.username = self.username.strip() or None
        super().save(*args, **kwargs)


class PasswordResetOTP(models.Model):
    """One-time code emailed to Brand Admins for password reset."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_otps")
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"OTP for {self.user_id}"
