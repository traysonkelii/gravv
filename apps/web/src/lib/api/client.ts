import createClient, { type Middleware } from 'openapi-fetch'
import type { paths } from '@/lib/api/schema'
import { useUiStore } from '@/lib/store'
import { supabase } from '@/lib/supabase'

export type Problem = {
  type: string
  title: string
  status: number
  detail?: string
  instance?: string
  request_id?: string
  errors?: { field: string; message: string }[]
}

export class ApiError extends Error {
  problem: Problem
  constructor(problem: Problem) {
    super(problem.title)
    this.problem = problem
  }
}

const baseUrl = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://127.0.0.1:8000'

async function accessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

/* Injects the bearer token and workspace header. On 401, refreshes the session and retries once,
   then signs out. */
async function fetchWithAuth(input: Request): Promise<Response> {
  const res = await fetch(input.clone())
  if (res.status !== 401) return res
  const { data } = await supabase.auth.refreshSession()
  if (!data.session) {
    await supabase.auth.signOut()
    return res
  }
  const headers = new Headers(input.headers)
  headers.set('Authorization', `Bearer ${data.session.access_token}`)
  return fetch(new Request(input, { headers }))
}

const auth: Middleware = {
  async onRequest({ request }) {
    const token = await accessToken()
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    const ws = useUiStore.getState().workspaceId
    if (ws) request.headers.set('X-Workspace-Id', ws)
    return request
  },
}

export const api = createClient<paths>({ baseUrl, fetch: fetchWithAuth })
api.use(auth)

/* Unwraps an openapi-fetch result: returns data or throws ApiError with the Problem body. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const problem = (result.error as Problem | undefined) ?? {
      type: 'https://gravv.app/problems/unknown',
      title: 'Request failed',
      status: result.response.status,
    }
    throw new ApiError(problem)
  }
  return result.data as T
}
