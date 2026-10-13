import { createBrowserRouter, Navigate, RouterProvider, useParams } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '../shared/api/queryClient.ts'
import { AcceptInvitePage } from '../features/auth/AcceptInvitePage.tsx'
import { ForgotPasswordPage } from '../features/auth/ForgotPasswordPage.tsx'
import { LoginPage } from '../features/auth/LoginPage.tsx'
import { SuperAdminLoginPage } from '../features/auth/SuperAdminLoginPage.tsx'
import { AuditPage } from '../features/audit/AuditPage.tsx'
import { BranchesPage } from '../features/branches/BranchesPage.tsx'
import { InventoryTabs } from '../features/inventory/InventoryTabs.tsx'
import { InventoryPage } from '../features/inventory/InventoryPage.tsx'
import { RecipesPage } from '../features/inventory/RecipesPage.tsx'
import { StockPage } from '../features/inventory/StockPage.tsx'
import { ProductionPage } from '../features/inventory/ProductionPage.tsx'
import { ProductsPage } from '../features/inventory/ProductsPage.tsx'
import { SalesPage } from '../features/inventory/SalesPage.tsx'
import { TransfersPage } from '../features/inventory/TransfersPage.tsx'
import { ApprovalsPage } from '../features/expenses/ApprovalsPage.tsx'
import { ExpenseDetailPage } from '../features/expenses/ExpenseDetailPage.tsx'
import { ExpensesPage } from '../features/expenses/ExpensesPage.tsx'
import { RecurringPage } from '../features/expenses/RecurringPage.tsx'
import { ExpenseReportsPage } from '../features/expenses/ReportsPage.tsx'
import { NotFoundPage } from '../features/errors/NotFoundPage.tsx'
import { OverviewPage } from '../features/overview/OverviewPage.tsx'
import { PeoplePage } from '../features/people/PeoplePage.tsx'
import { PlansPage } from '../features/platform/PlansPage.tsx'
import { BrandDetailPage } from '../features/platform/BrandDetailPage.tsx'
import { TenantsPage } from '../features/platform/TenantsPage.tsx'
import { SettingsPage } from '../features/settings/SettingsPage.tsx'
import { RequireSession, SessionGate } from './SessionGate.tsx'
import { WorkspaceLayout } from './WorkspaceLayout.tsx'

const router = createBrowserRouter([
  {
    element: <SessionGate />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/forgot-password', element: <Navigate to="/login" replace /> },
      { path: '/superadmin/login', element: <SuperAdminLoginPage /> },
      { path: '/b/:brandSlug', element: <BrandPortalRedirect /> },
      { path: '/b/:brandSlug/login', element: <LoginPage /> },
      { path: '/b/:brandSlug/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/invitations/accept', element: <AcceptInvitePage /> },
      {
        element: <RequireSession />,
        children: [
          {
            element: <WorkspaceLayout />,
            children: [
              { index: true, element: <OverviewPage /> },
              { path: 'branches', element: <BranchesPage /> },
              { 
                path: 'inventory',
                element: <InventoryTabs />,
                children: [
                  { index: true, element: <InventoryPage /> },
                  { path: 'recipes', element: <RecipesPage /> },
                  { path: 'production', element: <ProductionPage /> },
                  { path: 'transfers', element: <TransfersPage /> },
                  { path: 'stock', element: <StockPage /> },
                ],
              },
              { path: 'products', element: <ProductsPage /> },
              { path: 'sales', element: <SalesPage /> },
              { path: 'expenses', element: <ExpensesPage /> },
              { path: 'expenses/approvals', element: <ApprovalsPage /> },
              { path: 'expenses/recurring', element: <RecurringPage /> },
              { path: 'expenses/reports', element: <ExpenseReportsPage /> },
              { path: 'expenses/:expenseId', element: <ExpenseDetailPage /> },
              { path: 'people', element: <PeoplePage /> },
              { path: 'settings', element: <SettingsPage /> },
              { path: 'audit', element: <AuditPage /> },
              { path: 'platform/brands/:brandId', element: <BrandDetailPage /> },
              { path: 'platform/brands', element: <TenantsPage /> },
              { path: 'platform/tenants', element: <Navigate to="/platform/brands" replace /> },
              { path: 'platform/plans', element: <PlansPage /> },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

function BrandPortalRedirect() {
  const { brandSlug } = useParams<{ brandSlug: string }>()
  return <Navigate to={`/b/${brandSlug}/login`} replace />
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
