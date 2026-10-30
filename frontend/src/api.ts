export const getToken = () => localStorage.getItem('token')
export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; headers?: Record<string, string> } = {}): Promise<T> {
  const r = await fetch('/api' + path, {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}), ...(opts.headers || {}) },
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  })
  if (r.status === 401 && path !== '/auth/login') { localStorage.removeItem('token'); location.reload() }
  const data = await r.json().catch(() => ({}))
  if (!r.ok) {
    const d = data.detail
    const msg = typeof d === 'string' ? d : typeof d?.mensaje === 'string' ? d.mensaje : JSON.stringify(d ?? r.status)
    throw Object.assign(new Error(msg), { status: r.status, detail: d })
  }
  return data
}
