<#
.SYNOPSIS
    Install Claude Code Configuration on Windows.
.DESCRIPTION
    Installs the same profile layers as install.sh with user-specific path
    substitution for templated files such as CLAUDE.md and settings.json.
.PARAMETER InstallProfile
    Installation profile: minimal, standard, or full.
.PARAMETER Target
    Install only a specific component (e.g. "skills", "rules", "hooks").
    When set, only that component is copied/linked, no CLAUDE.md or settings changes.
.PARAMETER Link
    Use symbolic links for non-templated assets when possible.
.EXAMPLE
    .\install.ps1
    .\install.ps1 -InstallProfile full
    .\install.ps1 -Target skills
    .\install.ps1 -Link
#>
param(
    [ValidateSet("minimal", "standard", "full")]
    # WHY: Alias keeps backward compat with test_install.ps1 which uses -Profile "full"
    [Alias("Profile")]
    [string]$InstallProfile = "standard",
    [ValidateSet("", "skills", "rules", "hooks", "agents", "scripts", "memory")]
    [string]$Target = "",
    [switch]$Link
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeDir = Join-Path $env:USERPROFILE ".claude"
$UserHomeForward = ($env:USERPROFILE -replace "\\", "/")
$ClaudeDirForward = ($ClaudeDir -replace "\\", "/")

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return ($python.Source -replace "\\", "/")
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $resolved = (& py -3 -c "import sys; print(sys.executable)" 2>$null).Trim()
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                return ($resolved -replace "\\", "/")
            }
        } catch {
        }
    }

    return "python"
}

$PythonCmdForward = Get-PythonCommand

Write-Host "Claude Code Configuration Installer (Windows)" -ForegroundColor Cyan
Write-Host "Profile: $InstallProfile | Target: $(if ($Target) { $Target } else { 'all' }) | Link mode: $Link" -ForegroundColor Gray
Write-Host ""

if (Test-Path $ClaudeDir) {
    $BackupDir = "$ClaudeDir.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "Backing up existing config to $BackupDir..." -ForegroundColor Yellow
    Copy-Item -Path $ClaudeDir -Destination $BackupDir -Recurse -Force
}

Ensure-Directory $ClaudeDir

function Install-Files {
    param(
        [string]$Source,
        [string]$Dest,
        [string]$Pattern = "*"
    )

    $SourcePath = Join-Path $ScriptDir $Source
    if (-not (Test-Path $SourcePath)) {
        Write-Host "  Skipping $Source (not found)" -ForegroundColor DarkGray
        return
    }

    $Files = Get-ChildItem -Path $SourcePath -Filter $Pattern -File -ErrorAction SilentlyContinue
    $DestPath = Join-Path $ClaudeDir $Dest
    Ensure-Directory $DestPath

    foreach ($File in $Files) {
        $Target = Join-Path $DestPath $File.Name
        if ($Link) {
            if (Test-Path $Target) {
                Remove-Item $Target -Force
            }
            New-Item -ItemType SymbolicLink -Path $Target -Target $File.FullName -Force | Out-Null
        } else {
            Copy-Item -Path $File.FullName -Destination $Target -Force
        }
    }

    Write-Host "  $Source -> $Dest ($($Files.Count) files)" -ForegroundColor Green
}

function Install-FlatFile {
    param(
        [string]$Source,
        [string]$Dest
    )

    $SourcePath = Join-Path $ScriptDir $Source
    $DestPath = Join-Path $ClaudeDir $Dest
    Ensure-Directory (Split-Path -Parent $DestPath)

    if ($Link) {
        if (Test-Path $DestPath) {
            Remove-Item $DestPath -Force
        }
        New-Item -ItemType SymbolicLink -Path $DestPath -Target $SourcePath -Force | Out-Null
    } else {
        Copy-Item -Path $SourcePath -Destination $DestPath -Force
    }

    Write-Host "  $Source -> $Dest" -ForegroundColor Green
}

function Install-TemplatedFile {
    param(
        [string]$Source,
        [string]$Dest
    )

    $SourcePath = Join-Path $ScriptDir $Source
    $DestPath = Join-Path $ClaudeDir $Dest
    Ensure-Directory (Split-Path -Parent $DestPath)

    $Content = Get-Content $SourcePath -Raw
    $Content = $Content.Replace("__USER_HOME__", $UserHomeForward)
    $Content = $Content.Replace("__CLAUDE_HOME__", $ClaudeDirForward)
    $Content = $Content.Replace("__PYTHON_CMD__", $PythonCmdForward)
    Set-Content -Path $DestPath -Value $Content -NoNewline

    Write-Host "  $Source -> $Dest (templated)" -ForegroundColor Green
}

function Install-Skills {
    $SourcePath = Join-Path $ScriptDir "skills"
    $DestPath = Join-Path $ClaudeDir "skills"
    if (-not (Test-Path $SourcePath)) {
        return
    }

    if ($Link) {
        if (Test-Path $DestPath) {
            Remove-Item $DestPath -Force -Recurse
        }
        New-Item -ItemType SymbolicLink -Path $DestPath -Target $SourcePath -Force | Out-Null
    } else {
        Ensure-Directory $DestPath
        Copy-Item -Path "$SourcePath\*" -Destination $DestPath -Recurse -Force
    }

    $SkillCount = (Get-ChildItem -Path $SourcePath -Recurse -File).Count
    Write-Host "  skills ($SkillCount files)" -ForegroundColor Green
}

# WHY: parity with install.sh — last30days is an external git-clone skill,
# not a local extension directory. Without this, Windows installs miss it.
function Install-ExternalSkills {
    $Target = Join-Path $ClaudeDir "skills\last30days"
    if (Test-Path $Target) {
        Write-Host "  last30days already installed" -ForegroundColor DarkGray
        return
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "  git not found - skip last30days" -ForegroundColor Yellow
        return
    }
    Write-Host "  Cloning last30days-skill..." -ForegroundColor White
    git clone https://github.com/mvanhorn/last30days-skill.git $Target 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  last30days installed" -ForegroundColor Green
    } else {
        Write-Host "  Failed to clone last30days (network?)" -ForegroundColor Yellow
    }
}

function Install-MemoryTemplates {
    # WHY: Join-Path with 3+ args requires PowerShell 7+. Use nested calls for PS 5.1 compat.
    $TemplatesPath = Join-Path (Join-Path $ScriptDir "memory") "templates"
    if (-not (Test-Path $TemplatesPath)) {
        return
    }

    $MemoryDir = Join-Path $ClaudeDir "memory"
    Ensure-Directory $MemoryDir
    Ensure-Directory (Join-Path $MemoryDir "projects")

    $Count = 0
    foreach ($Template in Get-ChildItem -Path $TemplatesPath -Filter "*.template.md" -File) {
        $TargetName = $Template.BaseName -replace "\.template$", ""
        $TargetPath = Join-Path $MemoryDir "$TargetName.md"
        Copy-Item -Path $Template.FullName -Destination $TargetPath -Force
        $Count += 1
    }

    Write-Host "  memory/templates -> memory ($Count files)" -ForegroundColor Green
}

# -Target: install only a single component and exit
if ($Target) {
    switch ($Target) {
        "skills"  { Write-Host "Installing skills..." -ForegroundColor White; Install-Skills }
        "rules"   { Write-Host "Installing rules..." -ForegroundColor White; Install-Files "rules" "rules" "*.md" }
        "hooks"   {
            Write-Host "Installing hooks..." -ForegroundColor White
            Install-Files "hooks" "hooks" "*.py"
            Install-FlatFile "hooks\statusline.py" "statusline.py"
            Install-TemplatedFile "hooks\settings.json" "settings.json"
        }
        "agents"  { Write-Host "Installing agents..." -ForegroundColor White; Install-Files "agents" "agents" "*.md" }
        "scripts" { Write-Host "Installing scripts..." -ForegroundColor White; Install-Files "scripts" "scripts" "*.py" }
        "memory"  { Write-Host "Installing memory templates..." -ForegroundColor White; Install-MemoryTemplates }
    }
    Write-Host "`nTarget '$Target' install complete." -ForegroundColor Green
    exit 0
}

Write-Host "Installing CLAUDE.md..." -ForegroundColor White
Install-TemplatedFile "claude-md\CLAUDE.md" "CLAUDE.md"

Write-Host "Installing core rules..." -ForegroundColor White
Install-Files "rules" "rules" "integrity.md"
Install-Files "rules" "rules" "security.md"

if ($InstallProfile -eq "minimal") {
    Write-Host "`nMinimal install complete." -ForegroundColor Green
    exit 0
}

Write-Host "Installing rules..." -ForegroundColor White
Install-Files "rules" "rules" "*.md"

Write-Host "Installing hooks..." -ForegroundColor White
Install-Files "hooks" "hooks" "*.py"
Install-FlatFile "hooks\statusline.py" "statusline.py"
Install-TemplatedFile "hooks\settings.json" "settings.json"

# WHY: learning hooks WRITE to memory\_auto\. Without the dir + anchor files the
# writes fail silently and the learning loop never closes. Seed idempotently.
Write-Host "Seeding learning memory..." -ForegroundColor White
$AutoDir = Join-Path (Join-Path $ClaudeDir "memory") "_auto"
Ensure-Directory $AutoDir
$PatternsFile = Join-Path $AutoDir "patterns.md"
if (-not (Test-Path $PatternsFile)) {
    @"
# Patterns — accumulated lessons

> Auto-filled by pattern_extractor.py after ``fix:`` commits. Read back at session start.
> Tags: [AVOID] = anti-pattern, [REPEAT] = proven approach, [x N] = recurrence counter.

## Debugging and Fixes

## Architecture Decisions
"@ | Set-Content -Path $PatternsFile -Encoding UTF8
    Write-Host "  seeded memory\_auto\patterns.md" -ForegroundColor Green
}
$LogFile = Join-Path $AutoDir "learning_log.md"
if (-not (Test-Path $LogFile)) {
    @"
# Learning Log

> Auto-filled by learning_tracker.py. Read at session start.

## Machine Log
"@ | Set-Content -Path $LogFile -Encoding UTF8
    Write-Host "  seeded memory\_auto\learning_log.md" -ForegroundColor Green
}

Write-Host "Installing skills..." -ForegroundColor White
Install-Skills

Write-Host "Installing agents..." -ForegroundColor White
Install-Files "agents" "agents" "*.md"

if ($InstallProfile -eq "standard") {
    Write-Host "`nStandard install complete." -ForegroundColor Green
    exit 0
}

Write-Host "Installing scripts..." -ForegroundColor White
Install-Files "scripts" "scripts" "*.py"

Write-Host "Installing MCP profiles..." -ForegroundColor White
Install-Files "mcp-profiles" "mcp-profiles" "*"

Write-Host "Installing memory templates..." -ForegroundColor White
Install-MemoryTemplates

Write-Host "Installing external skills..." -ForegroundColor White
Install-ExternalSkills

New-Item -ItemType File -Path (Join-Path $ClaudeDir ".first-run") -Force | Out-Null

# WHY: warn if git identity is unset — otherwise agent commits get a placeholder author.
$GitEmail = ""
try { $GitEmail = (git config --global user.email) 2>$null } catch {}
if ([string]::IsNullOrWhiteSpace($GitEmail) -or $GitEmail -match 'your_email|placeholder|example\.com|почт') {
    Write-Host "`n! git identity not set — agent commits here would get a placeholder author." -ForegroundColor Yellow
    Write-Host '  Fix once:  git config --global user.email "you@example.com"' -ForegroundColor Yellow
    Write-Host '             git config --global user.name  "Your Name"' -ForegroundColor Yellow
}

Write-Host "`nFull install complete." -ForegroundColor Green
Write-Host "Run 'claude' to start using the configuration." -ForegroundColor Cyan
