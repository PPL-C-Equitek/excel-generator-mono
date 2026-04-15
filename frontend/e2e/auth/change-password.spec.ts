import { expect, test } from '@playwright/test'

test('change password blocks invalid form submission before request', async ({ page }) => {
  let requestCount = 0

  await page.route('**/auth/change-password/', async (route) => {
    requestCount += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unexpected' }),
    })
  })

  await page.goto('/change-password')

  await page.getByRole('button', { name: 'Change Password' }).click()

  await expect(page.getByText('New password is required.')).toBeVisible()
  await expect(page.getByText('Password confirmation is required.')).toBeVisible()
  expect(requestCount).toBe(0)
})

test('change password blocks weak password before request', async ({ page }) => {
  let requestCount = 0

  await page.route('**/auth/change-password/', async (route) => {
    requestCount += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'unexpected' }),
    })
  })

  await page.goto('/change-password')

  await page.locator('#newPassword').fill('weak')
  await page.locator('#newPasswordConfirm').fill('weak')
  await page.getByRole('button', { name: 'Change Password' }).click()

  await expect(
    page.getByText(
      'Password must be at least 8 characters long and include a letter, a number, and a special character.'
    )
  ).toBeVisible()
  expect(requestCount).toBe(0)
})

test('change password submits payload and shows success state', async ({ page }) => {
  let changePasswordPayload: Record<string, unknown> | null = null

  await page.route('**/auth/change-password/', async (route) => {
    const rawBody = route.request().postData()
    changePasswordPayload = rawBody ? JSON.parse(rawBody) : null

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Password changed successfully.' }),
    })
  })

  await page.goto('/change-password')

  await page.locator('#currentPassword').fill('OldP@ssword123!')
  await page.locator('#newPassword').fill('NewP@ssword123!')
  await page.locator('#newPasswordConfirm').fill('NewP@ssword123!')
  await page.getByRole('button', { name: 'Change Password' }).click()

  await expect(page.getByRole('heading', { name: 'Password Updated' })).toBeVisible()
  await expect(page.getByText('Password changed successfully.')).toBeVisible()
  expect(changePasswordPayload).toMatchObject({
    current_password: 'OldP@ssword123!',
    new_password: 'NewP@ssword123!',
    new_password_confirm: 'NewP@ssword123!',
  })
})

test('change password keeps form visible when backend returns an error', async ({ page }) => {
  await page.route('**/auth/change-password/', async (route) => {
    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Current password is incorrect.' }),
    })
  })

  await page.goto('/change-password')

  await page.locator('#newPassword').fill('NewP@ssword123!')
  await page.locator('#newPasswordConfirm').fill('NewP@ssword123!')
  await page.getByRole('button', { name: 'Change Password' }).click()

  await expect(page.getByText('Current password is incorrect.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Change Password' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Change Password' })).toBeVisible()
})
