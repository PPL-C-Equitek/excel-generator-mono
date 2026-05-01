"use client";

import { useEffect, useState } from "react";
import { getSessionResume, type SessionResume } from "@/services/sessions";

export function useSessionResume(sessionId: string | null) {
  const [session, setSession] = useState<SessionResume | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const hasSessionId = sessionId !== null;
  const activeSession = hasSessionId ? session : null;
  const activeError = hasSessionId ? error : null;
  const activeIsLoading = hasSessionId ? isLoading : false;
  const activeIsNotFound = hasSessionId ? isNotFound : false;

  useEffect(() => {
    let isActive = true;

    if (!sessionId) {
      return;
    }

    const timeoutId = setTimeout(() => {
      if (!isActive) {
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
    }, 0);

    return () => {
      isActive = false;
      clearTimeout(timeoutId);
    };
  }, [sessionId]);

  return {
    session: activeSession,
    isLoading: activeIsLoading,
    error: activeError,
    isNotFound: activeIsNotFound,
  };
}
