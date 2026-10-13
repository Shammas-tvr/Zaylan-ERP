import { useEffect, useState } from 'react'
import {
  useNotificationSettings,
  useUpdateBranding,
  useUpdateNotificationSettings,
  useUpdateOrganization,
  useWorkspace,
} from '../workspace/queries.ts'
import type { Branding, NotificationSettings, Organization } from '../../shared/api/types.ts'
import { defaultBranding } from '../../shared/brand.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { industryLabel } from '../../shared/labels.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { SelectField, TextArea, TextField } from '../../shared/ui/Field.tsx'
import { NoAccess, Notice } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'

export function SettingsPage() {
  usePageTitle('Settings')
  const workspace = useWorkspace()
  const context = workspace.data
  if (!context) return null
  if (!can(context.permissions, 'organization.view')) return <NoAccess />
  return (
    <SettingsForm
      key={context.organization.id}
      organization={context.organization}
      branding={context.branding}
      canManage={can(context.permissions, 'organization.manage')}
    />
  )
}

function SettingsForm({
  organization,
  branding,
  canManage,
}: {
  organization: Organization
  branding: Branding
  canManage: boolean
}) {
  const [profile, setProfile] = useState(organization)
  const [brand, setBrand] = useState(branding)
  const [notice, setNotice] = useState<string | null>(null)
  const saveProfile = useUpdateOrganization()
  const saveBrand = useUpdateBranding()

  return (
    <div className="grid gap-6">
      <PageHeader title="Settings" description="Organization profile, regional defaults, and the colors this business sees." />
      {notice ? <Notice>{notice}</Notice> : null}
      <Panel>
        <h2 className="text-lg font-semibold">Organization</h2>
        <form
          className="mt-5 grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault()
            saveProfile.mutate(profile, { onSuccess: () => setNotice('Organization profile saved.') })
          }}
        >
          <TextField label="Display name" disabled={!canManage} value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} />
          <TextField label="Legal name" disabled={!canManage} value={profile.legal_name} onChange={(event) => setProfile({ ...profile, legal_name: event.target.value })} />
          <SelectField label="Industry" disabled={!canManage} value={profile.industry} onChange={(event) => setProfile({ ...profile, industry: event.target.value })}>
            {Object.entries(industryLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </SelectField>
          <TextField label="Currency" disabled={!canManage} maxLength={3} value={profile.currency} onChange={(event) => setProfile({ ...profile, currency: event.target.value.toUpperCase() })} />
          <TextField label="Timezone" disabled={!canManage} value={profile.timezone} onChange={(event) => setProfile({ ...profile, timezone: event.target.value })} />
          <TextField label="Locale" disabled={!canManage} value={profile.locale} onChange={(event) => setProfile({ ...profile, locale: event.target.value })} />
          <TextField label="Tax registration" disabled={!canManage} value={profile.tax_registration_number} onChange={(event) => setProfile({ ...profile, tax_registration_number: event.target.value })} />
          <TextField label="Contact email" type="email" disabled={!canManage} value={profile.contact_email} onChange={(event) => setProfile({ ...profile, contact_email: event.target.value })} />
          <div className="sm:col-span-2">
            <TextArea label="Address" disabled={!canManage} value={profile.address} onChange={(event) => setProfile({ ...profile, address: event.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              disabled={!canManage}
              checked={profile.prices_include_tax}
              onChange={(event) => setProfile({ ...profile, prices_include_tax: event.target.checked })}
            />
            Prices include tax
          </label>
          {saveProfile.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(saveProfile.error)}</p> : null}
          {canManage ? (
            <div className="sm:col-span-2">
              <Button type="submit" disabled={saveProfile.isPending}>
                {saveProfile.isPending ? 'Saving…' : 'Save profile'}
              </Button>
            </div>
          ) : null}
        </form>
      </Panel>
      <Panel>
        <h2 className="text-lg font-semibold">Branding</h2>
        <p className="mt-1 text-sm text-ink-soft">Cream stays the usual background. Accent colors are used for actions and the selected section.</p>
        <form
          className="mt-5 grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault()
            saveBrand.mutate(brand, { onSuccess: () => setNotice('Branding saved.') })
          }}
        >
          <TextField label="Business name on screen" disabled={!canManage} value={brand.display_name} onChange={(event) => setBrand({ ...brand, display_name: event.target.value })} />
          <ColorField label="Primary" disabled={!canManage} value={brand.primary_color} onChange={(value) => setBrand({ ...brand, primary_color: value })} />
          <ColorField label="Secondary" disabled={!canManage} value={brand.secondary_color} onChange={(value) => setBrand({ ...brand, secondary_color: value })} />
          <ColorField label="Background" disabled={!canManage} value={brand.background_color} onChange={(value) => setBrand({ ...brand, background_color: value })} />
          <ColorField label="Surface" disabled={!canManage} value={brand.surface_color} onChange={(value) => setBrand({ ...brand, surface_color: value })} />
          <ColorField label="Text" disabled={!canManage} value={brand.text_color} onChange={(value) => setBrand({ ...brand, text_color: value })} />
          {saveBrand.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(saveBrand.error)}</p> : null}
          {canManage ? (
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button type="submit" disabled={saveBrand.isPending}>
                {saveBrand.isPending ? 'Saving…' : 'Save branding'}
              </Button>
              <Button
                variant="secondary"
                disabled={saveBrand.isPending}
                onClick={() => {
                  const next = {
                    ...brand,
                    primary_color: defaultBranding.primary_color,
                    secondary_color: defaultBranding.secondary_color,
                    background_color: defaultBranding.background_color,
                    surface_color: defaultBranding.surface_color,
                    text_color: defaultBranding.text_color,
                  }
                  setBrand(next)
                  saveBrand.mutate(next, { onSuccess: () => setNotice('Colors are back to the Zaylan defaults.') })
                }}
              >
                Use default colors
              </Button>
            </div>
          ) : null}
        </form>
      </Panel>
      <NotificationSettingsPanel canManage={canManage} />
    </div>
  )
}

function NotificationSettingsPanel({ canManage }: { canManage: boolean }) {
  const settings = useNotificationSettings()
  const save = useUpdateNotificationSettings()
  const [form, setForm] = useState<NotificationSettings | null>(null)

  useEffect(() => {
    if (settings.data) setForm(settings.data)
  }, [settings.data])

  if (!form) return null

  return (
    <Panel>
      <h2 className="text-lg font-semibold">Expense notifications</h2>
      <p className="mt-1 text-sm text-ink-soft">
        Primary and extra emails receive submission alerts and pending-approval reminders (24h / 48h by default).
      </p>
      <form
        className="mt-5 grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate({
            primary_email: form.primary_email,
            extra_recipient_emails: form.extra_recipient_emails,
            reminder_intervals_hours: form.reminder_intervals_hours,
            reminders_enabled: form.reminders_enabled,
          })
        }}
      >
        <TextField
          label="Primary notification email"
          type="email"
          disabled={!canManage}
          value={form.primary_email}
          onChange={(e) => setForm({ ...form, primary_email: e.target.value })}
        />
        <TextField
          label="Extra recipients"
          disabled={!canManage}
          hint="Comma-separated emails"
          value={form.extra_recipient_emails.join(', ')}
          onChange={(e) =>
            setForm({
              ...form,
              extra_recipient_emails: e.target.value
                .split(',')
                .map((part) => part.trim())
                .filter(Boolean),
            })
          }
        />
        <TextField
          label="Reminder intervals (hours)"
          disabled={!canManage}
          hint="Comma-separated, e.g. 24, 48"
          value={form.reminder_intervals_hours.join(', ')}
          onChange={(e) =>
            setForm({
              ...form,
              reminder_intervals_hours: e.target.value
                .split(',')
                .map((part) => Number(part.trim()))
                .filter((n) => Number.isFinite(n) && n > 0),
            })
          }
        />
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            disabled={!canManage}
            checked={form.reminders_enabled}
            onChange={(e) => setForm({ ...form, reminders_enabled: e.target.checked })}
          />
          Send reminder emails while expenses remain pending
        </label>
        {save.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(save.error)}</p> : null}
        {canManage ? (
          <div className="sm:col-span-2">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save notification settings'}
            </Button>
          </div>
        ) : null}
      </form>
    </Panel>
  )
}

function ColorField({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}) {
  return (
    <label className="grid gap-1.5 text-sm font-medium">
      {label}
      <span className="flex h-11 items-center gap-3 rounded-xl border border-line bg-[var(--brand-surface)] px-3">
        <input type="color" disabled={disabled} value={safeHex(value)} aria-label={label} onChange={(event) => onChange(event.target.value.toUpperCase())} />
        <input
          className="w-full bg-transparent uppercase outline-none"
          disabled={disabled}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </span>
    </label>
  )
}

function safeHex(value: string) {
  return /^#[0-9A-Fa-f]{6}$/.test(value) ? value : '#6B2E2E'
}
