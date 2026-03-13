import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = "https://otjczdatmzdwhnsnnduh.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im90amN6ZGF0bXpkd2huc25uZHVoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMyNzA2ODcsImV4cCI6MjA4ODg0NjY4N30.b6FPvA2lkAzhILlDijtlpWw7FnxMmk2oKiKS_QT5GaM";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

/** Only @ipsotek.com emails can register. */
export const ALLOWED_DOMAIN = "ipsotek.com";

export function isAllowedEmail(email) {
  return email.toLowerCase().endsWith(`@${ALLOWED_DOMAIN}`);
}
