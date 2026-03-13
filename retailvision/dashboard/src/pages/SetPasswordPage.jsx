import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import Turnstile, { resetTurnstile, TURNSTILE_SITE_KEY } from "../components/Turnstile";

const hasTurnstile = TURNSTILE_SITE_KEY && !TURNSTILE_SITE_KEY.startsWith("__");

export default function SetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [expired, setExpired] = useState(false);
  const [resendEmail, setResendEmail] = useState("");
  const [resendSent, setResendSent] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    // Listen for auth events from URL hash processing
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (cancelled) return;
      if (session) {
        setReady(true);
        setExpired(false);
      }
    });

    // Poll for session — handles case where event already fired
    async function checkSession() {
      for (let i = 0; i < 20; i++) {
        if (cancelled) return;
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
          setReady(true);
          return;
        }
        await new Promise((r) => setTimeout(r, 500));
      }
      // Timeout — link is expired or invalid
      if (!cancelled) {
        setExpired(true);
        setReady(true);
      }
    }
    checkSession();

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, []);

  async function handleResend(e) {
    e.preventDefault();
    setError("");
    if (!resendEmail) return setError("Please enter your email address.");
    if (hasTurnstile && !captchaToken) return setError("Please complete the security check.");
    setLoading(true);

    const { error: err } = await supabase.auth.resend({
      type: "signup",
      email: resendEmail,
      options: {
        emailRedirectTo: `${window.location.origin}/set-password`,
        ...(hasTurnstile && { captchaToken }),
      },
    });

    if (err) {
      setError(err.message);
    } else {
      setResendSent(true);
    }
    setCaptchaToken("");
    resetTurnstile();
    setLoading(false);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!password) return setError("Password is required.");
    if (password.length < 6) return setError("Password must be at least 6 characters.");
    if (password !== confirm) return setError("Passwords do not match.");

    setLoading(true);
    const { error: err } = await supabase.auth.updateUser({ password });
    if (err) {
      setError(err.message);
      setLoading(false);
    } else {
      navigate("/chat", { replace: true });
    }
  }

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
            {expired ? "Link expired" : "Set your password"}
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            {expired
              ? "Your verification link has expired or was already used"
              : "Choose a password for your account"}
          </p>
        </div>

        <div className="bg-bg-card border border-border rounded-2xl p-6">
          {!ready ? (
            /* ── Loading / verifying ── */
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
              <p className="text-xs text-text-secondary">Verifying your email...</p>
            </div>
          ) : expired ? (
            /* ── Expired link: show resend form ── */
            resendSent ? (
              <div className="flex flex-col items-center gap-3 py-4 text-center">
                <svg className="w-10 h-10 text-accent-green" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                </svg>
                <p className="text-sm text-text-primary font-medium">New link sent!</p>
                <p className="text-xs text-text-secondary">
                  Check your inbox for a fresh verification link. Click it within 1 hour.
                </p>
                <a href="/" className="text-xs text-accent-cyan hover:underline mt-2">
                  Back to login
                </a>
              </div>
            ) : (
              <form onSubmit={handleResend} className="flex flex-col gap-3">
                <p className="text-xs text-text-secondary mb-1">
                  This can happen if the link was clicked by an email security scanner,
                  or if too much time passed. Enter your email to receive a new link.
                </p>
                <div>
                  <label className="block text-[11px] text-text-secondary mb-1">Email</label>
                  <input
                    type="email"
                    value={resendEmail}
                    onChange={(e) => setResendEmail(e.target.value)}
                    placeholder="name@ipsotek.com"
                    className="w-full px-3 py-2 rounded-lg bg-bg-primary border border-border text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:border-accent-cyan transition-colors"
                    autoComplete="email"
                    autoFocus
                  />
                </div>
                {hasTurnstile && (
                  <Turnstile
                    onVerify={(token) => setCaptchaToken(token)}
                    onExpire={() => setCaptchaToken("")}
                  />
                )}
                {error && (
                  <p className="text-xs text-accent-red bg-accent-red/10 border border-accent-red/20 rounded-lg px-3 py-2">{error}</p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 rounded-lg bg-accent-orange text-white text-sm font-medium hover:bg-accent-orange/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-1"
                >
                  {loading ? "Sending..." : "Resend verification link"}
                </button>
                <a href="/" className="text-xs text-accent-cyan hover:underline text-center mt-1">
                  Back to login
                </a>
              </form>
            )
          ) : (
            /* ── Valid session: set password form ── */
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div>
                <label className="block text-[11px] text-text-secondary mb-1">New password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 6 characters"
                  className="w-full px-3 py-2 rounded-lg bg-bg-primary border border-border text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:border-accent-cyan transition-colors"
                  autoComplete="new-password"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-[11px] text-text-secondary mb-1">Confirm password</label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repeat password"
                  className="w-full px-3 py-2 rounded-lg bg-bg-primary border border-border text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:border-accent-cyan transition-colors"
                  autoComplete="new-password"
                />
              </div>
              {error && (
                <p className="text-xs text-accent-red bg-accent-red/10 border border-accent-red/20 rounded-lg px-3 py-2">{error}</p>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-accent-orange text-white text-sm font-medium hover:bg-accent-orange/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-1"
              >
                {loading ? "Saving..." : "Set password & continue"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
