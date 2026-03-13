import { useState, useCallback } from "react";
import { supabase, isAllowedEmail, ALLOWED_DOMAIN } from "../lib/supabase";
import Turnstile, { resetTurnstile, TURNSTILE_SITE_KEY } from "../components/Turnstile";

const TABS = ["Sign in", "Register"];
const hasTurnstile = TURNSTILE_SITE_KEY && !TURNSTILE_SITE_KEY.startsWith("__");

export default function LoginPage() {
  const [tab, setTab] = useState(0); // 0=login, 1=register
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [showResend, setShowResend] = useState(false);

  const onCaptchaVerify = useCallback((token) => setCaptchaToken(token), []);
  const onCaptchaExpire = useCallback(() => setCaptchaToken(""), []);

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    if (!email || !password) return setError("Email and password are required.");
    if (hasTurnstile && !captchaToken) return setError("Please complete the security check.");
    setLoading(true);
    const { error: err } = await supabase.auth.signInWithPassword({
      email,
      password,
      options: hasTurnstile ? { captchaToken } : undefined,
    });
    if (err) {
      setError(err.message);
      // Show resend option if email isn't confirmed
      if (err.message.toLowerCase().includes("not confirmed") || err.message.toLowerCase().includes("not verified")) {
        setShowResend(true);
      }
    }
    setCaptchaToken("");
    resetTurnstile();
    setLoading(false);
  }

  async function handleResendVerification() {
    setError("");
    setInfo("");
    if (!email) return setError("Please enter your email first.");
    if (hasTurnstile && !captchaToken) return setError("Please complete the security check.");
    setLoading(true);
    const { error: err } = await supabase.auth.resend({
      type: "signup",
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/set-password`,
        ...(hasTurnstile && { captchaToken }),
      },
    });
    if (err) {
      setError(err.message);
    } else {
      setInfo("Verification link sent! Check your inbox.");
      setShowResend(false);
    }
    setCaptchaToken("");
    resetTurnstile();
    setLoading(false);
  }

  async function handleRegister(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (!email) return setError("Email is required.");
    if (!isAllowedEmail(email)) {
      return setError(`Only @${ALLOWED_DOMAIN} email addresses can register.`);
    }
    if (hasTurnstile && !captchaToken) return setError("Please complete the security check.");
    setLoading(true);
    const tempPassword = crypto.randomUUID() + "Aa1!";
    const redirectUrl = `${window.location.origin}/set-password`;
    const { error: err } = await supabase.auth.signUp({
      email,
      password: tempPassword,
      options: {
        emailRedirectTo: redirectUrl,
        ...(hasTurnstile && { captchaToken }),
      },
    });
    if (err) {
      setError(err.message);
    } else {
      setInfo("Check your inbox — we've sent a link to set your password.");
    }
    setCaptchaToken("");
    resetTurnstile();
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo / Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent-orange/20 border border-accent-orange/30 mb-4">
            <span className="text-[10px] font-bold text-accent-orange leading-tight text-center whitespace-pre">
              {"Vision\nAI"}
            </span>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            RetailVision AI
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Agentic Analytics Platform
          </p>
        </div>

        {/* Form card */}
        <div className="bg-bg-card border border-border rounded-2xl overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-border">
            {TABS.map((label, i) => (
              <button
                key={label}
                onClick={() => { setTab(i); setError(""); setInfo(""); setCaptchaToken(""); setShowResend(false); resetTurnstile(); }}
                className={`flex-1 py-3 text-xs font-medium transition-colors cursor-pointer ${
                  tab === i
                    ? "text-accent-orange border-b-2 border-accent-orange"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="p-6">
            {/* ── Sign in tab ── */}
            {tab === 0 && (
              <form onSubmit={handleLogin} className="flex flex-col gap-3">
                <div>
                  <label className="block text-[11px] text-text-secondary mb-1">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={`name@${ALLOWED_DOMAIN}`}
                    className="w-full px-3 py-2 rounded-lg bg-bg-primary border border-border text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:border-accent-cyan transition-colors"
                    autoComplete="email"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-text-secondary mb-1">Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    className="w-full px-3 py-2 rounded-lg bg-bg-primary border border-border text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:border-accent-cyan transition-colors"
                    autoComplete="current-password"
                  />
                </div>
                {hasTurnstile && (
                  <Turnstile onVerify={onCaptchaVerify} onExpire={onCaptchaExpire} />
                )}
                {error && (
                  <p className="text-xs text-accent-red bg-accent-red/10 border border-accent-red/20 rounded-lg px-3 py-2">{error}</p>
                )}
                {showResend && (
                  <button
                    type="button"
                    onClick={handleResendVerification}
                    disabled={loading}
                    className="w-full py-2 rounded-lg border border-accent-cyan/30 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/10 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    Resend verification email
                  </button>
                )}
                {info && (
                  <p className="text-xs text-accent-green bg-accent-green/10 border border-accent-green/20 rounded-lg px-3 py-2">{info}</p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 rounded-lg bg-accent-orange text-white text-sm font-medium hover:bg-accent-orange/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-1"
                >
                  {loading ? "Please wait..." : "Sign in"}
                </button>
              </form>
            )}

            {/* ── Register tab ── */}
            {tab === 1 && (
              <form onSubmit={handleRegister} className="flex flex-col gap-3">
                <p className="text-xs text-text-secondary mb-1">
                  Enter your company email and we'll send a link to set up your account.
                </p>
                <div>
                  <label className="block text-[11px] text-text-secondary mb-1">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={`name@${ALLOWED_DOMAIN}`}
                    className="w-full px-3 py-2 rounded-lg bg-bg-primary border border-border text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:border-accent-cyan transition-colors"
                    autoComplete="email"
                  />
                </div>
                {hasTurnstile && (
                  <Turnstile onVerify={onCaptchaVerify} onExpire={onCaptchaExpire} />
                )}
                {error && (
                  <p className="text-xs text-accent-red bg-accent-red/10 border border-accent-red/20 rounded-lg px-3 py-2">{error}</p>
                )}
                {info && (
                  <p className="text-xs text-accent-green bg-accent-green/10 border border-accent-green/20 rounded-lg px-3 py-2">{info}</p>
                )}
                <button
                  type="submit"
                  disabled={loading || !!info}
                  className="w-full py-2.5 rounded-lg bg-accent-orange text-white text-sm font-medium hover:bg-accent-orange/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-1"
                >
                  {loading ? "Sending..." : "Send setup link"}
                </button>
                <p className="text-[10px] text-text-secondary text-center mt-1">
                  Restricted to @{ALLOWED_DOMAIN} addresses.
                </p>
                {info && (
                  <button
                    type="button"
                    onClick={handleResendVerification}
                    disabled={loading}
                    className="w-full py-2 rounded-lg border border-border text-text-secondary text-xs font-medium hover:text-accent-cyan hover:border-accent-cyan/30 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    Link expired? Resend verification email
                  </button>
                )}
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
