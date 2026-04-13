import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDirectory = path.dirname(fileURLToPath(import.meta.url))
const frontendDirectory = path.resolve(currentDirectory, '..')
const repositoryRoot = path.resolve(frontendDirectory, '..')
const dockerComposeFile = path.resolve(repositoryRoot, 'docker-compose.e2e.yml')
const playwrightCli = path.resolve(
    frontendDirectory,
    'node_modules',
    'playwright',
    'cli.js'
)

function resolveCommand(command) {
    return command
}

function run(command, args, env = process.env) {
    const result = spawnSync(resolveCommand(command), args, {
        cwd: frontendDirectory,
        env,
        stdio: 'inherit',
    })

    if (result.error) {
        console.error(result.error.message)
        process.exit(1)
    }

    if (result.status !== 0) {
        process.exit(result.status ?? 1)
    }
}

run('docker', ['compose', '-f', dockerComposeFile, 'up', '-d', '--build', 'db', 'backend', 'frontend'])
run(process.execPath, [playwrightCli, 'install', 'chromium'])
run(
    process.execPath,
    [playwrightCli, 'test', ...process.argv.slice(2)],
    {
        ...process.env,
        PLAYWRIGHT_USE_DOCKER_SERVICES: 'true',
    }
)
