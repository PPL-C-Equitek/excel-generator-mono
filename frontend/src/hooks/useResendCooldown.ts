'use client';

import type React from 'react';
import { useEffect, useMemo, useState } from 'react';

function getStorageKey(email?: string): string | undefined {
  const normalizedEmail = email?.trim().toLowerCase();
  if (!normalizedEmail) {
    return undefined;
  }

  return `resend_cooldown_${normalizedEmail}`;
}

function getStoredExpiryTime(email?: string): number | null {
  if (globalThis.window === undefined) {
    return null;
  }

  const storageKey = getStorageKey(email);
  if (!storageKey) {
    return null;
  }

  const rawValue = globalThis.window.localStorage.getItem(storageKey);
  if (!rawValue) {
    return null;
  }

  const expiryTime = Number(rawValue);
  if (!Number.isFinite(expiryTime)) {
    globalThis.window.localStorage.removeItem(storageKey);
    return null;
  }

  if (expiryTime <= Date.now()) {
    globalThis.window.localStorage.removeItem(storageKey);
    return null;
  }

  return expiryTime;
}

function getRemainingSecondsFromExpiry(expiryTime: number | null): number {
  if (expiryTime === null) {
    return 0;
  }

  const remainingSeconds = Math.ceil((expiryTime - Date.now()) / 1000);
  return Math.max(remainingSeconds, 0);
}

export function getRemainingResendCooldownForEmail(email?: string): number {
  return getStoredCooldown(email);
}

export function setResendCooldownForEmail(email: string, cooldownSeconds: number): void {
  if (globalThis.window === undefined) {
    return;
  }

  const storageKey = getStorageKey(email);
  if (!storageKey) {
    return;
  }

  if (cooldownSeconds <= 0) {
    globalThis.window.localStorage.removeItem(storageKey);
    return;
  }

  globalThis.window.localStorage.setItem(
    storageKey,
    String(Date.now() + cooldownSeconds * 1000)
  );
}

function getStoredCooldown(email?: string): number {
  return getRemainingSecondsFromExpiry(getStoredExpiryTime(email));
}

export function useResendCooldown(initialValue = 0, email?: string) {
  const storageKey = useMemo(() => getStorageKey(email), [email]);
  const [cooldown, setCooldown] = useState(() => {
    const storedCooldown = getStoredCooldown(email);
    return storedCooldown > 0 ? storedCooldown : initialValue;
  });

  useEffect(() => {
    const browserWindow = globalThis.window;

    const syncCooldown = () => {
      const storedCooldown = getStoredCooldown(email);
      setCooldown((prev) => {
        if (storedCooldown > 0) {
          return storedCooldown;
        }

        if (initialValue > 0 && prev > 0) {
          return prev;
        }

        if (prev > 0 || initialValue <= 0) {
          return 0;
        }

        return initialValue;
      });
    };

    syncCooldown();

    const timer = storageKey
      ? browserWindow.setInterval(syncCooldown, 1000)
      : null;

    const handleStorage = (event: StorageEvent) => {
      if (event.storageArea !== browserWindow.localStorage) {
        return;
      }

      if (event.key !== storageKey) {
        return;
      }

      syncCooldown();
    };

    if (storageKey) {
      browserWindow.addEventListener('storage', handleStorage);
    }

    return () => {
      if (timer !== null) {
        browserWindow.clearInterval(timer);
      }

      if (storageKey) {
        browserWindow.removeEventListener('storage', handleStorage);
      }
    };
  }, [email, initialValue, storageKey]);

  const setPersistedCooldown: React.Dispatch<React.SetStateAction<number>> = (value) => {
    setCooldown((prev) => {
      const nextValue =
        typeof value === 'function'
          ? (value as (previousValue: number) => number)(prev)
          : value;

      if (globalThis.window !== undefined && storageKey) {
        if (nextValue <= 0) {
          globalThis.window.localStorage.removeItem(storageKey);
        } else {
          globalThis.window.localStorage.setItem(
            storageKey,
            String(Date.now() + nextValue * 1000)
          );
        }
      }

      return Math.max(nextValue, 0);
    });
  };

  return {
    cooldown,
    setCooldown: setPersistedCooldown,
  };
}
