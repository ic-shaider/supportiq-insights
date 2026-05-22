import { useState, useEffect, useCallback } from 'react'
const API = '/api/v1'
export function useApi<T>(endpoint: string, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}${endpoint}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
    } catch (err: any) { setError(err.message) } finally { setLoading(false) }
  }, [endpoint])
  useEffect(() => { fetchData() }, [fetchData, ...deps])
  return { data, loading, error, refetch: fetchData }
}
export async function apiPost<T>(endpoint: string, body?: any): Promise<T> {
  const res = await fetch(`${API}${endpoint}`, {
    method: 'POST', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
