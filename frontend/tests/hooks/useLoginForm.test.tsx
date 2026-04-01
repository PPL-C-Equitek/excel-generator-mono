import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import useLoginForm from '../../src/hooks/useLoginForm'

describe('useLoginForm', () => {
    describe('positive', () => {
        it('initializes with empty fields', () => {
            const { result } = renderHook(() => useLoginForm())
            expect(result.current.email).toBe('')
            expect(result.current.password).toBe('')
            expect(result.current.rememberMe).toBe(false)
            expect(result.current.error).toBeNull()
        })

        it('updates email', () => {
            const { result } = renderHook(() => useLoginForm())
            act(() => result.current.setEmail('test@example.com'))
            expect(result.current.email).toBe('test@example.com')
        })

        it('updates password', () => {
            const { result } = renderHook(() => useLoginForm())
            act(() => result.current.setPassword('secret123'))
            expect(result.current.password).toBe('secret123')
        })

        it('toggles rememberMe', () => {
            const { result } = renderHook(() => useLoginForm())
            act(() => result.current.setRememberMe(true))
            expect(result.current.rememberMe).toBe(true)
        })

        it('calls onSubmit with valid data', () => {
            const mockOnSubmit = vi.fn()
            const { result } = renderHook(() => useLoginForm({ onSubmit: mockOnSubmit }))
            act(() => {
                result.current.setEmail('test@example.com')
                result.current.setPassword('secret123')
            })
            act(() => result.current.handleSubmit())
            expect(mockOnSubmit).toHaveBeenCalledWith({
                email: 'test@example.com',
                password: 'secret123',
                rememberMe: false,
            })
        })
    })

    describe('negative', () => {
        it('sets error for invalid email', () => {
            const { result } = renderHook(() => useLoginForm())
            act(() => {
                result.current.setEmail('invalid')
                result.current.setPassword('secret123')
            })
            act(() => result.current.handleSubmit())
            expect(result.current.error).toBeTruthy()
        })

        it('sets error when password is empty', () => {
            const { result } = renderHook(() => useLoginForm())
            act(() => {
                result.current.setEmail('test@example.com')
                result.current.setPassword('')
            })
            act(() => result.current.handleSubmit())
            expect(result.current.error).toBeTruthy()
        })

        it('does not call onSubmit when validation fails', () => {
            const mockOnSubmit = vi.fn()
            const { result } = renderHook(() => useLoginForm({ onSubmit: mockOnSubmit }))
            act(() => result.current.handleSubmit())
            expect(mockOnSubmit).not.toHaveBeenCalled()
        })
    })
})