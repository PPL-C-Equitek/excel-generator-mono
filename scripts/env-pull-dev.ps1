param(
  [string]$EnvFilePath = ""
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvPath = if ($EnvFilePath) { $EnvFilePath } else { Join-Path $RootDir ".env" }

if (-not (Get-Command infisical -ErrorAction SilentlyContinue)) {
  Write-Error "Error: infisical CLI not found. Install it first: https://infisical.com/docs/cli/overview"
}

$hasToken = -not [string]::IsNullOrWhiteSpace($env:INFISICAL_TOKEN)

Write-Output "Pulling Infisical secrets for env 'dev' into $EnvPath"

$infisicalCommand = "infisical"
$infisicalCmdPath = Join-Path $env:APPDATA "npm\infisical.cmd"
if (Test-Path -LiteralPath $infisicalCmdPath) {
  # Prefer .cmd shim to avoid PowerShell ExternalScript wrapper quirks.
  $infisicalCommand = $infisicalCmdPath
}

$args = @("export", "--format=dotenv", "--env=dev")
if ($hasToken) {
  $args += @("--token=$($env:INFISICAL_TOKEN)")
}
if (-not [string]::IsNullOrWhiteSpace($env:INFISICAL_PROJECT_ID)) {
  $args += @("--projectId=$($env:INFISICAL_PROJECT_ID)")
}

$content = & $infisicalCommand @args
if ($LASTEXITCODE -ne 0) {
  if ($hasToken) {
    Write-Error "Error: failed to export secrets from Infisical using INFISICAL_TOKEN."
  }
  Write-Error "Error: failed to export secrets from Infisical. Run 'infisical login' and 'infisical init' in repo root, or pass project id via INFISICAL_PROJECT_ID."
}

if ([string]::IsNullOrWhiteSpace(($content -join "`n"))) {
  Write-Error "Error: Infisical export returned empty output."
}

[System.IO.File]::WriteAllText($EnvPath, ($content -join "`n"))
Write-Output "Success: wrote secrets to $EnvPath"

& (Join-Path $PSScriptRoot "env-check.ps1") -EnvFilePath $EnvPath
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
