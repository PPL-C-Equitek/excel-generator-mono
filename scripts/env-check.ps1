param(
  [string]$EnvFilePath = ""
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TemplatePath = Join-Path $RootDir ".env.example"
$EnvPath = if ($EnvFilePath) { $EnvFilePath } else { Join-Path $RootDir ".env" }

if (-not (Test-Path -LiteralPath $TemplatePath)) {
  Write-Error "Error: template file not found: $TemplatePath"
}

function Parse-EnvFile {
  param([string]$Path)

  $keys = [System.Collections.Generic.List[string]]::new()
  $seen = @{}
  $malformed = [System.Collections.Generic.List[string]]::new()

  $lines = Get-Content -LiteralPath $Path
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $lineNo = $i + 1
    $line = $lines[$i].TrimEnd("`r")
    $trimmed = $line.Trim()

    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) {
      continue
    }

    if (-not $line.Contains("=")) {
      $malformed.Add("line ${lineNo}: $line")
      continue
    }

    $key = $line.Substring(0, $line.IndexOf("=")).Trim()
    if ($key -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
      $malformed.Add("line ${lineNo}: $line")
      continue
    }

    if (-not $seen.ContainsKey($key)) {
      $keys.Add($key)
      $seen[$key] = $true
    }
  }

  return @{
    Keys = $keys
    Seen = $seen
    Malformed = $malformed
  }
}

if (-not (Test-Path -LiteralPath $EnvPath)) {
  Write-Error "Check failed: .env not found at $EnvPath"
}

$template = Parse-EnvFile -Path $TemplatePath
$envFile = Parse-EnvFile -Path $EnvPath

if ($template.Malformed.Count -gt 0) {
  Write-Output "Check failed: malformed lines in .env.example"
  foreach ($item in $template.Malformed) {
    Write-Output "  - $item"
  }
  exit 1
}

if ($envFile.Malformed.Count -gt 0) {
  Write-Output "Check failed: malformed lines in .env"
  foreach ($item in $envFile.Malformed) {
    Write-Output "  - $item"
  }
  exit 1
}

$missing = [System.Collections.Generic.List[string]]::new()
foreach ($key in $template.Keys) {
  if (-not $envFile.Seen.ContainsKey($key)) {
    $missing.Add($key)
  }
}

if ($missing.Count -gt 0) {
  Write-Output "Check failed: missing required key(s) in .env:"
  foreach ($key in $missing) {
    Write-Output "  - $key"
  }
  exit 1
}

Write-Output "Check passed: .env includes all keys from .env.example"
