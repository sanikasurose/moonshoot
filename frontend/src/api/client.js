// ponytail: plain fetch wrapper; add axios only if interceptors become necessary
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${sessionStorage.getItem('jwt') || ''}`,
      ...options.headers,
    },
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}
