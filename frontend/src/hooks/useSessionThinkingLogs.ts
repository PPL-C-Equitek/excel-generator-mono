"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getThinkingLogsBySession,
  type ThinkingLogItem,
} from "@/services/thinkingLogs";

export function useSessionThinkingLogs(sessionId: string | null) {
  const [thinkingLogs, setThinkingLogs] = useState<ThinkingLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    if (!sessionId) {
      setThinkingLogs([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    void getThinkingLogsBySession(sessionId)
      .then((response) => {
        if (!isActive) {
          return;
        }

        setThinkingLogs(response.results);
      })
      .catch((nextError: unknown) => {
        if (!isActive) {
          return;
        }

        setThinkingLogs([]);
        setError(
          nextError instanceof Error ? nextError.message : "Failed to load thinking log.",
        );
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [sessionId]);

  const thinkingLogsByOutputId = useMemo(
    () =>
      thinkingLogs.reduce<Record<string, ThinkingLogItem>>((acc, item) => {
        acc[item.id] = item;
        return acc;
      }, {}),
    [thinkingLogs],
  );

  return { thinkingLogs, thinkingLogsByOutputId, isLoading, error };
}
