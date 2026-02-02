/**
 * Authenticated API helper for LeadSynergy.
 *
 * Sends the Supabase JWT access token in the Authorization header and the
 * user ID in X-User-ID for backward compatibility with the backend during
 * migration.
 */

import { createClient } from "@/lib/supabase/client"

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"

/**
 * Build the standard auth headers for API calls.
 *
 * Returns headers object with:
 * - Authorization: Bearer <jwt> (for verified auth)
 * - X-User-ID: <user_id> (backward compat)
 *
 * Returns null if the user is not authenticated.
 */
export async function getAuthHeaders(): Promise<Record<string, string> | null> {
  try {
    const supabase = createClient()
    const {
      data: { session },
    } = await supabase.auth.getSession()

    if (!session?.user) return null

    return {
      Authorization: `Bearer ${session.access_token}`,
      "X-User-ID": session.user.id,
    }
  } catch {
    return null
  }
}

/**
 * Make an authenticated fetch call to the backend API.
 *
 * Automatically includes auth headers. Returns null if the user is not
 * authenticated.
 */
export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response | null> {
  const headers = await getAuthHeaders()
  if (!headers) return null

  const mergedHeaders = {
    ...headers,
    ...(options.headers || {}),
  }

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: mergedHeaders,
  })
}
