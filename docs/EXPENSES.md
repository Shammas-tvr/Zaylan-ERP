# Expenses, brands, and notifications

Brand = `Organization` (no separate Company parent). Platform Super Admin onboards brands; Brand Admin (Owner) approves expenses.

## Permissions

| Code | Who |
|------|-----|
| `expenses.view` / `expenses.submit` | Branch-scoped roles (cashier, branch manager) and owners |
| `expenses.approve` / `expenses.pay` / `expenses.configure` | Brand-level (Owner, Accountant) — not branch managers |

Self-approval is always rejected when the actor submitted the expense.

## Statuses

`DRAFT` → `PENDING_APPROVAL` → `APPROVED` or `REJECTED` → `PAID`

Recurring generation creates `PENDING_APPROVAL` rows only (never approved/paid automatically). Unique on organization + branch + category + billing period for recurring entries.

## Jobs

```text
generate_recurring_expenses
send_expense_reminders
retry_failed_emails
```

Reminder intervals default to 24h and 48h (configurable per brand under Settings). Duplicates are prevented via `EmailDeliveryLog` uniqueness.

## Env

See `backend/.env.example` for `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `MEDIA_ROOT`, `EXPENSE_RECEIPT_MAX_BYTES`.
