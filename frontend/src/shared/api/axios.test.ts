import axios from 'axios'
import MockAdapter from 'axios-mock-adapter'
import { beforeEach, describe, expect, it } from 'vitest'

import { clearSession, getAccessToken, setAccessToken, setOrganizationId } from '../session'
import { api, refreshAccessToken } from './axios'

describe('axios client', () => {
  beforeEach(() => {
    clearSession()
  })

  it('attaches the access token and organization header', async () => {
    const mock = new MockAdapter(api)
    setAccessToken('access-1')
    setOrganizationId('org-1')
    mock.onGet('/me/').reply((config) => {
      expect(config.headers?.Authorization).toBe('Bearer access-1')
      expect(config.headers?.['X-Organization-ID']).toBe('org-1')
      return [200, { id: 'u1', email: 'a@example.com', full_name: 'A' }]
    })
    await api.get('/me/')
    mock.restore()
  })

  it('single-flights refresh so concurrent 401s share one retry', async () => {
    const root = new MockAdapter(axios)
    root.onPost(/\/auth\/refresh$/).replyOnce(200, {
      access: 'access-2',
      user: { id: 'u1', email: 'a@example.com', full_name: 'A' },
    })
    const first = refreshAccessToken()
    const second = refreshAccessToken()
    await expect(Promise.all([first, second])).resolves.toEqual(['access-2', 'access-2'])
    expect(getAccessToken()).toBe('access-2')
    expect(root.history.post).toHaveLength(1)
    root.restore()
  })
})
