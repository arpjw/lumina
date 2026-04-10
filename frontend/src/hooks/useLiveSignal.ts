"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL, type LatestSignal } from "@/lib/api";

interface LiveMessage extends LatestSignal {
  type: string;
  timestamp: string;
}

const STATIC_FALLBACK: LiveMessage = {
  type: "signal_update",
  timestamp: new Date().toISOString(),
  date: new Date().toISOString().slice(0, 10),
  regime: "transition",
  confidence: 0.71,
  probabilities: { risk_on: 0.18, transition: 0.71, risk_off: 0.11 },
  source_counts: { reddit: 0, gdelt: 0, fred: 0, edgar: 0, wikipedia: 0 },
};

export function useLiveSignal() {
  const [signal, setSignal] = useState<LiveMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);
  const failedOnce = useRef(false);

  function connect() {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
        retryCount.current = 0;
        failedOnce.current = false;
      };

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.type === "signal_update") {
            setSignal(data);
          }
        } catch {
          // ignore malformed frames
        }
      };

      ws.onerror = () => {
        setError("WebSocket error");
      };

      ws.onclose = () => {
        setConnected(false);

        // After first failure, provide static fallback so the gauge renders
        if (!failedOnce.current) {
          failedOnce.current = true;
          setSignal(STATIC_FALLBACK);
        }

        // Only retry a few times to avoid infinite loops when no backend
        if (retryCount.current < 3) {
          const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
          retryCount.current += 1;
          retryRef.current = setTimeout(connect, delay);
        }
      };
    } catch {
      setError("Could not connect to live signal stream");
      if (!failedOnce.current) {
        failedOnce.current = true;
        setSignal(STATIC_FALLBACK);
      }
    }
  }

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (retryRef.current) clearTimeout(retryRef.current);
    };
  }, []);

  return { signal, connected, error };
}
