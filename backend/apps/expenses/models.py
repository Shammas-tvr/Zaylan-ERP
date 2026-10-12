from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Upper

from apps.core.models import TimeStampedModel


def expense_receipt_path(instance, filename: str) -> str:
    return f"expenses/{instance.organization_id}/{instance.pk}/{filename}"


class ExpenseCategory(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="expense_categories"
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "organization", Upper("code"), name="expenses_category_org_code_unique"
            ),
        ]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return self.name


class RecurringFrequency(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"


class RecurringExpense(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="recurring_expenses"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="recurring_expenses"
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="recurring_expenses"
    )
    expected_amount = models.DecimalField(max_digits=14, decimal_places=2)
    frequency = models.CharField(
        max_length=16, choices=RecurringFrequency.choices, default=RecurringFrequency.MONTHLY
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    due_day = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(28)]
    )
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "is_active", "branch"])]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "id"], name="expenses_recurring_org_id_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.category} @ {self.branch}"


class ExpenseEntryType(models.TextChoices):
    RECURRING = "RECURRING", "Recurring"
    VARIABLE = "VARIABLE", "Variable"


class ExpenseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    PAID = "PAID", "Paid"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
    UPI = "UPI", "UPI"
    CARD = "CARD", "Card"
    CHEQUE = "CHEQUE", "Cheque"
    OTHER = "OTHER", "Other"


class Expense(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="expenses"
    )
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="expenses"
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses"
    )
    recurring_expense = models.ForeignKey(
        RecurringExpense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_expenses",
    )
    entry_type = models.CharField(max_length=16, choices=ExpenseEntryType.choices)
    status = models.CharField(
        max_length=32, choices=ExpenseStatus.choices, default=ExpenseStatus.DRAFT
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    expense_date = models.DateField()
    billing_period = models.CharField(max_length=7, blank=True)  # YYYY-MM
    payment_method = models.CharField(
        max_length=32, choices=PaymentMethod.choices, default=PaymentMethod.OTHER
    )
    description = models.TextField(blank=True)
    receipt = models.FileField(upload_to=expense_receipt_path, blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submitted_expenses",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_expenses",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rejected_expenses",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paid_expenses",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "branch", "status"]),
            models.Index(fields=["organization", "billing_period"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "id"], name="expenses_expense_org_id_unique"
            ),
            models.UniqueConstraint(
                fields=["organization", "branch", "category", "billing_period"],
                condition=Q(entry_type="RECURRING") & ~Q(billing_period=""),
                name="expenses_recurring_period_unique",
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="expenses_expense_amount_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.category} {self.amount} ({self.status})"
