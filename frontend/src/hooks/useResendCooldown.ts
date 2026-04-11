'use client';

import type React from 'react';
import { useEffect, useState } from 'react';

function getStoredCooldown(storageKey?: string): number {
  if (!storageKey || typeof globalThis.sessionStorage === 'undefined') {
    return 0;
  }

  const rawValue = globalThis.sessionStorage.getItem(storageKey);
  if (!rawValue) {
    return 0;
  }

  const cooldownUntil = Number(rawValue);
  if (!Number.isFinite(cooldownUntil)) {
    globalThis.sessionStorage.removeItem(storageKey);
    return 0;
  }

  const remainingSeconds = Math.ceil((cooldownUntil - Date.now()) / 1000);
  if (remainingSeconds <= 0) {
    globalThis.sessionStorage.removeItem(storageKey);
    return 0;
  }

  return remainingSeconds;
}

function persistCooldown(storageKey: string | undefined, nextValue: number): void {
  if (!storageKey || typeof globalThis.sessionStorage === 'undefined') {
    return;
  }

  if (nextValue <= 0) {
    globalThis.sessionStorage.removeItem(storageKey);
    return;
  }

  const cooldownUntil = Date.now() + nextValue * 1000;
  globalThis.sessionStorage.setItem(storageKey, String(cooldownUntil));
}

export function useResendCooldown(initialValue = 0, storageKey?: string) {
  const [cooldown, setCooldown] = useState(() => {
    const storedCooldown = getStoredCooldown(storageKey);
    return storedCooldown > 0 ? storedCooldown : initialValue;
  });

  useEffect(() => {
    if (cooldown <= 0) return undefined;

    const timer = globalThis.setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          globalThis.clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => globalThis.clearInterval(timer);
  }, [cooldown]);

  const setPersistedCooldown: React.Dispatch<React.SetStateAction<number>> = (value) => {
    setCooldown((prev) => {
      const nextValue = typeof value === 'function' ? value(prev) : value;
      persistCooldown(storageKey, nextValue);
      return nextValue;
    });
  };

  return {
    cooldown,
    setCooldown: setPersistedCooldown,
  };
}
