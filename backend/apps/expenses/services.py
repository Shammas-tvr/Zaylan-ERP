"""Expense lifecycle: categories, recurring templates, submit/approve/reject/pay, generation."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError
from apps.notifications.models import NotificationType
from apps.notifications.services import (
    brand_admin_users,
    get_or_create_settings,
    notify_users,
    send_expense_email,
)

from .models import (
    Expense,
    ExpenseCategory,
    ExpenseEntryType,
    ExpenseStatus,
    RecurringExpense,
    RecurringFrequency,
)


def _require_branch(ctx, branch_id):
    from apps.branches.models import Branch

    branch = Branch.objects.filter(organization=ctx.organization, pk=branch_id).first()
    if branch is None:
        raise ValidationError({"branch_id": ["Unknown branch."]})
    return branch


def _require_category(ctx, category_id) -> ExpenseCategory:
    category = ExpenseCategory.objects.filter(organization=ctx.organization, pk=category_id).first()
    if category is None:
        raise ValidationError({"category_id": ["Unknown category."]})
    return category


@transaction.atomic
def create_category(ctx, data: dict, *, request=None) -> ExpenseCategory:
    category = ExpenseCategory(
        organization=ctx.organization,
        code=data["code"].strip().upper(),
        name=data["name"].strip(),
        is_active=data.get("is_active", True),
    )
    try:
        category.full_clean()
        category.save()
    except IntegrityError as exc:
        raise ConflictError("A category with this code already exists.") from exc
    record_event(
        action="expenses.category_created",
        actor=ctx.user,
        organization=ctx.organization,
        target=category,
        metadata={"code": category.code, "name": category.name},
        request=request,
    )
    return category


@transaction.atomic
def update_category(ctx, category: ExpenseCategory, data: dict, *, request=None) -> ExpenseCategory:
    category = ExpenseCategory.objects.select_for_update().get(
        pk=category.pk, organization=ctx.organization
    )
    changed = {}
    for field in ("name", "is_active"):
        if field in data and getattr(category, field) != data[field]:
            changed[field] = [getattr(category, field), data[field]]
            setattr(category, field, data[field])
    if "code" in data:
        code = data["code"].strip().upper()
        if category.code != code:
            changed["code"] = [category.code, code]
            category.code = code
    if changed:
        try:
            category.full_clean()
            category.save()
        except IntegrityError as exc:
            raise ConflictError("A category with this code already exists.") from exc
        record_event(
            action="expenses.category_updated",
            actor=ctx.user,
            organization=ctx.organization,
            target=category,
            metadata=changed,
            request=request,
        )
    return category


@transaction.atomic
def create_recurring(ctx, data: dict, *, request=None) -> RecurringExpense:
    branch = _require_branch(ctx, data["branch_id"])
    category = _require_category(ctx, data["category_id"])
    if not category.is_active:
        raise ValidationError({"category_id": ["Category is inactive."]})
    end_date = data.get("end_date")
    if end_date and end_date < data["start_date"]:
        raise ValidationError({"end_date": ["End date must be on or after start date."]})
    row = RecurringExpense(
        organization=ctx.organization,
        branch=branch,
        category=category,
        expected_amount=data["expected_amount"],
        frequency=data.get("frequency", RecurringFrequency.MONTHLY),
        start_date=data["start_date"],
        end_date=end_date,
        due_day=data.get("due_day", 1),
        description=data.get("description", ""),
        is_active=data.get("is_active", True),
    )
    row.full_clean()
    row.save()
    record_event(
        action="expenses.recurring_created",
        actor=ctx.user,
        organization=ctx.organization,
        branch=branch,
        target=row,
        metadata={"category": category.code, "amount": str(row.expected_amount)},
        request=request,
    )
    return row


@transaction.atomic
def update_recurring(ctx, row: RecurringExpense, data: dict, *, request=None) -> RecurringExpense:
    row = RecurringExpense.objects.select_for_update().get(pk=row.pk, organization=ctx.organization)
    changed = {}
    if "branch_id" in data:
        branch = _require_branch(ctx, data["branch_id"])
        if row.branch_id != branch.pk:
            changed["branch_id"] = [str(row.branch_id), str(branch.pk)]
            row.branch = branch
    if "category_id" in data:
        category = _require_category(ctx, data["category_id"])
        if row.category_id != category.pk:
            changed["category_id"] = [str(row.category_id), str(category.pk)]
            row.category = category
    for field in (
        "expected_amount",
        "frequency",
        "start_date",
        "end_date",
        "due_day",
        "description",
        "is_active",
    ):
        if field in data and getattr(row, field) != data[field]:
            changed[field] = [str(getattr(row, field)), str(data[field])]
            setattr(row, field, data[field])
    if row.end_date and row.end_date < row.start_date:
        raise ValidationError({"end_date": ["End date must be on or after start date."]})
    if changed:
        row.full_clean()
        row.save()
        record_event(
            action="expenses.recurring_updated",
            actor=ctx.user,
            organization=ctx.organization,
            branch=row.branch,
            target=row,
            metadata=changed,
            request=request,
        )
    return row


def _billing_period(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


@transaction.atomic
def create_expense(ctx, data: dict, *, request=None) -> Expense:
    branch = _require_branch(ctx, data["branch_id"])
    if "expenses.submit" in ctx.tenant_permissions:
        pass
    elif branch.pk in ctx.branch_ids_with("expenses.submit"):
        pass
    else:
        raise PermissionDenied("You cannot submit expenses for this branch.")
    category = _require_category(ctx, data["category_id"])
    expense_date = data["expense_date"]
    expense = Expense(
        organization=ctx.organization,
        branch=branch,
        category=category,
        entry_type=ExpenseEntryType.VARIABLE,
        status=ExpenseStatus.DRAFT,
        amount=data["amount"],
        expense_date=expense_date,
        billing_period=data.get("billing_period") or _billing_period(expense_date),
        payment_method=data.get("payment_method", "OTHER"),
        description=data.get("description", ""),
        submitted_by=ctx.user,
    )
    if data.get("receipt") is not None:
        expense.receipt = data["receipt"]
    expense.full_clean()
    expense.save()
    record_event(
        action="expenses.created",
        actor=ctx.user,
        organization=ctx.organization,
        branch=branch,
        target=expense,
        metadata={"amount": str(expense.amount), "status": expense.status},
        request=request,
    )
    return expense


@transaction.atomic
def update_draft(ctx, expense: Expense, data: dict, *, request=None) -> Expense:
    expense = Expense.objects.select_for_update().get(pk=expense.pk, organization=ctx.organization)
    if expense.status != ExpenseStatus.DRAFT:
        raise BusinessRuleViolation("Only draft expenses can be edited.")
    if expense.submitted_by_id and expense.submitted_by_id != ctx.user.pk:
        if not ctx.has_permission("expenses.configure"):
            raise PermissionDenied("You can only edit your own drafts.")
    changed = {}
    if "branch_id" in data:
        branch = _require_branch(ctx, data["branch_id"])
        expense.branch = branch
        changed["branch_id"] = str(branch.pk)
    if "category_id" in data:
        expense.category = _require_category(ctx, data["category_id"])
        changed["category_id"] = str(expense.category_id)
    for field in ("amount", "expense_date", "payment_method", "description", "billing_period"):
        if field in data and getattr(expense, field) != data[field]:
            changed[field] = [str(getattr(expense, field)), str(data[field])]
            setattr(expense, field, data[field])
    if "receipt" in data and data["receipt"] is not None:
        expense.receipt = data["receipt"]
        changed["receipt"] = True
    if changed:
        expense.full_clean()
        expense.save()
        record_event(
            action="expenses.updated",
            actor=ctx.user,
            organization=ctx.organization,
            branch=expense.branch,
            target=expense,
            metadata=changed,
            request=request,
        )
    return expense


def _expense_review_url(expense: Expense) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/expenses/{expense.pk}"


def _notify_submitted(expense: Expense) -> None:
    admins = brand_admin_users(expense.organization)
    title = f"Expense pending: {expense.category.name}"
    body = (
        f"{expense.branch.name} · {expense.amount} · submitted by "
        f"{getattr(expense.submitted_by, 'full_name', '') or expense.submitted_by}"
    )
    notify_users(
        organization=expense.organization,
        users=admins,
        notification_type=NotificationType.EXPENSE_SUBMITTED,
        title=title,
        body=body,
        link_path=f"/expenses/{expense.pk}",
        expense_id=expense.pk,
    )
    settings_row = get_or_create_settings(expense.organization)
    recipients = settings_row.recipient_emails()
    if not recipients:
        recipients = [u.email for u in admins if u.email]
    subject = f"[{expense.organization.name}] Expense awaiting approval"
    message = (
        f"Brand: {expense.organization.name}\n"
        f"Branch: {expense.branch.name}\n"
        f"Category: {expense.category.name}\n"
        f"Amount: {expense.amount}\n"
        f"Date: {expense.expense_date}\n"
        f"Submitter: {getattr(expense.submitted_by, 'email', '')}\n"
        f"Review: {_expense_review_url(expense)}\n"
    )
    send_expense_email(
        organization=expense.organization,
        expense=expense,
        event="expense_submitted",
        recipients=recipients,
        subject=subject,
        message=message,
    )


@transaction.atomic
def submit_expense(ctx, expense: Expense, *, request=None) -> Expense:
    expense = Expense.objects.select_for_update().get(pk=expense.pk, organization=ctx.organization)
    if expense.status not in (ExpenseStatus.DRAFT, ExpenseStatus.REJECTED):
        raise BusinessRuleViolation("Only draft or rejected expenses can be submitted.")
    if not ctx.has_permission_anywhere("expenses.submit"):
        raise PermissionDenied()
    if (
        "expenses.submit" not in ctx.tenant_permissions
        and expense.branch_id not in ctx.branch_ids_with("expenses.submit")
    ):
        raise PermissionDenied("You cannot submit expenses for this branch.")
    expense.status = ExpenseStatus.PENDING_APPROVAL
    expense.submitted_by = ctx.user
    expense.submitted_at = timezone.now()
    expense.rejection_reason = ""
    expense.rejected_at = None
    expense.rejected_by = None
    expense.save()
    record_event(
        action="expenses.submitted",
        actor=ctx.user,
        organization=ctx.organization,
        branch=expense.branch,
        target=expense,
        metadata={"amount": str(expense.amount)},
        request=request,
    )
    _notify_submitted(expense)
    return expense


@transaction.atomic
def approve_expense(ctx, expense: Expense, *, request=None) -> Expense:
    expense = Expense.objects.select_for_update().get(pk=expense.pk, organization=ctx.organization)
    if expense.status != ExpenseStatus.PENDING_APPROVAL:
        raise BusinessRuleViolation("Only pending expenses can be approved.")
    if expense.submitted_by_id == ctx.user.pk:
        raise PermissionDenied("You cannot approve an expense you submitted.")
    expense.status = ExpenseStatus.APPROVED
    expense.approved_by = ctx.user
    expense.approved_at = timezone.now()
    expense.rejection_reason = ""
    expense.rejected_at = None
    expense.rejected_by = None
    expense.save()
    record_event(
        action="expenses.approved",
        actor=ctx.user,
        organization=ctx.organization,
        branch=expense.branch,
        target=expense,
        metadata={"amount": str(expense.amount)},
        request=request,
    )

    if expense.submitted_by_id:
        notify_users(
            organization=expense.organization,
            users=[expense.submitted_by],
            notification_type=NotificationType.EXPENSE_APPROVED,
            title=f"Expense approved: {expense.category.name}",
            body=f"{expense.branch.name} · {expense.amount}",
            link_path=f"/expenses/{expense.pk}",
            expense_id=expense.pk,
        )
        if expense.submitted_by.email:
            send_expense_email(
                organization=expense.organization,
                expense=expense,
                event="expense_approved",
                recipients=[expense.submitted_by.email],
                subject=f"[{expense.organization.name}] Expense approved",
                message=(
                    f"Your expense for {expense.category.name} ({expense.amount}) was approved.\n"
                    f"{_expense_review_url(expense)}\n"
                ),
            )
    return expense


@transaction.atomic
def reject_expense(ctx, expense: Expense, *, reason: str, request=None) -> Expense:
    expense = Expense.objects.select_for_update().get(pk=expense.pk, organization=ctx.organization)
    if expense.status != ExpenseStatus.PENDING_APPROVAL:
        raise BusinessRuleViolation("Only pending expenses can be rejected.")
    if expense.submitted_by_id == ctx.user.pk:
        raise PermissionDenied("You cannot reject an expense you submitted.")
    if not reason or not reason.strip():
        raise ValidationError({"reason": ["A rejection reason is required."]})
    expense.status = ExpenseStatus.REJECTED
    expense.rejected_by = ctx.user
    expense.rejected_at = timezone.now()
    expense.rejection_reason = reason.strip()
    expense.approved_by = None
    expense.approved_at = None
    expense.save()
    record_event(
        action="expenses.rejected",
        actor=ctx.user,
        organization=ctx.organization,
        branch=expense.branch,
        target=expense,
        metadata={"reason": expense.rejection_reason},
        request=request,
    )

    if expense.submitted_by_id:
        notify_users(
            organization=expense.organization,
            users=[expense.submitted_by],
            notification_type=NotificationType.EXPENSE_REJECTED,
            title=f"Expense rejected: {expense.category.name}",
            body=expense.rejection_reason,
            link_path=f"/expenses/{expense.pk}",
            expense_id=expense.pk,
        )
        if expense.submitted_by.email:
            send_expense_email(
                organization=expense.organization,
                expense=expense,
                event="expense_rejected",
                recipients=[expense.submitted_by.email],
                subject=f"[{expense.organization.name}] Expense rejected",
                message=(
                    f"Your expense for {expense.category.name} ({expense.amount}) was rejected.\n"
                    f"Reason: {expense.rejection_reason}\n"
                    f"{_expense_review_url(expense)}\n"
                ),
            )
    return expense


@transaction.atomic
def mark_paid(ctx, expense: Expense, *, payment_reference: str = "", request=None) -> Expense:
    expense = Expense.objects.select_for_update().get(pk=expense.pk, organization=ctx.organization)
    if expense.status != ExpenseStatus.APPROVED:
        raise BusinessRuleViolation("Only approved expenses can be marked paid.")
    expense.status = ExpenseStatus.PAID
    expense.paid_by = ctx.user
    expense.paid_at = timezone.now()
    expense.payment_reference = payment_reference or ""
    expense.save()
    record_event(
        action="expenses.paid",
        actor=ctx.user,
        organization=ctx.organization,
        branch=expense.branch,
        target=expense,
        metadata={"payment_reference": expense.payment_reference},
        request=request,
    )
    return expense


def generate_recurring_for_period(*, as_of: date | None = None) -> dict:
    """
    Create PENDING_APPROVAL expenses for active monthly recurring templates.
    Never auto-approves or marks paid. Idempotent per branch+category+period.
    """
    as_of = as_of or timezone.localdate()
    period = _billing_period(as_of)
    created = 0
    skipped = 0
    templates = RecurringExpense.objects.filter(is_active=True).select_related(
        "organization", "branch", "category"
    )
    for template in templates:
        if template.start_date > as_of:
            skipped += 1
            continue
        if template.end_date and template.end_date < as_of:
            skipped += 1
            continue
        # Due day gate: generate on/after due day within the month.
        last_day = monthrange(as_of.year, as_of.month)[1]
        due_day = min(template.due_day, last_day)
        if as_of.day < due_day:
            skipped += 1
            continue
        if Expense.objects.filter(
            organization=template.organization,
            branch=template.branch,
            category=template.category,
            billing_period=period,
            entry_type=ExpenseEntryType.RECURRING,
        ).exists():
            skipped += 1
            continue
        expense_date = date(as_of.year, as_of.month, due_day)
        try:
            with transaction.atomic():
                expense = Expense(
                    organization=template.organization,
                    branch=template.branch,
                    category=template.category,
                    recurring_expense=template,
                    entry_type=ExpenseEntryType.RECURRING,
                    status=ExpenseStatus.PENDING_APPROVAL,
                    amount=Decimal(template.expected_amount),
                    expense_date=expense_date,
                    billing_period=period,
                    payment_method="OTHER",
                    description=template.description
                    or f"Recurring {template.category.name} for {period}",
                    submitted_at=timezone.now(),
                )
                expense.full_clean()
                expense.save()
                record_event(
                    action="expenses.recurring_generated",
                    actor=None,
                    organization=template.organization,
                    branch=template.branch,
                    target=expense,
                    metadata={"period": period, "recurring_id": str(template.pk)},
                )
                created += 1
            _notify_submitted(expense)
        except IntegrityError:
            skipped += 1
    return {"created": created, "skipped": skipped, "period": period}


def send_pending_reminders(*, now=None) -> dict:
    """Send reminder emails for expenses still pending past configured intervals."""
    now = now or timezone.now()
    sent = 0
    skipped = 0
    pending = Expense.objects.filter(status=ExpenseStatus.PENDING_APPROVAL).select_related(
        "organization", "branch", "category", "submitted_by"
    )
    for expense in pending:
        settings_row = get_or_create_settings(expense.organization)
        if not settings_row.reminders_enabled:
            skipped += 1
            continue
        submitted_at = expense.submitted_at or expense.created_at
        age_hours = (now - submitted_at).total_seconds() / 3600
        recipients = settings_row.recipient_emails()
        if not recipients:
            recipients = [u.email for u in brand_admin_users(expense.organization) if u.email]
        for hours in settings_row.reminder_hours():
            if age_hours < hours:
                continue
            interval_key = f"{hours}h"
            from apps.notifications.models import EmailDeliveryStatus

            logs = send_expense_email(
                organization=expense.organization,
                expense=expense,
                event="expense_reminder",
                recipients=recipients,
                subject=f"[{expense.organization.name}] Reminder: expense awaiting approval",
                message=(
                    f"Expense still pending after {hours} hours.\n"
                    f"Branch: {expense.branch.name}\n"
                    f"Category: {expense.category.name}\n"
                    f"Amount: {expense.amount}\n"
                    f"{_expense_review_url(expense)}\n"
                ),
                interval_key=interval_key,
            )
            newly = sum(1 for log in logs if log.status == EmailDeliveryStatus.SENT)
            if newly:
                sent += newly
                notify_users(
                    organization=expense.organization,
                    users=brand_admin_users(expense.organization),
                    notification_type=NotificationType.EXPENSE_REMINDER,
                    title=f"Reminder: {expense.category.name}",
                    body=f"Still pending · {expense.branch.name} · {expense.amount}",
                    link_path=f"/expenses/{expense.pk}",
                    expense_id=expense.pk,
                )
            else:
                skipped += 1
    return {"sent": sent, "skipped": skipped}
