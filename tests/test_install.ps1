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
    param(
        [string]$Profile,
        [switch]$AllowExternalSkills
    )

    $HomePath = New-TestHome
    try {
        $env:USERPROFILE = $HomePath
        & (Join-Path $RepoRoot "install.ps1") -Profile $Profile -AllowExternalSkills:$AllowExternalSkills | Out-Null
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

# WHY (2026-07-29): install.ps1 used to seed patterns.md/learning_log.md at
# memory\_auto\, the legacy path -- rules/memory-protocol.md documents
# memory\<name>.md (no _auto\) as canonical, and the hooks that read/write
# these files were already migrated there (PR #242/#243). A fresh install
# silently re-creating the _auto\-vs-canonical split was the exact
# regression these two assertions plus their negative-control pair guard.
Assert-True (Test-Path (Join-Path $FullHome ".claude\memory\patterns.md")) "full seeds patterns.md at canonical path"
Assert-True (Test-Path (Join-Path $FullHome ".claude\memory\learning_log.md")) "full seeds learning_log.md at canonical path"
Assert-True (-not (Test-Path (Join-Path $FullHome ".claude\memory\_auto\patterns.md"))) "full does not seed patterns.md at legacy _auto\ path"
Assert-True (-not (Test-Path (Join-Path $FullHome ".claude\memory\_auto\learning_log.md"))) "full does not seed learning_log.md at legacy _auto\ path"
Assert-True (-not ($SettingsContent -match "C:/Users/[a-zA-Z]+/\.(claude|AppData)")) "settings.json has no author-specific paths"
Assert-True (-not $SettingsContent.Contains("__CLAUDE_HOME__")) "settings.json resolves CLAUDE placeholder"
Assert-True ($SettingsContent.Contains(($FullHome -replace "\\", "/"))) "settings.json includes installed home path"

# WHY (F-05, security audit 2026-07-12): full profile previously cloned
# last30days-skill (unpinned, ungated) unconditionally -- this is the exact
# path CI's windows-install job exercised on every run with zero consent
# and zero commit verification. Regression: must be skipped by default.
Assert-True (-not (Test-Path (Join-Path $FullHome ".claude\skills\last30days"))) "full without -AllowExternalSkills skips last30days"

Remove-Item $MinimalHome -Recurse -Force
Remove-Item $FullHome -Recurse -Force

# WHY: separate opt-in run, since this is the only case that needs network
# access (git clone) -- keep the default full-profile test above network-free.
if (Get-Command git -ErrorAction SilentlyContinue) {
    $ExternalHome = Invoke-InstallCheck -Profile "full" -AllowExternalSkills
    $ExternalTarget = Join-Path $ExternalHome ".claude\skills\last30days"
    Assert-True (Test-Path $ExternalTarget) "full -AllowExternalSkills installs last30days"
    if (Test-Path $ExternalTarget) {
        Push-Location $ExternalTarget
        try {
            $ActualSha = (git rev-parse HEAD).Trim()
            Assert-True ($ActualSha -eq "4bbfee40553d0eb4a25583834335449607c6bea3") "last30days checked out at the pinned SHA"
        } finally {
            Pop-Location
        }
    }
    Remove-Item $ExternalHome -Recurse -Force
} else {
    Write-Host "  SKIP -AllowExternalSkills tests (git not found)" -ForegroundColor DarkGray
}

# WHY (2026-11-18): an existing customized settings.json / CLAUDE.md must survive a plain
# re-run, be replaced only with -ForceReplace, and personal memory must never be overwritten.
# All writes go to a throwaway USERPROFILE; the live ~/.claude is never touched.
$ConflictHome = New-TestHome
$ClaudeHome = Join-Path $ConflictHome ".claude"
New-Item -ItemType Directory -Path $ClaudeHome -Force | Out-Null
Set-Content -Path (Join-Path $ClaudeHome "settings.json") -Value '{"_sentinel":"keep"}' -NoNewline
Set-Content -Path (Join-Path $ClaudeHome "CLAUDE.md") -Value "# my own notes" -NoNewline
$env:USERPROFILE = $ConflictHome
& (Join-Path $RepoRoot "install.ps1") -Profile "standard" | Out-Null
$KeptSettings = Get-Content (Join-Path $ClaudeHome "settings.json") -Raw
$KeptClaude = Get-Content (Join-Path $ClaudeHome "CLAUDE.md") -Raw
Assert-True ($KeptSettings -match "_sentinel") "re-run keeps an existing, differing settings.json"
Assert-True ($KeptClaude -match "my own notes") "re-run keeps an existing, differing CLAUDE.md"
& (Join-Path $RepoRoot "install.ps1") -Profile "standard" -ForceReplace | Out-Null
$ReplacedSettings = Get-Content (Join-Path $ClaudeHome "settings.json") -Raw
Assert-True (-not ($ReplacedSettings -match "_sentinel")) "-ForceReplace replaces settings.json"
Remove-Item $ConflictHome -Recurse -Force

# Personal memory is never overwritten by the seed templates.
$MemoryHome = New-TestHome
$MemoryDir = Join-Path $MemoryHome ".claude\memory"
New-Item -ItemType Directory -Path $MemoryDir -Force | Out-Null
Set-Content -Path (Join-Path $MemoryDir "patterns.md") -Value "# my personal patterns" -NoNewline
$env:USERPROFILE = $MemoryHome
& (Join-Path $RepoRoot "install.ps1") -Profile "full" | Out-Null
$PatternsAfter = Get-Content (Join-Path $MemoryDir "patterns.md") -Raw
Assert-True ($PatternsAfter -match "my personal patterns") "install never overwrites personal memory/patterns.md"
Remove-Item $MemoryHome -Recurse -Force

# WHY (2026-11-18): -Link must never delete a real user skills directory, and must never
# damage the repository through a link. The user's own skill must survive; repo files must stay.
$LinkHome = New-TestHome
$UserSkillDir = Join-Path $LinkHome ".claude\skills\my-own-skill"
New-Item -ItemType Directory -Path $UserSkillDir -Force | Out-Null
Set-Content -Path (Join-Path $UserSkillDir "SKILL.md") -Value "# my own skill" -NoNewline
$env:USERPROFILE = $LinkHome
& (Join-Path $RepoRoot "install.ps1") -Profile "standard" -Link | Out-Null
Assert-True (Test-Path (Join-Path $UserSkillDir "SKILL.md")) "-Link keeps a real user skills directory"
Assert-True (Test-Path (Join-Path $RepoRoot "rules\integrity.md")) "-Link run leaves repository files intact"
Remove-Item $LinkHome -Recurse -Force

Write-Host ""
Write-Host "=== Results: $Pass passed, $Fail failed ==="
exit $Fail
