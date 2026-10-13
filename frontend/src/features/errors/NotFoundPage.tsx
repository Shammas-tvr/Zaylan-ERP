import { Link } from 'react-router-dom'
import { usePageTitle } from '../../shared/hooks.ts'
import { Wordmark } from '../../shared/ui/Wordmark.tsx'
import { useSession } from '../workspace/queries.ts'

export function NotFoundPage() {
  usePageTitle('Page not found')
  const session = useSession()
  const home = session.accessToken || session.preview ? '/' : '/login'

  return (
    <main className="grid min-h-[70vh] place-items-center px-6 py-16">
      <div className="w-full max-w-md text-center">
        <div className="flex justify-center">
          <Wordmark />
        </div>
        <p className="mt-10 font-display text-7xl tracking-tight text-[var(--brand-primary)]">404</p>
        <h1 className="mt-3 font-display text-3xl tracking-tight">Page not found</h1>
        <p className="mt-3 text-ink-soft">This address does not match a page in Zaylan.</p>
        <Link
          to={home}
          className="mt-8 inline-flex h-11 items-center justify-center rounded-xl bg-[var(--brand-primary)] px-4 text-sm font-medium text-[var(--brand-on-primary)] hover:opacity-90"
        >
          {home === '/' ? 'Back to workspace' : 'Back to sign in'}
        </Link>
      </div>
    </main>
  )
}
