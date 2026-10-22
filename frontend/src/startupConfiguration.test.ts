import { describe, expect, it } from 'vitest'
import { resolveConfig } from 'vite'
import path from 'node:path'

describe('frontend/backend host compatibility', () => {
  it.each(['::1', '[::1]', '::'])('builds valid bind and proxy addresses for %s', async host => {
    const previous = process.env.HOST
    process.env.HOST = host
    try {
      const config = await resolveConfig({ configFile: path.resolve('vite.config.ts') }, 'serve')
      const proxy = config.server.proxy!['/api'] as { target: string }
      const target = new URL(proxy.target)
      expect(target.hostname).toBe(host === '::' ? '127.0.0.1' : '[::1]')
      expect(config.server.host).toBe(host === '[::1]' ? '::1' : host)
    } finally {
      if (previous === undefined) delete process.env.HOST
      else process.env.HOST = previous
    }
  })
})
