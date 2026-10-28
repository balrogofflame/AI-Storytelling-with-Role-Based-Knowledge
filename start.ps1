param(
    [string]$Model,
    [switch]$CheckOnly,
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python was not found. Install Python 3.10+ and reopen PowerShell.'
}
$previousKey = $env:OPENAI_API_KEY
$previousModel = $env:OPENAI_MODEL
try {
    if (-not [string]::IsNullOrWhiteSpace($Model)) { $env:OPENAI_MODEL = $Model }
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_MODEL)) {
        $env:OPENAI_MODEL = Read-Host 'Enter a Responses API model ID available to your API project'
    }
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        $secureKey = Read-Host 'Paste API key (hidden; kept in memory only)' -AsSecureString
        $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer); $secureKey.Dispose() }
    }
    Write-Host 'Running ONE live API check. This may incur API charges; no automatic retries.'
    & python (Join-Path $PSScriptRoot 'check_ai.py') --live
    if ($LASTEXITCODE -ne 0) { throw 'AI connection check failed. See README.md for setup steps.' }
    if (-not $CheckOnly) {
        & python (Join-Path $PSScriptRoot 'server.py') --port $Port
        if ($LASTEXITCODE -ne 0) { throw 'Local server failed to start.' }
    }
} finally {
    $env:OPENAI_API_KEY = $previousKey
    $env:OPENAI_MODEL = $previousModel
}
