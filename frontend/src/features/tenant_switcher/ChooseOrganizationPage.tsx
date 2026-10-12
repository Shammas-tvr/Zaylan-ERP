import { Navigate } from 'react-router-dom'

import { Button, Card, Page } from '../../shared/components/ui'
import { useAuth, useOrganizations } from '../authentication/AuthProvider'

export function ChooseOrganizationPage() {
  const { selectOrganization, user } = useAuth()
  const { data: memberships = [], isLoading } = useOrganizations()
  const platform = Boolean(user?.platform_permissions?.length)

  if (isLoading) return <p className="p-8">Loading…</p>
  if (!memberships.length && platform) return <Navigate to="/platform" replace />
  if (!memberships.length) {
    return (
      <Page title="No organization yet">
        <Card>
          <p className="text-sm">Your account is not a member of an organization. Ask an administrator for an invitation.</p>
        </Card>
      </Page>
    )
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-16">
      <h1 className="mb-4 font-display text-3xl font-semibold">Choose an organization</h1>
      <div className="flex flex-col gap-3">
        {memberships.map((membership) => (
          <Card key={membership.id}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold">{membership.organization.name}</p>
                <p className="text-sm text-ink/70">{membership.organization.industry}</p>
              </div>
              <Button onClick={() => selectOrganization(membership.organization.id)}>Open</Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
