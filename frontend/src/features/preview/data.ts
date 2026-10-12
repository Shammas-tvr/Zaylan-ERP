import type {
  AuditEvent,
  Branch,
  Branding,
  Invitation,
  Me,
  Member,
  Organization,
  OrganizationSummary,
  Plan,
  PlatformTenant,
  Role,
  SubscriptionSummary,
  WorkspaceContext,
} from '../../shared/api/types.ts'
import { permissionCatalog } from '../../shared/permissions.ts'

export const ZAYLAN_ID = '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0001'
export const CEDAR_ID = '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0002'
const BHARUCH_ID = '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0011'
const VADODARA_ID = '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0012'
const CEDAR_BRANCH_ID = '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0021'

const zaylanBrand: Branding = {
  display_name: 'Zaylan',
  logo_url: '',
  primary_color: '#6B2E2E',
  secondary_color: '#B58A5A',
  background_color: '#F3E7D6',
  surface_color: '#FFFDF9',
  text_color: '#171717',
}

const cedarBrand: Branding = {
  display_name: 'Cedar Bakehouse',
  logo_url: '',
  primary_color: '#2F4A3C',
  secondary_color: '#B58A5A',
  background_color: '#EFE8DC',
  surface_color: '#FFFDF9',
  text_color: '#171717',
}

const zaylanOrg: Organization = {
  id: ZAYLAN_ID,
  name: 'Zaylan',
  legal_name: 'Zaylan',
  slug: 'zaylan',
  industry: 'dessert_shop',
  status: 'active',
  currency: 'INR',
  timezone: 'Asia/Kolkata',
  locale: 'en-IN',
  tax_registration_number: '',
  prices_include_tax: true,
  contact_email: 'hello@zaylan.test',
  contact_phone: '',
  address: 'Bharuch, Gujarat',
}

const cedarOrg: Organization = {
  id: CEDAR_ID,
  name: 'Cedar Bakehouse',
  legal_name: 'Cedar Bakehouse',
  slug: 'cedar-bakehouse',
  industry: 'cafe',
  status: 'active',
  currency: 'INR',
  timezone: 'Asia/Kolkata',
  locale: 'en-IN',
  tax_registration_number: '',
  prices_include_tax: true,
  contact_email: 'hello@cedar.test',
  contact_phone: '',
  address: 'Vadodara, Gujarat',
}

const bharuch: Branch = {
  id: BHARUCH_ID,
  code: 'BH',
  name: 'Bharuch',
  status: 'active',
  timezone: 'Asia/Kolkata',
  phone: '',
  email: 'bharuch@zaylan.test',
  address: 'Bharuch, Gujarat',
}

const vadodara: Branch = {
  id: VADODARA_ID,
  code: 'VD',
  name: 'Vadodara',
  status: 'active',
  timezone: 'Asia/Kolkata',
  phone: '',
  email: 'vadodara@zaylan.test',
  address: 'Vadodara, Gujarat',
}

const cedarBranch: Branch = {
  id: CEDAR_BRANCH_ID,
  code: 'MAIN',
  name: 'Main cafe',
  status: 'active',
  timezone: 'Asia/Kolkata',
  phone: '',
  email: 'cafe@cedar.test',
  address: 'Vadodara, Gujarat',
}

const growthFeatures = [
  'multi_branch',
  'pos',
  'recipes',
  'inventory',
  'purchasing',
  'production',
  'expenses',
  'finance_reports',
]

const zaylanSubscription: SubscriptionSummary = {
  plan_code: 'growth',
  plan_name: 'Growth',
  status: 'trialing',
  is_usable: true,
  features: growthFeatures,
  max_branches: 5,
  max_members: 25,
  trial_ends_at: '2026-10-26T00:00:00.000Z',
}

const cedarSubscription: SubscriptionSummary = {
  plan_code: 'starter',
  plan_name: 'Starter',
  status: 'active',
  is_usable: true,
  features: ['pos', 'expenses'],
  max_branches: 1,
  max_members: 5,
  trial_ends_at: null,
}

function tenantPermissions() {
  return Object.fromEntries(Object.keys(permissionCatalog).map((code) => [code, { scope: 'tenant' as const }]))
}

export type PreviewData = {
  me: Me
  organizations: OrganizationSummary[]
  contexts: Record<string, WorkspaceContext>
  members: Record<string, Member[]>
  invitations: Record<string, Invitation[]>
  roles: Record<string, Role[]>
  audit: Record<string, AuditEvent[]>
  tenants: PlatformTenant[]
  plans: Plan[]
}

export const initialPreview: PreviewData = {
  me: {
    id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0100',
    email: 'owner@zaylan.test',
    full_name: 'Owner',
    platform_permissions: [
      'platform.tenants.view',
      'platform.tenants.manage',
      'platform.plans.view',
      'platform.plans.manage',
      'platform.metrics.view',
      'platform.audit.view',
    ],
  },
  organizations: [
    {
      id: ZAYLAN_ID,
      name: 'Zaylan',
      slug: 'zaylan',
      industry: 'dessert_shop',
      status: 'active',
      branding: zaylanBrand,
    },
    {
      id: CEDAR_ID,
      name: 'Cedar Bakehouse',
      slug: 'cedar-bakehouse',
      industry: 'cafe',
      status: 'active',
      branding: cedarBrand,
    },
  ],
  contexts: {
    [ZAYLAN_ID]: {
      organization: zaylanOrg,
      branding: zaylanBrand,
      subscription: zaylanSubscription,
      permissions: tenantPermissions(),
      branches: [bharuch, vadodara],
    },
    [CEDAR_ID]: {
      organization: cedarOrg,
      branding: cedarBrand,
      subscription: cedarSubscription,
      permissions: {
        'branches.view': { scope: 'branches', branch_ids: [CEDAR_BRANCH_ID] },
        'catalog.view': { scope: 'branches', branch_ids: [CEDAR_BRANCH_ID] },
        'pos.sell': { scope: 'branches', branch_ids: [CEDAR_BRANCH_ID] },
        'sales.view_own': { scope: 'branches', branch_ids: [CEDAR_BRANCH_ID] },
      },
      branches: [cedarBranch],
    },
  },
  members: {
    [ZAYLAN_ID]: [
      {
        id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0100',
        full_name: 'Owner',
        email: 'owner@zaylan.test',
        status: 'active',
        branches: ['All branches'],
        roles: ['Owner / Admin'],
      },
      {
        id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0101',
        full_name: 'Branch manager',
        email: 'bharuch@zaylan.test',
        status: 'active',
        branches: ['Bharuch'],
        roles: ['Branch Manager'],
      },
      {
        id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0102',
        full_name: 'Cashier',
        email: 'vadodara@zaylan.test',
        status: 'active',
        branches: ['Vadodara'],
        roles: ['Cashier'],
      },
      {
        id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0103',
        full_name: 'Accountant',
        email: 'accounts@zaylan.test',
        status: 'active',
        branches: ['All branches'],
        roles: ['Accountant'],
      },
    ],
    [CEDAR_ID]: [
      {
        id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0100',
        full_name: 'Owner',
        email: 'owner@zaylan.test',
        status: 'active',
        branches: ['Main cafe'],
        roles: ['Cashier'],
      },
    ],
  },
  invitations: {
    [ZAYLAN_ID]: [
      {
        id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0201',
        email: 'partner@zaylan.test',
        role_name: 'Investor / Partner',
        status: 'pending',
        expires_at: '2026-10-15T12:00:00.000Z',
      },
    ],
    [CEDAR_ID]: [],
  },
  roles: {
    [ZAYLAN_ID]: [
      {
        id: 'role-owner',
        name: 'Owner / Admin',
        description: 'Full control of this organization. No platform privileges.',
        is_system: true,
        permissions: Object.keys(permissionCatalog),
      },
      {
        id: 'role-manager',
        name: 'Branch Manager',
        description: 'Runs assigned branches.',
        is_system: true,
        permissions: [
          'organization.view',
          'branches.view',
          'branches.manage',
          'members.view',
          'catalog.view',
          'pos.sell',
          'pos.refund',
          'sales.view_own',
          'sales.view',
          'inventory.view',
          'inventory.manage',
          'expenses.submit',
          'expenses.view',
        ],
      },
      {
        id: 'role-cashier',
        name: 'Cashier',
        description: 'Point of sale, own transactions, and own shift.',
        is_system: true,
        permissions: ['branches.view', 'catalog.view', 'pos.sell', 'sales.view_own'],
      },
      {
        id: 'role-inventory',
        name: 'Inventory Manager',
        description: 'Stock, purchasing, and wastage.',
        is_system: true,
        permissions: ['branches.view', 'catalog.view', 'inventory.view', 'inventory.manage', 'purchasing.manage'],
      },
      {
        id: 'role-accountant',
        name: 'Accountant',
        description: 'Expenses, approvals, and financial reports.',
        is_system: true,
        permissions: [
          'organization.view',
          'branches.view',
          'sales.view',
          'sales.totals.view',
          'expenses.view',
          'expenses.approve',
          'expenses.pay',
          'reports.financial.view',
          'costs.view',
        ],
      },
      {
        id: 'role-investor',
        name: 'Investor / Partner',
        description: 'Read-only access to authorized financial reports.',
        is_system: true,
        permissions: ['organization.view', 'branches.view', 'sales.totals.view', 'reports.financial.view'],
      },
    ],
    [CEDAR_ID]: [
      {
        id: 'cedar-cashier',
        name: 'Cashier',
        description: 'Point of sale, own transactions, and own shift.',
        is_system: true,
        permissions: ['branches.view', 'catalog.view', 'pos.sell', 'sales.view_own'],
      },
    ],
  },
  audit: {
    [ZAYLAN_ID]: [
      {
        id: 'audit-1',
        created_at: '2026-10-11T09:40:00.000Z',
        action: 'branch.created',
        actor_name: 'Owner',
        summary: 'Vadodara (VD)',
      },
      {
        id: 'audit-2',
        created_at: '2026-10-10T14:15:00.000Z',
        action: 'member.invited',
        actor_name: 'Owner',
        summary: 'partner@zaylan.test · Investor / Partner',
      },
      {
        id: 'audit-3',
        created_at: '2026-10-08T06:05:00.000Z',
        action: 'organization.updated',
        actor_name: 'Owner',
        summary: 'Currency set to INR',
      },
    ],
    [CEDAR_ID]: [
      {
        id: 'audit-c1',
        created_at: '2026-10-09T11:00:00.000Z',
        action: 'branch.created',
        actor_name: 'Owner',
        summary: 'Main cafe (MAIN)',
      },
    ],
  },
  tenants: [
    {
      id: ZAYLAN_ID,
      name: 'Zaylan',
      slug: 'zaylan',
      industry: 'dessert_shop',
      status: 'active',
      plan_name: 'Growth',
      plan_code: 'growth',
      subscription_status: 'active',
      branch_count: 2,
      member_count: 4,
      contact_email: 'hello@zaylan.test',
      legal_name: 'Zaylan',
    },
    {
      id: CEDAR_ID,
      name: 'Cedar Bakehouse',
      slug: 'cedar-bakehouse',
      industry: 'cafe',
      status: 'active',
      plan_name: 'Starter',
      plan_code: 'starter',
      subscription_status: 'trialing',
      branch_count: 1,
      member_count: 3,
      contact_email: 'hello@cedar.test',
      legal_name: 'Cedar Bakehouse',
    },
    {
      id: '4b2e6a10-1c3a-4e5f-9a11-0a0a0a0a0003',
      name: 'Northwind Retail',
      slug: 'northwind',
      industry: 'retail',
      status: 'suspended',
      plan_name: 'Growth',
      plan_code: 'growth',
      subscription_status: 'suspended',
      branch_count: 4,
      member_count: 18,
      contact_email: 'hello@northwind.test',
      legal_name: 'Northwind Retail Pvt Ltd',
    },
  ],
  plans: [
    {
      id: 'plan-starter',
      code: 'starter',
      name: 'Starter',
      description: 'One branch, with billing and expenses.',
      trial_days: 14,
      max_branches: 1,
      max_members: 5,
      features: ['pos', 'expenses'],
      is_active: true,
    },
    {
      id: 'plan-growth',
      code: 'growth',
      name: 'Growth',
      description: 'Several branches, recipes, inventory, and reports.',
      trial_days: 14,
      max_branches: 5,
      max_members: 25,
      features: growthFeatures,
      is_active: true,
    },
    {
      id: 'plan-scale',
      code: 'scale',
      name: 'Scale',
      description: 'Unlimited branches and franchise agreements.',
      trial_days: 14,
      max_branches: null,
      max_members: null,
      features: [...growthFeatures, 'franchise'],
      is_active: true,
    },
  ],
}
