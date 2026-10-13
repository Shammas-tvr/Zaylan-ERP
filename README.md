# Zaylan

Multi-tenant ERP + POS SaaS. Phase 1 establishes identity, organizations, branches, RBAC, subscriptions, audit logging, and a branded administration UI.

## Stack

- Backend: Django 5, Django REST Framework, Simple JWT, PostgreSQL
- Frontend: React, Vite, Tailwind CSS, Axios, TanStack Query

## Repository layout

- `backend/` — modular Django monolith (`apps.accounts`, `tenancy`, `branches`, `access_control`, `subscriptions`, `audit_logs`, `platform_admin`, `notifications`, `expenses`)
- `frontend/` — React application

## Environment

Never commit `.env` files. Local settings live in `backend/.env` and `frontend/.env`.

`backend/.env` must include a strong `DJANGO_SECRET_KEY`, a distinct `JWT_SIGNING_KEY`, a `DATABASE_URL` for a PostgreSQL role that can create databases (required by tests), and SMTP values for password-reset email (`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`).

`frontend/.env` leaves `VITE_API_URL` empty so the Vite dev server proxies `/api` to Django.

## Database

PostgreSQL 17 on `localhost:5432` is expected. Create a role and database, then set `DATABASE_URL` in `backend/.env`:

```sql
CREATE ROLE zaylan LOGIN PASSWORD 'choose-a-strong-password';
CREATE DATABASE zaylan OWNER zaylan;
ALTER ROLE zaylan CREATEDB;
```

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py bootstrap_platform --admin-email you@example.com
python manage.py onboard_tenant --name Zaylan --slug zaylan --owner-email owner@zaylan.test --industry DESSERT_SHOP --plan growth
python manage.py runserver
```

`bootstrap_platform` prompts for a password unless `PLATFORM_ADMIN_PASSWORD` is set. It also refreshes system role permissions (including expenses). The Brand Admin invitation link printed by `onboard_tenant` is single-use and emailed when SMTP/console mail is configured.

### Scheduled jobs (expenses)

Run on a schedule (Task Scheduler / cron). Do not rely on an open browser session.

```powershell
python manage.py generate_recurring_expenses
python manage.py send_expense_reminders
python manage.py retry_failed_emails
```

Email uses `EMAIL_*` / `DEFAULT_FROM_EMAIL` from the environment (console backend by default). Receipt uploads use `MEDIA_ROOT`.

Tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The UI is at http://localhost:5173. Sign in, or open an invitation URL (`/invitations/accept#token=...`).

```powershell
npm test
npm run build
```

## Auth and tenancy

- Access tokens live in memory and are sent as `Authorization: Bearer`.
- Refresh tokens are rotated HttpOnly cookies on `/api/v1/auth/`.
- Tenant APIs require `X-Organization-ID`. The header selects context; membership is resolved on the server.
- Platform administrators manage brand (organization) lifecycle and plans. They do not receive brand expense detail from the platform console.
- Brand Admins approve expenses. Branch users submit them. Self-approval is denied by default. Approval and payment are separate statuses.

## Verification

1. `backend/.venv/Scripts/python.exe manage.py check`
2. `backend/.venv/Scripts/python.exe -m pytest`
3. `cd frontend && npm test && npm run build`
4. Confirm a cashier cannot read `/api/v1/organization/members` or `/api/v1/audit-events/`.
5. Confirm an owner of tenant A receives 404/403 (never tenant B's payload) when substituting tenant B IDs.

## Later phases

Phase 2 adds the unified catalog, recipes, and costing. POS and inventory modules remain planned.
