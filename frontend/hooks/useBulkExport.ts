import { useState, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import type { BulkExportStatus } from "@/types";

export function useBulkExport() {
  const [status, setStatus] = useState<BulkExportStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startExport = useCallback(async (names: string[]) => {
    if (busy) return;
    setBusy(true);
    setStatus(null);
    stopPolling();

    try {
      const { export_id } = await api.bulkExport(names);

      pollRef.current = setInterval(async () => {
        try {
          const s = await api.getBulkExport(export_id);
          setStatus(s);
          const finished = s.done + s.failed === s.total;
          if (finished) {
            stopPolling();
            setBusy(false);
          }
        } catch {
          stopPolling();
          setBusy(false);
        }
      }, 2000);
    } catch {
      setBusy(false);
    }
  }, [busy, stopPolling]);

  return { status, busy, startExport };
}
