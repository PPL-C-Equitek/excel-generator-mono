import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useResendCooldown } from '../../src/hooks/useResendCooldown';

describe('useResendCooldown', () => {
  afterEach(() => {
    vi.useRealTimers();
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
});
