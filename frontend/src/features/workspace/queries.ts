import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSyncExternalStore } from 'react'
import { sessionStore } from '../../shared/session.ts'
import { clearTenantQueries } from '../../shared/api/queryClient.ts'
import {
  approveExpense,
  createBrand,
  createBranch,
  createExpense,
  createExpenseCategory,
  createRecurringExpense,
  createStaffMember,
  getContext,
  getExpense,
  getExpenseReport,
  getExpenseSummary,
  getMe,
  getNotificationSettings,
  getPlatformMetrics,
  getUnreadNotificationCount,
  listAudit,
  listExpenseCategories,
  listExpenses,
  listInvitations,
  listMembers,
  listNotifications,
  listOrganizations,
  listPlans,
  listRecurringExpenses,
  listRoles,
  listTenants,
  markAllNotificationsRead,
  markExpensePaid,
  markNotificationRead,
  rejectExpense,
  revokeInvitation,
  sendInvitation,
  setTenantStatus,
  setTenantSubscription,
  updateBrand,
  getTenant,
  submitExpense,
  updateBranding,
  updateNotificationSettings,
  updateOrganization,
} from '../../shared/api/workspace.ts'
import type {
  BranchInput,
  Branding,
  BrandOnboardInput,
  NotificationSettings,
  Organization,
  OrgStatus,
} from '../../shared/api/types.ts'

export function useSession() {
  return useSyncExternalStore(sessionStore.subscribe, sessionStore.get, sessionStore.get)
}

export function useOrganizationId() {
  return useSession().organizationId
}

export function selectOrganization(organizationId: string) {
  if (sessionStore.get().organizationId === organizationId) return
  sessionStore.set({ organizationId, branchId: null })
  clearTenantQueries()
}

export function selectBranch(branchId: string | null) {
  sessionStore.set({ branchId })
}

export function useMe() {
  const session = useSession()
  return useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    enabled: Boolean(session.accessToken || session.preview),
  })
}

export function useOrganizations() {
  const session = useSession()
  return useQuery({
    queryKey: ['organizations'],
    queryFn: listOrganizations,
    enabled: Boolean(session.accessToken || session.preview),
  })
}

export function useWorkspace() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['context', organizationId],
    queryFn: getContext,
    enabled: Boolean(organizationId),
  })
}

export function useMembers(enabled = true) {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['members', organizationId],
    queryFn: listMembers,
    enabled: Boolean(organizationId) && enabled,
  })
}

export function useInvitations(enabled = true) {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['invitations', organizationId],
    queryFn: listInvitations,
    enabled: Boolean(organizationId) && enabled,
  })
}

export function useRoles(enabled = true) {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['roles', organizationId],
    queryFn: listRoles,
    enabled: Boolean(organizationId) && enabled,
  })
}

export function useAudit(search: string, enabled = true) {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['audit', organizationId, search],
    queryFn: () => listAudit(search),
    enabled: Boolean(organizationId) && enabled,
  })
}

export function useTenants() {
  return useQuery({ queryKey: ['platform', 'tenants'], queryFn: listTenants })
}

export function useTenant(id: string) {
  return useQuery({
    queryKey: ['platform', 'tenants', id],
    queryFn: () => getTenant(id),
    enabled: Boolean(id),
  })
}

export function useUpdateBrand() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Parameters<typeof updateBrand>[1] }) =>
      updateBrand(id, input),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['platform', 'tenants'] })
      await queryClient.invalidateQueries({ queryKey: ['platform', 'tenants', variables.id] })
      await queryClient.invalidateQueries({ queryKey: ['platform', 'metrics'] })
    },
  })
}

export function usePlans() {
  return useQuery({ queryKey: ['platform', 'plans'], queryFn: listPlans })
}

function useRefresh(keys: string[]) {
  const queryClient = useQueryClient()
  const organizationId = useOrganizationId()
  return () => Promise.all(keys.map((key) => queryClient.invalidateQueries({ queryKey: [key, organizationId] })))
}

export function useCreateBranch() {
  const refresh = useRefresh(['context', 'audit'])
  return useMutation({
    mutationFn: (input: BranchInput) => createBranch(input),
    onSuccess: refresh,
  })
}

export function useUpdateOrganization() {
  const refresh = useRefresh(['context', 'audit'])
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (patch: Partial<Organization>) => updateOrganization(patch),
    onSuccess: async () => {
      await refresh()
      await queryClient.invalidateQueries({ queryKey: ['organizations'] })
    },
  })
}

export function useUpdateBranding() {
  const refresh = useRefresh(['context', 'audit'])
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (patch: Branding) => updateBranding(patch),
    onSuccess: async () => {
      await refresh()
      await queryClient.invalidateQueries({ queryKey: ['organizations'] })
    },
  })
}

export function useSendInvitation() {
  const refresh = useRefresh(['invitations', 'audit'])
  return useMutation({
    mutationFn: sendInvitation,
    onSuccess: refresh,
  })
}

export function useCreateStaff() {
  const refresh = useRefresh(['members', 'audit'])
  return useMutation({
    mutationFn: createStaffMember,
    onSuccess: refresh,
  })
}

export function useRevokeInvitation() {
  const refresh = useRefresh(['invitations', 'audit'])
  return useMutation({
    mutationFn: (id: string) => revokeInvitation(id),
    onSuccess: refresh,
  })
}

export function useSetTenantStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: OrgStatus }) => setTenantStatus(id, status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['platform', 'tenants'] })
      await queryClient.invalidateQueries({ queryKey: ['platform', 'metrics'] })
      await queryClient.invalidateQueries({ queryKey: ['organizations'] })
      await queryClient.invalidateQueries({ queryKey: ['context'] })
    },
  })
}

export function usePlatformMetrics() {
  const me = useMe()
  const allowed = Boolean(me.data?.platform_permissions?.includes('platform.metrics.view'))
  return useQuery({
    queryKey: ['platform', 'metrics'],
    queryFn: getPlatformMetrics,
    enabled: allowed || Boolean(me.data?.platform_permissions?.includes('platform.tenants.view')),
  })
}

export function useCreateBrand() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BrandOnboardInput) => createBrand(input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['platform', 'tenants'] })
      await queryClient.invalidateQueries({ queryKey: ['platform', 'metrics'] })
    },
  })
}

export function useSetTenantSubscription() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, plan_code, status }: { id: string; plan_code?: string; status?: string }) =>
      setTenantSubscription(id, { plan_code, status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['platform', 'tenants'] })
      await queryClient.invalidateQueries({ queryKey: ['platform', 'metrics'] })
    },
  })
}

function useExpenseRefresh() {
  const queryClient = useQueryClient()
  const organizationId = useOrganizationId()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['expenses', organizationId] }),
      queryClient.invalidateQueries({ queryKey: ['expense-summary', organizationId] }),
      queryClient.invalidateQueries({ queryKey: ['expense-report', organizationId] }),
      queryClient.invalidateQueries({ queryKey: ['notifications', organizationId] }),
      queryClient.invalidateQueries({ queryKey: ['audit', organizationId] }),
    ])
}

export function useExpenses(params: { status?: string; search?: string } = {}) {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['expenses', organizationId, params.status ?? '', params.search ?? ''],
    queryFn: () => listExpenses(params),
    enabled: Boolean(organizationId),
  })
}

export function useExpense(id: string) {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['expenses', organizationId, id],
    queryFn: () => getExpense(id),
    enabled: Boolean(organizationId && id),
  })
}

export function useExpenseSummary() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['expense-summary', organizationId],
    queryFn: getExpenseSummary,
    enabled: Boolean(organizationId),
  })
}

export function useExpenseReport() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['expense-report', organizationId],
    queryFn: getExpenseReport,
    enabled: Boolean(organizationId),
  })
}

export function useExpenseCategories() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['expense-categories', organizationId],
    queryFn: listExpenseCategories,
    enabled: Boolean(organizationId),
  })
}

export function useRecurringExpenses() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['expense-recurring', organizationId],
    queryFn: listRecurringExpenses,
    enabled: Boolean(organizationId),
  })
}

export function useCreateExpense() {
  const refresh = useExpenseRefresh()
  return useMutation({ mutationFn: createExpense, onSuccess: refresh })
}

export function useSubmitExpense() {
  const refresh = useExpenseRefresh()
  return useMutation({ mutationFn: (id: string) => submitExpense(id), onSuccess: refresh })
}

export function useApproveExpense() {
  const refresh = useExpenseRefresh()
  return useMutation({ mutationFn: (id: string) => approveExpense(id), onSuccess: refresh })
}

export function useRejectExpense() {
  const refresh = useExpenseRefresh()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectExpense(id, reason),
    onSuccess: refresh,
  })
}

export function useMarkExpensePaid() {
  const refresh = useExpenseRefresh()
  return useMutation({
    mutationFn: ({ id, payment_reference }: { id: string; payment_reference?: string }) =>
      markExpensePaid(id, payment_reference),
    onSuccess: refresh,
  })
}

export function useCreateExpenseCategory() {
  const queryClient = useQueryClient()
  const organizationId = useOrganizationId()
  return useMutation({
    mutationFn: createExpenseCategory,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['expense-categories', organizationId] }),
  })
}

export function useCreateRecurringExpense() {
  const queryClient = useQueryClient()
  const organizationId = useOrganizationId()
  return useMutation({
    mutationFn: createRecurringExpense,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['expense-recurring', organizationId] }),
  })
}

export function useNotifications() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['notifications', organizationId],
    queryFn: listNotifications,
    enabled: Boolean(organizationId),
    refetchInterval: 60_000,
  })
}

export function useUnreadNotificationCount() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['notifications', organizationId, 'unread'],
    queryFn: getUnreadNotificationCount,
    enabled: Boolean(organizationId),
    refetchInterval: 60_000,
  })
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient()
  const organizationId = useOrganizationId()
  return useMutation({
    mutationFn: (id: string) => markNotificationRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications', organizationId] }),
  })
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient()
  const organizationId = useOrganizationId()
  return useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications', organizationId] }),
  })
}

export function useNotificationSettings() {
  const organizationId = useOrganizationId()
  return useQuery({
    queryKey: ['notification-settings', organizationId],
    queryFn: getNotificationSettings,
    enabled: Boolean(organizationId),
  })
}

export function useUpdateNotificationSettings() {
  const queryClient = useQueryClient()
  const organizationId = useOrganizationId()
  return useMutation({
    mutationFn: (patch: Partial<NotificationSettings>) => updateNotificationSettings(patch),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['notification-settings', organizationId] }),
  })
}
