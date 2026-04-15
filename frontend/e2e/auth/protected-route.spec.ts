import { expect, test } from '@playwright/test'

test.use({
    storageState: { cookies: [], origins: [] },
})

test('redirects unauthenticated users to the login page', async ({ page }) => {
    await page.goto('/history')

    await page.waitForURL('**/login')
    await expect(page.getByRole('button', { name: /^Sign In$/ })).toBeVisible()
    await expect(page.getByText('Sign in to continue to your workspace.')).toBeVisible()
})

test('redirects to login when refresh token validation fails', async ({ page }) => {
    let refreshRequestCount = 0

    await page.addInitScript(() => {
        globalThis.localStorage.setItem('refresh_token', 'expired-refresh-token')
    })

    await page.route('**/auth/refresh/', async (route) => {
        refreshRequestCount += 1
        await route.fulfill({
            status: 401,
            contentType: 'application/json',
            body: JSON.stringify({ message: 'Invalid refresh token.' }),
        })
    })

    await page.goto('/change-password')

    await page.waitForURL('**/login')
    await expect(page.getByRole('button', { name: /^Sign In$/ })).toBeVisible()
    expect(refreshRequestCount).toBe(1)
})
