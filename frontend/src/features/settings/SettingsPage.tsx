import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { tenantApi } from '../../shared/api/client'
import { queryKeys } from '../../shared/api/queryClient'
import { ApiError } from '../../shared/api/axios'
import { Alert, Button, Card, Field, Form, Page } from '../../shared/components/ui'
import { can, useTenant } from '../tenant_switcher/TenantProvider'
import { useAuth } from '../authentication/AuthProvider'

export function SettingsPage() {
  const tenant = useTenant()
  const { organizationId } = useAuth()
  const queryClient = useQueryClient()
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const manage = can(tenant, 'organization.manage')
  const save = useMutation({
    mutationFn: tenantApi.updateOrganization,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.context(organizationId!) }),
  })

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setError('')
    setMessage('')
    try {
      await save.mutateAsync({
        name: String(data.get('name')),
        legal_name: String(data.get('legal_name')),
        timezone: String(data.get('timezone')),
        currency: String(data.get('currency')),
      })
      setMessage('Settings saved.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to save settings.')
    }
  }

  return (
    <Page title="Organization settings" subtitle="Regional, tax and branding defaults for this tenant only.">
      <Card>
        <Form onSubmit={onSubmit}>
          {error ? <Alert>{error}</Alert> : null}
          {message ? <Alert tone="success">{message}</Alert> : null}
          <Field label="Display name" name="name" defaultValue={tenant.organization.name} disabled={!manage} />
          <Field label="Legal name" name="legal_name" defaultValue={tenant.organization.legal_name} disabled={!manage} />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Currency" name="currency" defaultValue={tenant.organization.currency} disabled={!manage} />
            <Field label="Timezone" name="timezone" defaultValue={tenant.organization.timezone} disabled={!manage} />
          </div>
          {manage ? <Button type="submit">Save changes</Button> : <p className="text-sm text-ink/70">You can view these settings but cannot change them.</p>}
        </Form>
      </Card>
    </Page>
  )
}
