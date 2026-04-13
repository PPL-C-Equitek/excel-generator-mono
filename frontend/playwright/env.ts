import fs from 'node:fs'
import path from 'node:path'

export const frontendDirectory = path.resolve(__dirname, '..')
export const repositoryRoot = path.resolve(frontendDirectory, '..')
export const backendDirectory = path.resolve(repositoryRoot, 'backend')
export const dockerComposeFile = path.resolve(
    repositoryRoot,
    'docker-compose.e2e.yml'
)

export const frontendBaseUrl =
    process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000'
export const backendBaseUrl =
    process.env.PLAYWRIGHT_BACKEND_URL ?? 'http://localhost:8000'
export const useDockerServices =
    process.env.PLAYWRIGHT_USE_DOCKER_SERVICES === 'true' ||
    process.env.PLAYWRIGHT_USE_DOCKER_SERVICES === '1'

export const e2eUserEmail =
    process.env.E2E_USER_EMAIL ?? 'e2e.user@example.com'
export const e2eUserPassword =
    process.env.E2E_USER_PASSWORD ?? 'E2E-Test#123'
export const e2eUserName = process.env.E2E_USER_NAME ?? 'E2E User'
export const e2eSeedSchemaName =
    process.env.E2E_SEED_SCHEMA_NAME ?? 'E2E Baseline Schema'
export const e2eSeedHistoryName =
    process.env.E2E_SEED_HISTORY_NAME ?? 'e2e-upload-report.pdf'

export const authStatePath = path.resolve(
    frontendDirectory,
    'playwright',
    '.auth',
    'user.json'
)

function quoteCommandPart(value: string): string {
    if (value.includes(' ') || value.includes('"')) {
        return `"${value.replace(/"/g, '\\"')}"`
    }

    return value
}

export function resolvePythonExecutable(): string {
    const windowsVenvPython = path.resolve(
        backendDirectory,
        'venv',
        'Scripts',
        'python.exe'
    )

    if (process.platform === 'win32' && fs.existsSync(windowsVenvPython)) {
        return windowsVenvPython
    }

    return process.platform === 'win32' ? 'python' : 'python3'
}

export function buildCommand(executable: string, args: string[]): string {
    return [quoteCommandPart(executable), ...args.map(quoteCommandPart)].join(' ')
}

export function createBackendEnvironment(): NodeJS.ProcessEnv {
    const mediaRoot = process.env.MEDIA_ROOT ?? './media'

    return {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        DJANGO_SECRET_KEY: process.env.DJANGO_SECRET_KEY ?? 'e2e-django-secret',
        JWT_SECRET_KEY: process.env.JWT_SECRET_KEY ?? 'e2e-jwt-secret',
        DJANGO_DEBUG: process.env.DJANGO_DEBUG ?? 'True',
        DJANGO_ALLOWED_HOSTS:
            process.env.DJANGO_ALLOWED_HOSTS ?? '127.0.0.1,localhost',
        DJANGO_CORS_ALLOWED_ORIGINS:
            process.env.DJANGO_CORS_ALLOWED_ORIGINS ??
            `${frontendBaseUrl},http://localhost:3000`,
        FRONTEND_URL: process.env.FRONTEND_URL ?? frontendBaseUrl,
        POSTGRES_DB: process.env.POSTGRES_DB ?? 'excel_generator_e2e',
        POSTGRES_USER: process.env.POSTGRES_USER ?? 'excel_e2e',
        POSTGRES_PASSWORD: process.env.POSTGRES_PASSWORD ?? 'excel_e2e',
        POSTGRES_HOST: process.env.POSTGRES_HOST ?? '127.0.0.1',
        POSTGRES_PORT: process.env.POSTGRES_PORT ?? '55432',
        GOOGLE_OAUTH_CLIENT_ID:
            process.env.GOOGLE_OAUTH_CLIENT_ID ?? 'mock-google-client-id',
        RESEND_FROM_EMAIL:
            process.env.RESEND_FROM_EMAIL ?? 'noreply@example.com',
        MEDIA_ROOT: mediaRoot,
        CSV_EXPORT_DIR:
            process.env.CSV_EXPORT_DIR ?? `${mediaRoot}/exports/csv`,
        EXCEL_EXPORT_DIR:
            process.env.EXCEL_EXPORT_DIR ?? `${mediaRoot}/exports/excel`,
        TESSERACT_LANG: process.env.TESSERACT_LANG ?? 'eng',
        E2E_TESTING: 'true',
    }
}

export function createFrontendEnvironment(): NodeJS.ProcessEnv {
    return {
        ...process.env,
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? backendBaseUrl,
        NEXT_PUBLIC_GOOGLE_CLIENT_ID:
            process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? 'mock-google-client-id',
        E2E_TESTING: 'true',
    }
}
