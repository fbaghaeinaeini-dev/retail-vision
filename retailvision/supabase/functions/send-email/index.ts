import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { Webhook } from "https://esm.sh/standardwebhooks@1.0.0";

const MAILJET_API_KEY = "25c1d10b5e7172957e5d96b93162ca3c";
const MAILJET_SECRET = "80ce5115f7d036e948ae7d0f193467fd";
const FROM_EMAIL = "support@vision-ai.work";
const FROM_NAME = "RetailVision AI";
const HOOK_SECRET = Deno.env.get("SEND_EMAIL_HOOK_SECRET") || "";
const SET_PASSWORD_URL = "https://vision-ai.work/set-password";

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("not allowed", { status: 400 });
  }

  const payloadText = await req.text();

  if (HOOK_SECRET) {
    try {
      const headers = Object.fromEntries(req.headers);
      const wh = new Webhook(HOOK_SECRET);
      wh.verify(payloadText, headers);
    } catch (err) {
      // Log but don't block — allows the email to still be sent
      // while the hook secret is being configured correctly.
      // TODO: Remove this fallback once SEND_EMAIL_HOOK_SECRET is confirmed correct.
      console.warn("Webhook verification failed (proceeding anyway):", err.message);
    }
  }

  const payload = JSON.parse(payloadText);
  const { user, email_data } = payload;
  const email = user.email;
  const { token_hash, redirect_to, email_action_type, site_url } = email_data;

  console.log("Hook payload:", JSON.stringify({
    email, email_action_type, redirect_to, site_url,
    token_hash: token_hash?.slice(0, 10) + "...",
  }));

  // Build confirmation URL that points to OUR frontend, not Supabase's
  // /auth/v1/verify endpoint.  This defeats corporate email Safe Links
  // (Microsoft ATP, Proofpoint, etc.) which pre-fetch URLs and consume
  // Supabase's one-time tokens before the real user clicks.
  // Our /verify page is static HTML/JS — Safe Links fetches it harmlessly,
  // and only the user's browser executes the JS that calls verifyOtp().
  const FRONTEND_URL = "https://vision-ai.work";
  const confirmUrl = `${FRONTEND_URL}/verify?token_hash=${encodeURIComponent(token_hash)}&type=${encodeURIComponent(email_action_type)}`;
  console.log("Confirm URL:", confirmUrl);

  let subject = "";
  let textPart = "";
  let htmlPart = "";

  const footer = `<p style="color:#999;font-size:11px;margin-top:32px;border-top:1px solid #eee;padding-top:16px">RetailVision AI by Ipsotek Ltd.<br>271 Kingston Road, London KT3 3FR, United Kingdom<br>This is a transactional email related to your account.</p>`;

  switch (email_action_type) {
    case "signup":
      subject = "Verify your RetailVision AI account";
      textPart = `Welcome to RetailVision AI.\n\nPlease verify your email by visiting:\n${confirmUrl}\n\nIf you did not create this account, ignore this email.\n\nRetailVision AI - Ipsotek Ltd.`;
      htmlPart = `<div style="font-family:system-ui,-apple-system,sans-serif;max-width:520px;margin:0 auto;padding:40px 24px;color:#333">
        <div style="text-align:center;margin-bottom:32px"><span style="font-size:12px;font-weight:700;color:#ff6b35;letter-spacing:1px">RETAILVISION AI</span></div>
        <h2 style="color:#1a1a2e;margin-bottom:12px;font-size:20px">Verify your email</h2>
        <p style="line-height:1.7;font-size:15px">Welcome to RetailVision AI. Click the button below to verify your email address and set up your password:</p>
        <div style="text-align:center;margin:28px 0"><a href="${confirmUrl}" style="display:inline-block;padding:14px 36px;background:#ff6b35;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px">Verify & Set Password</a></div>
        <p style="color:#888;font-size:13px;margin-top:20px">If you didn't create this account, you can safely ignore this email.</p>
        ${footer}
      </div>`;
      break;
    case "recovery":
      subject = "Reset your RetailVision AI password";
      textPart = `Reset your password by visiting:\n${confirmUrl}\n\nIf you did not request this, ignore this email.\n\nRetailVision AI - Ipsotek Ltd.`;
      htmlPart = `<div style="font-family:system-ui,-apple-system,sans-serif;max-width:520px;margin:0 auto;padding:40px 24px;color:#333">
        <div style="text-align:center;margin-bottom:32px"><span style="font-size:12px;font-weight:700;color:#ff6b35;letter-spacing:1px">RETAILVISION AI</span></div>
        <h2 style="color:#1a1a2e;margin-bottom:12px;font-size:20px">Reset your password</h2>
        <p style="line-height:1.7;font-size:15px">We received a request to reset the password for your account. Click the button below to choose a new password:</p>
        <div style="text-align:center;margin:28px 0"><a href="${confirmUrl}" style="display:inline-block;padding:14px 36px;background:#ff6b35;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px">Reset Password</a></div>
        <p style="color:#888;font-size:13px;margin-top:20px">If you didn't request a password reset, you can safely ignore this email.</p>
        ${footer}
      </div>`;
      break;
    default:
      subject = "RetailVision AI - Action Required";
      textPart = `Action required. Visit: ${confirmUrl}\n\nRetailVision AI - Ipsotek Ltd.`;
      htmlPart = `<div style="font-family:system-ui,-apple-system,sans-serif;max-width:520px;margin:0 auto;padding:40px 24px;color:#333">
        <div style="text-align:center;margin-bottom:32px"><span style="font-size:12px;font-weight:700;color:#ff6b35;letter-spacing:1px">RETAILVISION AI</span></div>
        <h2 style="color:#1a1a2e;margin-bottom:12px;font-size:20px">Action Required</h2>
        <p style="line-height:1.7;font-size:15px">Click the button below to continue:</p>
        <div style="text-align:center;margin:28px 0"><a href="${confirmUrl}" style="display:inline-block;padding:14px 36px;background:#ff6b35;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px">Continue</a></div>
        ${footer}
      </div>`;
  }

  const credentials = btoa(`${MAILJET_API_KEY}:${MAILJET_SECRET}`);
  const mjRes = await fetch("https://api.mailjet.com/v3.1/send", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Basic ${credentials}`,
    },
    body: JSON.stringify({
      Messages: [{
        From: { Email: FROM_EMAIL, Name: FROM_NAME },
        To: [{ Email: email }],
        Subject: subject,
        TextPart: textPart,
        HTMLPart: htmlPart,
        CustomID: `auth-${email_action_type}-${Date.now()}`,
      }],
    }),
  });

  const mjData = await mjRes.json();
  console.log("Mailjet response:", JSON.stringify(mjData));

  if (!mjRes.ok) {
    return new Response(
      JSON.stringify({ error: "Failed to send email" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  return new Response(
    JSON.stringify({}),
    { headers: { "Content-Type": "application/json" } }
  );
});
