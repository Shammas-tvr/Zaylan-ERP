import { useState } from 'react'
import { uploadCatalogImage } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { Button } from '../../shared/ui/Button.tsx'

const allowed = ['image/jpeg', 'image/png', 'image/webp']

export function ImageField({
  purpose,
  imageUrl,
  disabled,
  onChange,
}: {
  purpose: 'product' | 'item'
  imageUrl: string | null
  disabled?: boolean
  onChange: (imageKey: string) => void
}) {
  const [preview, setPreview] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const shown = preview || imageUrl

  return (
    <div className="grid gap-2">
      <span className="text-sm font-medium">Image</span>
      {shown ? (
        <img src={shown} alt="" className="h-28 w-28 rounded-2xl border border-line object-cover" />
      ) : (
        <div className="grid h-28 w-28 place-items-center rounded-2xl border border-dashed border-line text-xs text-ink-soft">No image</div>
      )}
      {disabled ? null : (
        <div className="flex flex-wrap gap-2">
          <label className="inline-flex h-9 cursor-pointer items-center rounded-xl border border-line px-3 text-sm">
            {busy ? 'Uploading…' : shown ? 'Replace' : 'Upload'}
            <input
              className="sr-only"
              type="file"
              accept={allowed.join(',')}
              disabled={busy}
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                if (!file) return
                if (!allowed.includes(file.type)) {
                  setError('Use a JPEG, PNG, or WebP image.')
                  return
                }
                setBusy(true)
                setError('')
                const local = URL.createObjectURL(file)
                void uploadCatalogImage(file, purpose)
                  .then((key) => {
                    setPreview(local)
                    onChange(key)
                  })
                  .catch((reason: unknown) => {
                    URL.revokeObjectURL(local)
                    setError(reason instanceof Error ? reason.message : errorMessage(reason))
                  })
                  .finally(() => setBusy(false))
              }}
            />
          </label>
          {shown ? (
            <Button type="button" variant="secondary" size="sm" onClick={() => { setPreview(null); onChange('') }}>
              Remove
            </Button>
          ) : null}
        </div>
      )}
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </div>
  )
}
