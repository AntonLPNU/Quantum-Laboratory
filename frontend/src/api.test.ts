import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiConnectionError, api } from './api';

describe('local API transport', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('explains how to recover from a same-origin network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(api('/api/health')).rejects.toBeInstanceOf(ApiConnectionError);
    await expect(api('/api/health')).rejects.toThrow(/локальним API.*Перезапустіть Quantum Laboratory/);
  });

  it('retains structured server errors from the Python API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ error: { message: 'invalid observable' } }),
    }));
    await expect(api('/api/analyze/observable', {})).rejects.toThrow('invalid observable');
  });
});
