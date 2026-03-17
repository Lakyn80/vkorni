"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useCacheList() {
  const [names, setNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getCacheList();
      const sorted = (Array.isArray(data.names) ? data.names : []).sort((a, b) =>
        a.localeCompare(b, "ru")
      );
      setNames(sorted);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки списка");
    } finally {
      setLoading(false);
    }
  }, []);

  const addName = useCallback((name: string) => {
    setNames((prev) =>
      Array.from(new Set([...prev, name])).sort((a, b) => a.localeCompare(b, "ru"))
    );
  }, []);

  const deleteName = useCallback(async (name: string) => {
    try {
      await api.deleteCache(name);
      setNames((prev) => prev.filter((n) => n !== name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }, []);

  const deleteAll = useCallback(async () => {
    try {
      await api.deleteAllCache();
      setNames([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления всех");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { names, loading, error, refresh, addName, deleteName, deleteAll };
}
