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
  if (typeof window === 'undefined') {
    return null;
  }

  const storageKey = getStorageKey(email);
  if (!storageKey) {
    return null;
  }

  const rawValue = window.localStorage.getItem(storageKey);
  if (!rawValue) {
    return null;
  }

  const expiryTime = Number(rawValue);
  if (!Number.isFinite(expiryTime)) {
    window.localStorage.removeItem(storageKey);
    return null;
  }

  if (expiryTime <= Date.now()) {
    window.localStorage.removeItem(storageKey);
    return null;
  }

  return expiryTime;
}

function getRemainingSecondsFromExpiry(expiryTime: number | null): number {
  if (expiryTime === null) {
    return 0;
  }

  const remainingSeconds = Math.ceil((expiryTime - Date.now()) / 1000);
  return remainingSeconds > 0 ? remainingSeconds : 0;
}

export function getRemainingResendCooldownForEmail(email?: string): number {
  return getStoredCooldown(email);
}

export function setResendCooldownForEmail(email: string, cooldownSeconds: number): void {
  if (typeof window === 'undefined') {
    return;
  }

  const storageKey = getStorageKey(email);
  if (!storageKey) {
    return;
  }

  if (cooldownSeconds <= 0) {
    window.localStorage.removeItem(storageKey);
    return;
  }

  window.localStorage.setItem(
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
    const storedCooldown = getStoredCooldown(email);
    setCooldown(storedCooldown > 0 ? storedCooldown : initialValue);
  }, [email, initialValue]);

  useEffect(() => {
    if (!storageKey || typeof window === 'undefined') {
      return undefined;
    }

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

    const timer = window.setInterval(syncCooldown, 1000);

    const handleStorage = (event: StorageEvent) => {
      if (event.storageArea !== window.localStorage) {
        return;
      }

      if (event.key !== storageKey) {
        return;
      }

      syncCooldown();
    };

    window.addEventListener('storage', handleStorage);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener('storage', handleStorage);
    };
  }, [email, initialValue, storageKey]);

  const setPersistedCooldown: React.Dispatch<React.SetStateAction<number>> = (value) => {
    setCooldown((prev) => {
      const nextValue =
        typeof value === 'function'
          ? (value as (previousValue: number) => number)(prev)
          : value;

      if (typeof window !== 'undefined' && storageKey) {
        if (nextValue <= 0) {
          window.localStorage.removeItem(storageKey);
        } else {
          window.localStorage.setItem(storageKey, String(Date.now() + nextValue * 1000));
        }
      }

      return nextValue > 0 ? nextValue : 0;
    });
  };

  return {
    cooldown,
    setCooldown: setPersistedCooldown,
  };
}
