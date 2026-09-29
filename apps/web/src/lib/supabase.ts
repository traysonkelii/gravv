import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string

if (!url || !key) {
  console.warn('VITE_SUPABASE_URL or VITE_SUPABASE_PUBLISHABLE_KEY is missing; run `make env`.')
}

export const supabase = createClient(url ?? 'http://127.0.0.1:54321', key ?? 'missing', {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    flowType: 'pkce',
  },
})
