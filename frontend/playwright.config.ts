import { defineConfig } from '@playwright/test'
import {
    authStatePath,
    backendBaseUrl,
    backendDirectory,
    buildCommand,
    createBackendEnvironment,
    createFrontendEnvironment,
    frontendBaseUrl,
    frontendDirectory,
    resolvePythonExecutable,
    useDockerServices,
} from './playwright/env'

export default defineConfig({
    testDir: './e2e',
    fullyParallel: false,
    workers: 1,
    timeout: 30_000,
    expect: {
        timeout: 10_000,
    },
    globalSetup: './playwright/global-setup.ts',
    reporter: [
        ['list'],
        ['html', { open: 'never', outputFolder: 'playwright-report' }],
    ],
    use: {
        baseURL: frontendBaseUrl,
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
        viewport: {
            width: 1440,
            height: 900,
        },
    },
    projects: [
        {
            name: 'setup',
            testMatch: /e2e[\\/]setup[\\/]auth\.setup\.ts/,
        },
        {
            name: 'chromium',
            testIgnore: /e2e[\\/]setup[\\/]/,
            use: {
                browserName: 'chromium',
                storageState: authStatePath,
            },
            dependencies: ['setup'],
        },
    ],
    webServer: useDockerServices
        ? undefined
        : [
              {
                  command: buildCommand(resolvePythonExecutable(), [
                      'manage.py',
                      'runserver',
                      '127.0.0.1:8000',
                      '--noreload',
                  ]),
                  cwd: backendDirectory,
                  env: createBackendEnvironment(),
                  url: `${backendBaseUrl}/health/`,
                  timeout: 120_000,
                  reuseExistingServer: !process.env.CI,
              },
              {
                  command: 'npm run dev:e2e',
                  cwd: frontendDirectory,
                  env: createFrontendEnvironment(),
                  url: `${frontendBaseUrl}/login`,
                  timeout: 120_000,
                  reuseExistingServer: !process.env.CI,
              },
          ],
})
