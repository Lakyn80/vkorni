"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { BatchStatus } from "@/types";

const POLL_INTERVAL = 3000;

export function useBatch(onAllDone: () => void) {
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const poll = useCallback(async (id: string) => {
    try {
      const data = await api.getBatch(id);
      setBatch(data);
      if (data.queued === 0 && data.running === 0) {
        stopPolling();
        setBusy(false);
        onAllDone();
      }
    } catch {
      // keep polling on transient errors
    }
  }, [stopPolling, onAllDone]);

  const startBatch = useCallback(async (names: string[]) => {
    setError("");
    setBusy(true);
    setBatch(null);
    stopPolling();

    try {
      const res = await api.createBatch(names);
      setBatchId(res.batch_id);
      // Start polling immediately
      await poll(res.batch_id);
      intervalRef.current = setInterval(() => poll(res.batch_id), POLL_INTERVAL);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка запуска пакета");
      setBusy(false);
    }
  }, [poll, stopPolling]);

  const retryFailed = useCallback(async () => {
    if (!batchId) return;
    try {
      await api.retryBatch(batchId);
      setBusy(true);
      intervalRef.current = setInterval(() => poll(batchId), POLL_INTERVAL);
    } catch {
      // ignore
    }
  }, [batchId, poll]);

  const clearBatch = useCallback(() => {
    stopPolling();
    setBatchId(null);
    setBatch(null);
    setBusy(false);
    setError("");
  }, [stopPolling]);

  // Cleanup on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  return { batch, busy, error, startBatch, retryFailed, clearBatch };
}
