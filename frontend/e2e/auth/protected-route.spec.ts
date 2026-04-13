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
