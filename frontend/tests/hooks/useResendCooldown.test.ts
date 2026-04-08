import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useResendCooldown } from '@/hooks/useResendCooldown'

describe('useResendCooldown', () => {
    it('counts down to zero and clears the interval at the end', () => {
        vi.useFakeTimers()
        const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval')

        const { result } = renderHook(() => useResendCooldown(2))

        expect(result.current.cooldown).toBe(2)

        act(() => {
            vi.advanceTimersByTime(1000)
        })
        expect(result.current.cooldown).toBe(1)

        act(() => {
            vi.advanceTimersByTime(1000)
        })
        expect(result.current.cooldown).toBe(0)
        expect(clearIntervalSpy).toHaveBeenCalled()

        vi.useRealTimers()
    })
})
