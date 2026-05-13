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
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSession(null);
      setIsLoading(false);
      setError(null);
      setIsNotFound(false);
      return;
    }

    setSession(null);
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
        const normalizedMessage = message.trim().toLowerCase();
        const shouldShowNotFound =
          normalizedMessage === "not found." ||
          normalizedMessage.includes("not found") ||
          normalizedMessage.includes("forbidden") ||
          normalizedMessage.includes("unauthorized") ||
          normalizedMessage.includes("authentication credentials were not provided");
        setSession(null);
        setIsNotFound(shouldShowNotFound);
        setError(shouldShowNotFound ? null : message);
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

  return {
    session: activeSession,
    isLoading: activeIsLoading,
    error: activeError,
    isNotFound: activeIsNotFound,
  };
}
