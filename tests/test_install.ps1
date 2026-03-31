$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Pass = 0
$Fail = 0

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if ($Condition) {
        Write-Host "  PASS $Message" -ForegroundColor Green
        $script:Pass += 1
    } else {
        Write-Host "  FAIL $Message" -ForegroundColor Red
        $script:Fail += 1
    }
}

function New-TestHome {
    $Path = Join-Path ([System.IO.Path]::GetTempPath()) ("claude-config-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    return $Path
}

function Invoke-InstallCheck {
    param([string]$Profile)

    $HomePath = New-TestHome
    try {
        $env:USERPROFILE = $HomePath
        & (Join-Path $RepoRoot "install.ps1") -Profile $Profile | Out-Null
        return $HomePath
    } catch {
        Write-Host $_
        throw
    }
}

Write-Host "=== install.ps1 smoke tests ==="
Write-Host ""

$MinimalHome = Invoke-InstallCheck -Profile "minimal"
Assert-True (Test-Path (Join-Path $MinimalHome ".claude\CLAUDE.md")) "minimal installs CLAUDE.md"
Assert-True (Test-Path (Join-Path $MinimalHome ".claude\rules\integrity.md")) "minimal installs integrity.md"
Assert-True (Test-Path (Join-Path $MinimalHome ".claude\rules\security.md")) "minimal installs security.md"

$FullHome = Invoke-InstallCheck -Profile "full"
$SettingsPath = Join-Path $FullHome ".claude\settings.json"
$SettingsContent = Get-Content $SettingsPath -Raw
Assert-True (Test-Path $SettingsPath) "full installs settings.json"
Assert-True (Test-Path (Join-Path $FullHome ".claude\scripts\redact.py")) "full installs scripts"
Assert-True (Test-Path (Join-Path $FullHome ".claude\mcp-profiles\core.json")) "full installs MCP profiles"
Assert-True (Test-Path (Join-Path $FullHome ".claude\memory\activeContext.md")) "full installs memory templates"
Assert-True (-not ($SettingsContent -match "C:/Users/[a-zA-Z]+/\.(claude|AppData)")) "settings.json has no author-specific paths"
Assert-True (-not $SettingsContent.Contains("__CLAUDE_HOME__")) "settings.json resolves CLAUDE placeholder"
Assert-True ($SettingsContent.Contains(($FullHome -replace "\\", "/"))) "settings.json includes installed home path"

Remove-Item $MinimalHome -Recurse -Force
Remove-Item $FullHome -Recurse -Force

Write-Host ""
Write-Host "=== Results: $Pass passed, $Fail failed ==="
exit $Fail
