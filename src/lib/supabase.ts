// Supabase client helpers.
// - `getBrowserClient()`: browser-side, uses anonymous key.
// - `getBuildClient()`: Node/SSR build-time, prefers service_role when available.

import { createClient } from '@supabase/supabase-js';

let browserClient: ReturnType<typeof createClient> | null = null;
let buildClient: ReturnType<typeof createClient> | null = null;

export function getBrowserClient() {
  if (browserClient) return browserClient;
  const url = import.meta.env.PUBLIC_SUPABASE_URL as string | undefined;
  const anon = import.meta.env.PUBLIC_SUPABASE_ANON_KEY as string | undefined;
  if (!url || !anon) {
    // Returning null signals the UI to degrade gracefully.
    return null;
  }
  browserClient = createClient(url, anon, {
    auth: { persistSession: false },
  });
  return browserClient;
}

export function getBuildClient() {
  if (buildClient) return buildClient;
  const url = (import.meta.env.PUBLIC_SUPABASE_URL ?? process.env.PUBLIC_SUPABASE_URL) as
    | string
    | undefined;
  const serviceKey = (import.meta.env.SUPABASE_SERVICE_ROLE_KEY ??
    process.env.SUPABASE_SERVICE_ROLE_KEY) as string | undefined;
  const anon = (import.meta.env.PUBLIC_SUPABASE_ANON_KEY ??
    process.env.PUBLIC_SUPABASE_ANON_KEY) as string | undefined;
  if (!url) return null as any;
  buildClient = createClient(url, (serviceKey ?? anon) as string, {
    auth: { persistSession: false },
  });
  return buildClient;
}
