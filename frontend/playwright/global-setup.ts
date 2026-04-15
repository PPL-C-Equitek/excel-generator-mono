import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import {
    authStatePath,
    backendDirectory,
    backendBaseUrl,
    createBackendEnvironment,
    dockerComposeFile,
    e2eUserEmail,
    e2eUserName,
    e2eUserPassword,
    frontendBaseUrl,
    resolvePythonExecutable,
    useDockerServices,
} from './env'

const DATABASE_READY_RETRIES = 15
const DATABASE_READY_DELAY_MS = 2_000
const SERVICE_READY_RETRIES = 30

function runPythonCommand(args: string[]) {
    return spawnSync(resolvePythonExecutable(), args, {
        cwd: backendDirectory,
        env: createBackendEnvironment(),
        stdio: 'inherit',
    })
}

function runDockerComposeCommand(args: string[]) {
    return spawnSync(
        'docker',
        ['compose', '-f', dockerComposeFile, ...args],
        {
            cwd: backendDirectory,
            env: process.env,
            stdio: 'inherit',
        }
    )
}

async function waitForHttpReady(url: string, label: string) {
    let lastError: Error | null = null

    for (let attempt = 1; attempt <= SERVICE_READY_RETRIES; attempt += 1) {
        try {
            const response = await fetch(url, { redirect: 'manual' })
            if (response.ok || response.status === 302 || response.status === 307) {
                return
            }

            lastError = new Error(
                `${label} is not ready yet (status ${response.status}).`
            )
        } catch (error) {
            lastError =
                error instanceof Error
                    ? error
                    : new Error(`${label} is not reachable yet.`)
        }

        await new Promise((resolve) =>
            globalThis.setTimeout(resolve, DATABASE_READY_DELAY_MS)
        )
    }

    throw lastError ?? new Error(`Failed to reach ${label}.`)
}

async function waitForDatabaseAndMigrate() {
    let lastError: Error | null = null

    for (let attempt = 1; attempt <= DATABASE_READY_RETRIES; attempt += 1) {
        const result = runPythonCommand(['manage.py', 'migrate', '--noinput'])
        if (result.status === 0) {
            return
        }

        lastError = new Error(
            `Database not ready for Django migrations (attempt ${attempt}/${DATABASE_READY_RETRIES}).`
        )
        await new Promise((resolve) =>
            globalThis.setTimeout(resolve, DATABASE_READY_DELAY_MS)
        )
    }

    throw lastError ?? new Error('Failed to prepare the e2e database.')
}

async function waitForDockerServicesAndPrepareDatabase() {
    let lastError: Error | null = null

    for (let attempt = 1; attempt <= DATABASE_READY_RETRIES; attempt += 1) {
        const result = runDockerComposeCommand([
            'exec',
            '-T',
            'backend',
            'python',
            'manage.py',
            'migrate',
            '--noinput',
        ])

        if (result.status === 0) {
            await Promise.all([
                waitForHttpReady(`${backendBaseUrl}/health/`, 'Backend service'),
                waitForHttpReady(`${frontendBaseUrl}/login`, 'Frontend service'),
            ])
            return
        }

        lastError = new Error(
            `Docker backend is not ready for migrations (attempt ${attempt}/${DATABASE_READY_RETRIES}).`
        )
        await new Promise((resolve) =>
            globalThis.setTimeout(resolve, DATABASE_READY_DELAY_MS)
        )
    }

    throw lastError ?? new Error('Failed to prepare docker e2e services.')
}

export default async function globalSetup() {
    fs.mkdirSync(path.dirname(authStatePath), { recursive: true })
    fs.rmSync(authStatePath, { force: true })

    if (useDockerServices) {
        await waitForDockerServicesAndPrepareDatabase()
    } else {
        await waitForDatabaseAndMigrate()
    }

    const seedResult = useDockerServices
        ? runDockerComposeCommand([
              'exec',
              '-T',
              'backend',
              'python',
              'manage.py',
              'seed_e2e',
              '--reset',
              '--email',
              e2eUserEmail,
              '--password',
              e2eUserPassword,
              '--name',
              e2eUserName,
          ])
        : runPythonCommand([
              'manage.py',
              'seed_e2e',
              '--reset',
              '--email',
              e2eUserEmail,
              '--password',
              e2eUserPassword,
              '--name',
              e2eUserName,
          ])

    if (seedResult.status !== 0) {
        throw new Error('Failed to seed deterministic e2e data.')
    }
}
