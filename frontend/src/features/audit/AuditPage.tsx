import { useState } from 'react'
import { useAudit, useWorkspace } from '../workspace/queries.ts'
import { useDebouncedValue, usePageTitle } from '../../shared/hooks.ts'
import { actionLabel, formatWhen, labelOf } from '../../shared/labels.ts'
import { can } from '../../shared/permissions.ts'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'

export function AuditPage() {
  usePageTitle('Audit')
  const workspace = useWorkspace()
  const context = workspace.data
  const allowed = can(context?.permissions, 'audit.view')
  const [search, setSearch] = useState('')
  const debounced = useDebouncedValue(search)
  const audit = useAudit(debounced, allowed)

  if (!context) return null
  if (!allowed) return <NoAccess />

  return (
    <div className="grid gap-6">
      <PageHeader title="Audit" description="A record of organization changes. Passwords, tokens, and secrets are never stored here." />
      <TextField label="Search activity" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Branch, invitation, profile…" />
      <Panel>
        <DataTable
          caption="Audit events"
          rows={audit.data ?? []}
          rowKey={(event) => event.id}
          empty={audit.isLoading ? 'Loading activity…' : 'No matching activity.'}
          columns={[
            { header: 'When', render: (event) => formatWhen(event.created_at, context.organization.timezone) },
            { header: 'Action', render: (event) => labelOf(actionLabel, event.action) },
            { header: 'Detail', render: (event) => event.summary },
            { header: 'By', render: (event) => event.actor_name },
          ]}
        />
      </Panel>
    </div>
  )
}
