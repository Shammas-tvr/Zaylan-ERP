from django.db import models
from django.db.models.functions import Upper

from apps.core.models import TimeStampedModel
from apps.core.validators import validate_timezone


class BranchStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class Branch(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="branches"
    )
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=150)
    status = models.CharField(
        max_length=16, choices=BranchStatus.choices, default=BranchStatus.ACTIVE
    )
    # Blank means the branch inherits the organization timezone.
    timezone = models.CharField(max_length=64, blank=True, validators=[validate_timezone])
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=16, blank=True)
    login_user = models.OneToOneField(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="branch_login",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "organization", Upper("code"), name="branches_branch_org_code_unique"
            ),
            models.UniqueConstraint(
                fields=["organization", "id"], name="branches_branch_org_id_unique"
            ),
        ]
        indexes = [models.Index(fields=["organization", "status"])]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class MembershipBranchAccess(TimeStampedModel):
    """Grants a membership access to a branch; tenant consistency is enforced by composite FKs."""

    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="+"
    )
    membership = models.ForeignKey(
        "tenancy.OrganizationMembership", on_delete=models.CASCADE, related_name="branch_access"
    )
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="member_access")
    granted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "branch"], name="branches_access_membership_branch_unique"
            ),
        ]
        indexes = [models.Index(fields=["organization", "branch"])]
