import { useState, useEffect } from "react";

/**
 * Load the pipeline report.json bundle.
 *
 * In development, loads from /data/report.json (place a copy in dashboard/public/data/).
 * In production, the build step can inline or fetch from a configured URL.
 */
export function useReport(url = "/data/report.json") {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Failed to load report: ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setReport(data);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      }
    }

    load();
    return () => { cancelled = true; };
  }, [url]);

  return { report, loading, error };
}

/**
 * Load the 3D scene JSON bundle.
 */
export function useScene3D(url = "/data/3d_scene.json") {
  const [scene, setScene] = useState(null);

  useEffect(() => {
    fetch(url)
      .then((r) => r.ok ? r.json() : null)
      .then(setScene)
      .catch(() => setScene(null));
  }, [url]);

  return scene;
}
