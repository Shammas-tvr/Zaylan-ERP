import { describe, expect, it } from 'vitest'

import { queryKeys } from './queryClient'

describe('query keys', () => {
  it('scopes tenant data by organization id', () => {
    expect(queryKeys.members('aaa')[1]).toBe('aaa')
    expect(queryKeys.members('aaa')).not.toEqual(queryKeys.members('bbb'))
    expect(queryKeys.context('aaa')[0]).toBe('tenant')
  })
})
