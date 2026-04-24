import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getRemainingResendCooldownForEmail,
  setResendCooldownForEmail,
  useResendCooldown,
} from '../../src/hooks/useResendCooldown';

const defaultWindow = globalThis.window;

describe('useResendCooldown', () => {
  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(globalThis, 'window', {
      value: defaultWindow,
      configurable: true,
    });
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

  it('setResendCooldownForEmail ignores empty emails and removes cooldown when seconds are non-positive', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    setResendCooldownForEmail('   ', 60);
    expect(localStorage.length).toBe(0);

    localStorage.setItem('resend_cooldown_user@example.com', String(Date.now() + 60000));
    setResendCooldownForEmail('user@example.com', 0);

    expect(localStorage.getItem('resend_cooldown_user@example.com')).toBeNull();
  });

  it('setResendCooldownForEmail stores a positive cooldown for the normalized email key', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    setResendCooldownForEmail(' User@Example.com ', 60);

    expect(localStorage.getItem('resend_cooldown_user@example.com')).toBe(
      String(Date.now() + 60000)
    );
  });

  it('getRemainingResendCooldownForEmail returns zero when window is unavailable', () => {
    const originalWindow = globalThis.window;
    Object.defineProperty(globalThis, 'window', {
      value: undefined,
      configurable: true,
    });

    expect(getRemainingResendCooldownForEmail('user@example.com')).toBe(0);

    Object.defineProperty(globalThis, 'window', {
      value: originalWindow,
      configurable: true,
    });
  });

  it('setResendCooldownForEmail does nothing when window is unavailable', () => {
    const originalWindow = globalThis.window;
    Object.defineProperty(globalThis, 'window', {
      value: undefined,
      configurable: true,
    });

    expect(() => setResendCooldownForEmail('user@example.com', 60)).not.toThrow();

    Object.defineProperty(globalThis, 'window', {
      value: originalWindow,
      configurable: true,
    });
  });

  it('getRemainingResendCooldownForEmail returns zero for blank emails', () => {
    expect(getRemainingResendCooldownForEmail('   ')).toBe(0);
  });

  it('returns zero when the stored expiry becomes stale while being read', () => {
    localStorage.setItem('resend_cooldown_race@example.com', '1001');

    const dateNowSpy = vi
      .spyOn(Date, 'now')
      .mockReturnValueOnce(1000)
      .mockReturnValueOnce(1001);

    expect(getRemainingResendCooldownForEmail('race@example.com')).toBe(0);

    dateNowSpy.mockRestore();
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

  it('ignores storage events for other keys or storage areas', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const email = 'ignored@example.com';
    const { result } = renderHook(() => useResendCooldown(0, email));

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: 'resend_cooldown_other@example.com',
          newValue: String(Date.now() + 60000),
          storageArea: localStorage,
        })
      );
    });

    expect(result.current.cooldown).toBe(0);

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: `resend_cooldown_${email}`,
          newValue: String(Date.now() + 60000),
          storageArea: sessionStorage,
        })
      );
    });

    expect(result.current.cooldown).toBe(0);
  });

  it('keeps the existing cooldown when initialValue is positive and storage disappears', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const email = 'persist@example.com';
    const storageKey = `resend_cooldown_${email}`;
    const { result } = renderHook(() => useResendCooldown(5, email));

    act(() => {
      result.current.setCooldown(12);
    });

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

    expect(result.current.cooldown).toBe(12);
  });

  it('falls back to initialValue when cooldown is zero and the matching storage event fires', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const email = 'fallback@example.com';
    const storageKey = `resend_cooldown_${email}`;
    const { result } = renderHook(() => useResendCooldown(5, email));

    act(() => {
      result.current.setCooldown(0);
    });

    expect(result.current.cooldown).toBe(0);

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: storageKey,
          newValue: null,
          storageArea: localStorage,
        })
      );
    });

    expect(result.current.cooldown).toBe(5);
  });

  it('returns zero when setCooldown receives a negative value', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() => useResendCooldown(0, 'negative@example.com'));

    act(() => {
      result.current.setCooldown(-3);
    });

    expect(result.current.cooldown).toBe(0);
    expect(localStorage.getItem('resend_cooldown_negative@example.com')).toBeNull();
  });

  it('returns the initial value when the hook is used without an email', () => {
    const { result } = renderHook(() => useResendCooldown(7));

    expect(result.current.cooldown).toBe(7);
  });

  it('updates local state without touching storage when no email is provided', () => {
    const { result } = renderHook(() => useResendCooldown(0));

    act(() => {
      result.current.setCooldown(9);
    });

    expect(result.current.cooldown).toBe(9);
    expect(localStorage.length).toBe(0);
  });

  it('does not start sync timers or storage listeners when no email is provided', () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener');

    renderHook(() => useResendCooldown(0));

    expect(setIntervalSpy).not.toHaveBeenCalled();
    expect(addEventListenerSpy).not.toHaveBeenCalledWith('storage', expect.any(Function));
  });
});
