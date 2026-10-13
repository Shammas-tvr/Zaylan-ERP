import { useEffect, useState } from 'react'
import { Button } from '../../shared/ui/Button.tsx'

const PAGE_SIZE = 20

export function usePagedRows<T>(rows: T[], resetKey: string) {
  const [page, setPage] = useState(0)
  useEffect(() => {
    setPage(0)
  }, [resetKey])
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const safe = Math.min(page, pages - 1)
  return {
    rows: rows.slice(safe * PAGE_SIZE, safe * PAGE_SIZE + PAGE_SIZE),
    page: safe,
    pages,
    setPage,
  }
}

export function Pager({
  page,
  pages,
  onPage,
}: {
  page: number
  pages: number
  onPage: (page: number) => void
}) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-end gap-2 px-3 py-3 text-sm">
      <Button type="button" size="sm" variant="secondary" disabled={page === 0} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span>
        {page + 1} of {pages}
      </span>
      <Button type="button" size="sm" variant="secondary" disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </div>
  )
}
