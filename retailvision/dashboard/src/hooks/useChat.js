import { useState, useRef, useCallback } from "react";
import { supabase } from "../lib/supabase";

/**
 * Custom hook for managing chat state with SSE streaming.
 *
 * Connects to the /api/chat endpoint, sends user messages,
 * and streams back AI responses with optional visualization payloads.
 *
 * Text updates are debounced via requestAnimationFrame (~16ms) so rapid
 * token-level SSE events don't trigger a React re-render per token.
 */
export function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastActions, setLastActions] = useState([]);
  const [toolStatus, setToolStatus] = useState(null);
  const [streamPhase, setStreamPhase] = useState("idle"); // idle | thinking | streaming | preparing
  const sessionIdRef = useRef(null);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return;

    const userMsg = {
      id: crypto.randomUUID(),
      role: "user",
      content: text.trim(),
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setToolStatus(null);
    setStreamPhase("thinking");
    setError(null);

    // ── Declared before try so finally can always access them ──
    let preparingTimer = null;
    const resetPreparingTimer = () => {
      if (preparingTimer) clearTimeout(preparingTimer);
      preparingTimer = setTimeout(() => {
        setStreamPhase("preparing");
      }, 400);
    };
    const clearPreparingTimer = () => {
      if (preparingTimer) { clearTimeout(preparingTimer); preparingTimer = null; }
    };

    // ── Stream activity timeout via AbortController ────────
    // If nothing arrives for 60s, abort the fetch so catch/finally run
    const abortController = new AbortController();
    let activityTimer = null;
    const resetActivityTimer = () => {
      if (activityTimer) clearTimeout(activityTimer);
      activityTimer = setTimeout(() => {
        abortController.abort();
      }, 60_000);
    };
    const clearActivityTimer = () => {
      if (activityTimer) { clearTimeout(activityTimer); activityTimer = null; }
    };

    let assistantContent = "";
    let visualizations = [];
    let primaryViz = "";
    let flushPending = false;
    let assistantId = null;

    const scheduleFlush = () => {
      if (flushPending || !assistantId) return;
      flushPending = true;
      requestAnimationFrame(() => {
        flushPending = false;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: assistantContent,
                  visualizations: [...visualizations],
                  primaryViz,
                }
              : m,
          ),
        );
      });
    };

    try {
      const body = { message: text.trim() };
      if (sessionIdRef.current) {
        body.session_id = sessionIdRef.current;
      }

      // Get current Supabase access token for API auth
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token || "";

      resetActivityTimer();
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify(body),
        signal: abortController.signal,
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let actions = [];
      let buffer = "";

      assistantId = crypto.randomUUID();

      // Add placeholder assistant message
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          visualizations: [],
          timestamp: Date.now(),
        },
      ]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        resetActivityTimer();
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines from buffer
        const lines = buffer.split("\n");
        // Keep the last partial line in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data:")) continue;

          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr || jsonStr === "[DONE]") continue;

          try {
            const data = JSON.parse(jsonStr);

            // Capture session id
            if (data.session_id) {
              sessionIdRef.current = data.session_id;
            }

            // Accumulate text chunks — switch to streaming phase
            if (data.type === "text" && data.content) {
              assistantContent += data.content;
              setToolStatus(null);
              setStreamPhase("streaming");
              resetPreparingTimer();
              scheduleFlush();
            }

            // Collect visualization payloads — results are ready
            if (data.type === "visualization" && data.visualization) {
              visualizations = [...visualizations, data.visualization];
              clearPreparingTimer();
              setStreamPhase("idle");
              scheduleFlush();
            }

            // Primary viz hint
            if (data.type === "primary_viz" && data.viz_type) {
              primaryViz = data.viz_type;
            }

            // Tool status (transient — for loading indicator)
            if (data.type === "tool_status") {
              setToolStatus(data.tool ? { tool: data.tool, message: data.message } : null);
              setStreamPhase("thinking");
            }

            // Collect action payloads
            if (data.type === "action" && data.action) {
              actions.push(data.action);
            }

            // Handle errors from the stream
            if (data.type === "error") {
              const streamErr = new Error(data.content || "Stream error");
              streamErr._isStreamError = true;
              throw streamErr;
            }
          } catch (parseErr) {
            // If it's a stream error we threw, re-throw to outer catch
            if (parseErr._isStreamError) {
              throw parseErr;
            }
            // Otherwise ignore malformed SSE data lines
          }
        }
      }

      // Final update with complete content (ensure nothing is lost)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: assistantContent || "I received your message but had no response to generate.",
                visualizations,
                primaryViz,
              }
            : m,
        ),
      );

      // Set collected actions after stream completes
      setLastActions(actions);
    } catch (err) {
      const message = err.name === "AbortError"
        ? "Connection timed out. Please try again."
        : err.message || "Something went wrong. Please try again.";
      const errorMsg = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: message,
        error: true,
        timestamp: Date.now(),
      };
      setMessages((prev) => {
        // Remove placeholder assistant message if it exists with empty content
        const cleaned = prev.filter(
          (m) => !(m.role === "assistant" && m.content === "" && !m.error),
        );
        return [...cleaned, errorMsg];
      });
      setError(err.message);
    } finally {
      clearPreparingTimer();
      clearActivityTimer();
      setIsLoading(false);
      setToolStatus(null);
      setStreamPhase("idle");
    }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
    setError(null);
    sessionIdRef.current = null;
  }, []);

  return { messages, isLoading, error, sendMessage, clearChat, lastActions, toolStatus, streamPhase };
}
