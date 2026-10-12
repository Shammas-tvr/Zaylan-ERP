# Phase 1 extension contract

Later modules must follow these rules so tenant isolation stays intact.

## Ownership

- Every tenant-owned model has a non-nullable `organization` foreign key with `PROTECT`.
- Branch-owned models also have `branch` and a composite foreign key `(organization, branch)` → `branches_branch (organization_id, id)`.
- Serializers never accept `organization` or `branch` ownership from the client. Services assign them from `request.tenant`.

## Querying

- Views extend `TenantScopedViewSet` or `TenantAPIView`.
- `get_object()` must run on an organization-filtered queryset so foreign UUIDs return 404.
- Branch-scoped actions must also filter to `request.tenant.branch_ids_with(permission)`.

## Authorization

- Declare `permission_rules` for every action. Undeclared actions are denied.
- Check `resource.action` codes, never role names.
- Platform permissions are independent of tenant memberships.
- Gate paid modules with `feature_rules` / `required_feature`.

## Money and history

- Use `DecimalField` for money. Do not recalculate historical rows from current prices.
- Multi-record writes use `transaction.atomic()`.
- Sensitive actions call `record_event(...)`. Audit rows are append-only.

## Jobs, files, caches

- Include `organization_id` (and `branch_id` when relevant) in payloads and cache keys.
- Re-resolve authorization when the job runs. Do not trust the payload alone.
- Logs and error messages must not include another tenant's data.

## Frontend

- All HTTP goes through `src/shared/api/axios.ts`.
- Server state uses TanStack Query keys that start with `['tenant', organizationId, ...]`.
- Switching organization or signing out must call `resetTenantCache()` / `queryClient.clear()`.
- Hide UI from missing permissions, but never rely on that as security.
