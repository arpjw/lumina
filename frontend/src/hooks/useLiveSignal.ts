"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL, type LatestSignal } from "@/lib/api";

interface LiveMessage extends LatestSignal {
  type: string;
  timestamp: string;
}

export function useLiveSignal() {
  const [signal, setSignal] = useState<LiveMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);

  function connect() {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
        retryCount.current = 0;
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
        const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
        retryCount.current += 1;
        retryRef.current = setTimeout(connect, delay);
      };
    } catch (e) {
      setError("Could not connect to live signal stream");
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
