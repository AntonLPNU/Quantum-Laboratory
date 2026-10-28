export type ApiEnvelope<T = unknown> = Readonly<{
  kind: string;
  route: string;
  configuration: Record<string, unknown>;
  provenance: { engine: string; application_version: string };
  result: T;
}>;

export class ApiConnectionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiConnectionError';
  }
}

/** Sends a typed JSON request to the same-origin Python API and normalizes connection failures. */
export async function api<T = any>(route: string, body?: unknown): Promise<T> {
  try {
    const response = await fetch(route, body === undefined ? { headers: { Accept: 'application/json' } } : {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data?.error?.message ?? `HTTP ${response.status}`);
    return data as T;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiConnectionError(`Не вдалося з’єднатися з локальним API (${window.location.origin}). Перезапустіть Quantum Laboratory; якщо проблема повториться, перевірте журнал запуску.`);
    }
    throw error;
  }
}
