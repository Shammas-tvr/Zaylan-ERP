import { describe, expect, it } from 'vitest'

import { clearTenantQueries, queryClient } from './queryClient'

describe('tenant query cache', () => {
  it('clears tenant-scoped queries without dropping the signed-in user', () => {
    queryClient.setQueryData(['members', 'aaa'], [{ id: '1' }])
    queryClient.setQueryData(['context', 'aaa'], { id: 'org' })
    queryClient.setQueryData(['me'], { id: 'me' })
    clearTenantQueries()
    expect(queryClient.getQueryData(['members', 'aaa'])).toBeUndefined()
    expect(queryClient.getQueryData(['context', 'aaa'])).toBeUndefined()
    expect(queryClient.getQueryData(['me'])).toEqual({ id: 'me' })
  })
})
