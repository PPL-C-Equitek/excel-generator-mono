'use client';

import { useEffect, useState } from 'react';

export function useResendCooldown(initialValue = 0) {
  const [cooldown, setCooldown] = useState(initialValue);

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

  return {
    cooldown,
    setCooldown,
  };
}
