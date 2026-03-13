import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { supabase } from "../lib/supabase";

/**
 * Client-side email verification page.
 *
 * The email link points here instead of Supabase's /auth/v1/verify endpoint.
 * This makes verification Safe-Links-proof: corporate email scanners pre-fetch
 * the URL but don't execute JavaScript, so the one-time token survives until
 * the real user opens the page in their browser.
 */
export default function VerifyPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("verifying"); // verifying | success | error
  const [errorMsg, setErrorMsg] = useState("");

  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type"); // signup | recovery | email_change

  useEffect(() => {
    if (!tokenHash || !type) {
      setStatus("error");
      setErrorMsg("Invalid verification link — missing token or type.");
      return;
    }

    let cancelled = false;

    async function verify() {
      const { data, error } = await supabase.auth.verifyOtp({
        token_hash: tokenHash,
        type,
      });

      if (cancelled) return;

      if (error) {
        setStatus("error");
        setErrorMsg(error.message);
        return;
      }

      setStatus("success");

      // For signup and recovery, redirect to set-password page
      // The session is now active, so SetPasswordPage will detect it
      if (type === "signup" || type === "recovery") {
        setTimeout(() => {
          if (!cancelled) navigate("/set-password", { replace: true });
        }, 1200);
      } else {
        // For other types (email_change etc.), go to chat
        setTimeout(() => {
          if (!cancelled) navigate("/chat", { replace: true });
        }, 1200);
      }
    }

    verify();
    return () => { cancelled = true; };
  }, [tokenHash, type, navigate]);

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent-orange/20 border border-accent-orange/30 mb-4">
            <span className="text-[10px] font-bold text-accent-orange leading-tight text-center whitespace-pre">
              {"Vision\nAI"}
            </span>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            {status === "verifying" && "Verifying your email..."}
            {status === "success" && "Email verified!"}
            {status === "error" && "Verification failed"}
          </h1>
        </div>

        <div className="bg-bg-card border border-border rounded-2xl p-6">
          {status === "verifying" && (
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
              <p className="text-xs text-text-secondary">
                Confirming your email address...
              </p>
            </div>
          )}

          {status === "success" && (
            <div className="flex flex-col items-center gap-3 py-4 text-center">
              <svg className="w-10 h-10 text-accent-green" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
              <p className="text-sm text-text-primary font-medium">
                Your email has been verified
              </p>
              <p className="text-xs text-text-secondary">
                Redirecting you to set your password...
              </p>
            </div>
          )}

          {status === "error" && (
            <div className="flex flex-col items-center gap-3 py-4 text-center">
              <svg className="w-10 h-10 text-accent-red" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
              </svg>
              <p className="text-sm text-text-primary font-medium">
                {errorMsg || "Something went wrong"}
              </p>
              <p className="text-xs text-text-secondary mt-1">
                The link may have expired. You can request a new one from the login page.
              </p>
              <a
                href="/"
                className="mt-3 px-4 py-2 rounded-lg bg-accent-orange text-white text-xs font-medium hover:bg-accent-orange/90 transition-colors"
              >
                Back to login
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
