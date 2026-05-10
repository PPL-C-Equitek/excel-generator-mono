"use client";

import { useEffect, type RefObject } from "react";

export function useAutoScrollToBottom(
  ref: RefObject<HTMLElement | null>,
  enabled: boolean,
  dependencyKey: string,
) {
  useEffect(() => {
    if (!enabled || !ref.current) {
      return;
    }

    ref.current.scrollTop = ref.current.scrollHeight;
  }, [dependencyKey, enabled, ref]);
}

