import { describe, it, expect } from 'vitest'
import { validatePasswordForm } from '../../src/hooks/useTokenPasswordAction'

describe('validatePasswordForm', () => {
  it('returns passwordConfirm required when confirm is empty', () => {
    const errors = validatePasswordForm('SomePass123', '')
    expect(errors.password).toBe('')
    expect(errors.passwordConfirm).toBe('Password confirmation is required')
  })
})
