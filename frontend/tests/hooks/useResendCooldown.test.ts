import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useResendCooldown } from '../../src/hooks/useResendCooldown';

describe('useResendCooldown', () => {
  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it('persists the cooldown in localStorage when an email is provided', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() => useResendCooldown(0, 'user@example.com'));

    act(() => {
      result.current.setCooldown(60);
    });

    expect(localStorage.getItem('resend_cooldown_user@example.com')).toBe(
      String(Date.now() + 60000)
    );
  });

  it('restores the remaining cooldown from localStorage on mount', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));
    localStorage.setItem('resend_cooldown_user@example.com', String(Date.now() + 45000));

    const { result } = renderHook(() => useResendCooldown(0, 'user@example.com'));

    expect(result.current.cooldown).toBe(45);
  });

  it('clears invalid stored cooldown values', () => {
    localStorage.setItem('resend_cooldown_user@example.com', 'not-a-number');

    const { result } = renderHook(() => useResendCooldown(0, 'user@example.com'));

    expect(result.current.cooldown).toBe(0);
    expect(localStorage.getItem('resend_cooldown_user@example.com')).toBeNull();
  });

  it('clears expired stored cooldown values', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));
    localStorage.setItem('resend_cooldown_user@example.com', String(Date.now() - 1000));

    const { result } = renderHook(() => useResendCooldown(0, 'user@example.com'));

    expect(result.current.cooldown).toBe(0);
    expect(localStorage.getItem('resend_cooldown_user@example.com')).toBeNull();
  });

  it('removes the persisted cooldown when set to zero', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() => useResendCooldown(0, 'user@example.com'));

    act(() => {
      result.current.setCooldown(60);
    });

    act(() => {
      result.current.setCooldown(0);
    });

    expect(localStorage.getItem('resend_cooldown_user@example.com')).toBeNull();
  });

  it('supports updater functions when persisting cooldown', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() => useResendCooldown(5, 'user@example.com'));

    act(() => {
      result.current.setCooldown((prev) => prev + 10);
    });

    expect(result.current.cooldown).toBe(15);
    expect(localStorage.getItem('resend_cooldown_user@example.com')).toBe(
      String(Date.now() + 15000)
    );
  });

  it('restores the remaining cooldown from localStorage across unmounts for the same email', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const email = 'test@example.com';
    const storageKey = `resend_cooldown_${email}`;

    const { result, unmount } = renderHook(() => useResendCooldown(0, email));

    act(() => {
      result.current.setCooldown(60);
    });

    expect(localStorage.getItem(storageKey)).toBe(String(Date.now() + 60000));

    act(() => {
      vi.advanceTimersByTime(15000);
    });

    unmount();

    const { result: remountedResult } = renderHook(() => useResendCooldown(0, email));

    expect(remountedResult.current.cooldown).toBe(45);
  });

  it('keeps cooldown aligned with the stored expiry time as time advances', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() => useResendCooldown(0, 'sync@example.com'));

    act(() => {
      result.current.setCooldown(60);
    });

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(result.current.cooldown).toBe(59);

    act(() => {
      vi.advanceTimersByTime(29000);
    });

    expect(result.current.cooldown).toBe(30);
  });

  it('syncs cooldown immediately when localStorage changes from another tab', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const email = 'cross-tab@example.com';
    const storageKey = `resend_cooldown_${email}`;
    const { result } = renderHook(() => useResendCooldown(0, email));

    expect(result.current.cooldown).toBe(0);

    act(() => {
      localStorage.setItem(storageKey, String(Date.now() + 60000));
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: storageKey,
          newValue: String(Date.now() + 60000),
          storageArea: localStorage,
        })
      );
    });

    expect(result.current.cooldown).toBe(60);

    act(() => {
      localStorage.removeItem(storageKey);
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: storageKey,
          newValue: null,
          storageArea: localStorage,
        })
      );
    });

    expect(result.current.cooldown).toBe(0);
  });
});
