"use client";

import { useEffect, useState } from "react";
import { getSessionResume, type SessionResume } from "@/services/sessions";

export function useSessionResume(sessionId: string | null) {
  const [session, setSession] = useState<SessionResume | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    let isActive = true;

    if (!sessionId) {
      setSession(null);
      setError(null);
      setIsNotFound(false);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    setIsNotFound(false);

    void getSessionResume(sessionId)
      .then((nextSession) => {
        if (!isActive) {
          return;
        }

        setSession(nextSession);
        setIsNotFound(false);
      })
      .catch((nextError: unknown) => {
        if (!isActive) {
          return;
        }

        const message = nextError instanceof Error ? nextError.message : "Failed to load session.";
        setSession(null);
        setIsNotFound(message === "Not found.");
        setError(message === "Not found." ? null : message);
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

  return { session, isLoading, error, isNotFound };
}
