import { expect, test } from '@playwright/test'

test('forgot password validates email and sends trimmed payload', async ({ page }) => {
  let forgotPayload: Record<string, unknown> | null = null
  let resendPayload: Record<string, unknown> | null = null
  let resendCalled = false

  await page.route('**/auth/forgot-password/', async (route) => {
    const rawBody = route.request().postData()
    forgotPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'If the email exists, we sent a reset link.' }),
    })
  })

  await page.route('**/auth/resend-password-reset/', async (route) => {
    const rawBody = route.request().postData()
    resendPayload = rawBody ? JSON.parse(rawBody) : null
    resendCalled = true

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'If the email exists, we sent a new reset link.' }),
    })
  })

  await page.goto('/forgot-password')

  const emailInput = page.getByRole('textbox', { name: 'Email' })
  await emailInput.fill('   user@example.com   ')
  await page.getByRole('button', { name: 'Send Reset Link' }).click()

  await expect(
    page.getByText('If the email exists, we sent a reset link.')
  ).toBeVisible()

  expect(forgotPayload?.email).toBe('user@example.com')

  const resendButton = page.getByRole('button', { name: /^Resend Email$/ })
  await resendButton.click()
  await expect(
    page.getByText('If the email exists, we sent a new reset link.')
  ).toBeVisible()

  expect(resendCalled).toBe(true)
  expect(resendPayload?.email).toBe('   user@example.com   ')
})

test('forgot password blocks invalid emails before request', async ({ page }) => {
  let requestCount = 0

  await page.route('**/auth/forgot-password/', async (route) => {
    requestCount += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unexpected' }),
    })
  })

  await page.goto('/forgot-password')

  await page.getByRole('textbox', { name: 'Email' }).fill('invalid-email')
  await page.getByRole('button', { name: 'Send Reset Link' }).click()

  await expect(
    page.getByText('Please enter a valid email address.')
  ).toBeVisible()
  expect(requestCount).toBe(0)
})

test('reset password flow validates token and form inputs', async ({ page }) => {
  let submitCalled = false
  let submitPayload: Record<string, unknown> | null = null

  await page.route('**/auth/reset-password/', async (route) => {
    submitCalled = true
    const rawBody = route.request().postData()
    submitPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Your password has been reset successfully.' }),
    })
  })

  await page.goto('/auth/reset-password')
  await expect(page.getByRole('heading', { name: 'Reset Failed' })).toBeVisible()
  await expect(
    page.getByText('Reset token was not found. Please request a new password reset email.')
  ).toBeVisible()

  await page.goto('/auth/reset-password?token=reset-test-token')

  await page.getByRole('textbox', { name: 'Password' }).fill('P@ssw0rd123')
  await page.getByRole('textbox', { name: 'Confirm Password' }).fill('Different123')
  await page.getByRole('button', { name: 'Reset Password' }).click()

  await expect(page.getByText('Passwords do not match.')).toBeVisible()
  expect(submitCalled).toBe(false)

  await page.getByRole('textbox', { name: 'Password' }).fill('P@ssw0rd123')
  await page.getByRole('textbox', { name: 'Confirm Password' }).fill('P@ssw0rd123')
  await page.getByRole('button', { name: 'Reset Password' }).click()

  await expect(page.getByRole('heading', { name: 'Password Reset' })).toBeVisible()
  await expect(page.getByText('Your password has been reset successfully.')).toBeVisible()
  expect(submitPayload).toMatchObject({
    token: 'reset-test-token',
    password: 'P@ssw0rd123',
    password_confirm: 'P@ssw0rd123',
  })
})

test('verify email flow handles missing and invalid tokens', async ({ page }) => {
  await page.route('**/auth/verify-email/validate/', async (route) => {
    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'The verification token is invalid.' }),
    })
  })

  await page.goto('/auth/verify-email')
  await expect(page.getByRole('heading', { name: 'Verification Failed' })).toBeVisible()

  await page.goto('/auth/verify-email?token=invalid-token')
  await expect(page.getByRole('heading', { name: 'Verification Failed' })).toBeVisible()
  await expect(page.getByText('The verification token is invalid.')).toBeVisible()
})

test('verify email flow validates and submits new password', async ({ page }) => {
  let verifySubmitPayload: Record<string, unknown> | null = null

  await page.route('**/auth/verify-email/validate/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Token valid.' }),
    })
  })

  await page.route('**/auth/verify-email/', async (route) => {
    const rawBody = route.request().postData()
    verifySubmitPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Your email has been verified successfully.' }),
    })
  })

  await page.goto('/auth/verify-email?token=verify-token')

  await expect(page.getByRole('heading', { name: 'Set Your Password' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Password' }).fill('P@ssw0rd123')
  await page.getByRole('textbox', { name: 'Confirm Password' }).fill('P@ssw0rd123')
  await page.getByRole('button', { name: 'Verify Email and Save Password' }).click()

  await expect(page.getByRole('heading', { name: 'Email Verified' })).toBeVisible()
  await expect(
    page.getByText('Your email has been verified successfully.')
  ).toBeVisible()
  expect(verifySubmitPayload).toMatchObject({
    token: 'verify-token',
    password: 'P@ssw0rd123',
    password_confirm: 'P@ssw0rd123',
  })
})

test('reset password shows backend field errors without leaving the form', async ({ page }) => {
  let resetPayload: Record<string, unknown> | null = null

  await page.route('**/auth/reset-password/', async (route) => {
    const rawBody = route.request().postData()
    resetPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        errors: {
          password: ['Password is too weak.'],
          password_confirm: ['Passwords do not match.'],
        },
      }),
    })
  })

  await page.goto('/auth/reset-password?token=reset-test-token')

  await page.getByRole('textbox', { name: 'Password' }).fill('weak')
  await page.getByRole('textbox', { name: 'Confirm Password' }).fill('weak1')
  await page.getByRole('button', { name: 'Reset Password' }).click()

  await expect(page.getByText('Reset Your Password')).toBeVisible()
  await expect(page.getByText('Password is too weak.')).toBeVisible()
  await expect(page.getByText('Passwords do not match.')).toBeVisible()

  expect(resetPayload).toMatchObject({
    token: 'reset-test-token',
    password: 'weak',
    password_confirm: 'weak1',
  })
})

test('verify email shows backend field errors while token is valid', async ({ page }) => {
  let verifySubmitPayload: Record<string, unknown> | null = null

  await page.route('**/auth/verify-email/validate/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Token valid.' }),
    })
  })

  await page.route('**/auth/verify-email/', async (route) => {
    const rawBody = route.request().postData()
    verifySubmitPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        errors: {
          password: ['Password is required.'],
          password_confirm: ['Passwords do not match.'],
        },
      }),
    })
  })

  await page.goto('/auth/verify-email?token=verify-token')

  await page.getByRole('textbox', { name: 'Password' }).fill('abc')
  await page.getByRole('textbox', { name: 'Confirm Password' }).fill('abcd')
  await page.getByRole('button', { name: 'Verify Email and Save Password' }).click()

  await expect(page.getByText('Set Your Password')).toBeVisible()
  await expect(page.getByText('Password is required.')).toBeVisible()
  await expect(page.getByText('Passwords do not match.')).toBeVisible()

  expect(verifySubmitPayload).toMatchObject({
    token: 'verify-token',
    password: 'abc',
    password_confirm: 'abcd',
  })
})
