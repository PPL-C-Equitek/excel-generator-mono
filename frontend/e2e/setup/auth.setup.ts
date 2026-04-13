import fs from 'node:fs'
import path from 'node:path'
import { expect, test as setup } from '@playwright/test'
import { authStatePath, e2eUserEmail, e2eUserPassword } from '../../playwright/env'

setup('authenticate the seeded e2e user', async ({ page }) => {
    fs.mkdirSync(path.dirname(authStatePath), { recursive: true })

    await page.goto('/login')
    await page.getByLabel('Email').fill(e2eUserEmail)
    await page.getByTestId('password-input').fill(e2eUserPassword)
    await page.getByRole('button', { name: /^Sign In$/ }).click()

    await page.waitForURL('**/convert')
    await expect(page.getByRole('link', { name: 'Convert' })).toBeVisible()

    await page.context().storageState({ path: authStatePath })
})
