import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useResendCooldown } from '../../src/hooks/useResendCooldown';

describe('useResendCooldown', () => {
  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('persists the cooldown in sessionStorage when a storage key is provided', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() =>
      useResendCooldown(0, 'forgot-password-resend-cooldown:user@example.com')
    );

    act(() => {
      result.current.setCooldown(60);
    });

    expect(
      sessionStorage.getItem('forgot-password-resend-cooldown:user@example.com')
    ).toBe(String(Date.now() + 60000));
  });

  it('restores the remaining cooldown from sessionStorage on mount', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));
    sessionStorage.setItem(
      'forgot-password-resend-cooldown:user@example.com',
      String(Date.now() + 45000)
    );

    const { result } = renderHook(() =>
      useResendCooldown(0, 'forgot-password-resend-cooldown:user@example.com')
    );

    expect(result.current.cooldown).toBe(45);
  });

  it('clears invalid stored cooldown values', () => {
    sessionStorage.setItem(
      'forgot-password-resend-cooldown:user@example.com',
      'not-a-number'
    );

    const { result } = renderHook(() =>
      useResendCooldown(0, 'forgot-password-resend-cooldown:user@example.com')
    );

    expect(result.current.cooldown).toBe(0);
    expect(
      sessionStorage.getItem('forgot-password-resend-cooldown:user@example.com')
    ).toBeNull();
  });

  it('clears expired stored cooldown values', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));
    sessionStorage.setItem(
      'forgot-password-resend-cooldown:user@example.com',
      String(Date.now() - 1000)
    );

    const { result } = renderHook(() =>
      useResendCooldown(0, 'forgot-password-resend-cooldown:user@example.com')
    );

    expect(result.current.cooldown).toBe(0);
    expect(
      sessionStorage.getItem('forgot-password-resend-cooldown:user@example.com')
    ).toBeNull();
  });

  it('removes the persisted cooldown when set to zero', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() =>
      useResendCooldown(0, 'forgot-password-resend-cooldown:user@example.com')
    );

    act(() => {
      result.current.setCooldown(60);
    });

    act(() => {
      result.current.setCooldown(0);
    });

    expect(
      sessionStorage.getItem('forgot-password-resend-cooldown:user@example.com')
    ).toBeNull();
  });

  it('supports updater functions when persisting cooldown', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const { result } = renderHook(() =>
      useResendCooldown(5, 'forgot-password-resend-cooldown:user@example.com')
    );

    act(() => {
      result.current.setCooldown((prev) => prev + 10);
    });

    expect(result.current.cooldown).toBe(15);
    expect(
      sessionStorage.getItem('forgot-password-resend-cooldown:user@example.com')
    ).toBe(String(Date.now() + 15000));
  });

  it('restores the remaining cooldown from localStorage across unmounts for the same email', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-11T10:00:00.000Z'));

    const email = 'test@example.com';
    const storageKey = `verify-email-pending-resend-cooldown:${email}`;

    const { result, unmount } = renderHook(() => useResendCooldown(0, storageKey));

    act(() => {
      result.current.setCooldown(60);
    });

    expect(localStorage.getItem(storageKey)).toBe(String(Date.now() + 60000));

    act(() => {
      vi.advanceTimersByTime(15000);
    });

    unmount();

    const { result: remountedResult } = renderHook(() =>
      useResendCooldown(0, storageKey)
    );

    expect(remountedResult.current.cooldown).toBe(45);
  });
});
