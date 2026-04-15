import { expect, test } from '@playwright/test'

test('logs out the authenticated user and returns to login', async ({ page }) => {
    await page.goto('/convert')

    await expect(page.getByRole('link', { name: 'Convert' })).toBeVisible()
    await page.getByRole('button', { name: 'Logout' }).click()

    await page.waitForURL('**/login')
    await expect(page.getByRole('button', { name: /^Sign In$/ })).toBeVisible()
})
