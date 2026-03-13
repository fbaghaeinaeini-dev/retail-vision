import { useEffect, useRef, useCallback } from "react";

const SCRIPT_ID = "cf-turnstile-script";
const SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

// Site key — replace with your Cloudflare Turnstile site key
export const TURNSTILE_SITE_KEY = "0x4AAAAAACpcs5bYe7knNtua";

/**
 * Cloudflare Turnstile widget.
 *
 * Props:
 *  - onVerify(token)  — called when the user passes the challenge
 *  - onExpire()       — called when the token expires (optional)
 *  - onError()        — called on widget error (optional)
 */
export default function Turnstile({ onVerify, onExpire, onError }) {
  const containerRef = useRef(null);
  const widgetIdRef = useRef(null);

  const render = useCallback(() => {
    if (!containerRef.current || !window.turnstile) return;
    // Avoid double-render
    if (widgetIdRef.current !== null && widgetIdRef.current !== undefined) return;
    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey: TURNSTILE_SITE_KEY,
      callback: onVerify,
      "expired-callback": onExpire,
      "error-callback": onError,
      theme: "dark",
      size: "flexible",
    });
  }, [onVerify, onExpire, onError]);

  useEffect(() => {
    // Load the Turnstile script if not present
    if (!document.getElementById(SCRIPT_ID)) {
      const script = document.createElement("script");
      script.id = SCRIPT_ID;
      script.src = SCRIPT_URL;
      script.async = true;
      script.defer = true;
      script.onload = render;
      document.head.appendChild(script);
    } else if (window.turnstile) {
      render();
    } else {
      // Script tag exists but hasn't loaded yet — wait for it
      const existing = document.getElementById(SCRIPT_ID);
      existing.addEventListener("load", render);
      return () => existing.removeEventListener("load", render);
    }
  }, [render]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (widgetIdRef.current != null && window.turnstile) {
        try { window.turnstile.remove(widgetIdRef.current); } catch {}
        widgetIdRef.current = null;
      }
    };
  }, []);

  return <div ref={containerRef} className="flex justify-center" />;
}

/** Reset / re-render the widget (call after form submission). */
export function resetTurnstile() {
  if (window.turnstile) {
    window.turnstile.reset();
  }
}
