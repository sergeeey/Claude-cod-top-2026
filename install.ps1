<#
.SYNOPSIS
    Install Claude Code Configuration on Windows.
.DESCRIPTION
    Installs the same profile layers as install.sh with user-specific path
    substitution for templated files such as CLAUDE.md and settings.json.
.PARAMETER Profile
    Installation profile: minimal, standard, or full.
.PARAMETER Link
    Use symbolic links for non-templated assets when possible.
.EXAMPLE
    .\install.ps1
    .\install.ps1 -Profile full
    .\install.ps1 -Link
#>
param(
    [ValidateSet("minimal", "standard", "full")]
    [string]$Profile = "standard",
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
Write-Host "Profile: $Profile | Link mode: $Link" -ForegroundColor Gray
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

function Install-MemoryTemplates {
    $TemplatesPath = Join-Path $ScriptDir "memory" "templates"
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

Write-Host "Installing CLAUDE.md..." -ForegroundColor White
Install-TemplatedFile "claude-md\CLAUDE.md" "CLAUDE.md"

Write-Host "Installing core rules..." -ForegroundColor White
Install-Files "rules" "rules" "integrity.md"
Install-Files "rules" "rules" "security.md"

if ($Profile -eq "minimal") {
    Write-Host "`nMinimal install complete." -ForegroundColor Green
    exit 0
}

Write-Host "Installing rules..." -ForegroundColor White
Install-Files "rules" "rules" "*.md"

Write-Host "Installing hooks..." -ForegroundColor White
Install-Files "hooks" "hooks" "*.py"
Install-FlatFile "hooks\statusline.py" "statusline.py"
Install-TemplatedFile "hooks\settings.json" "settings.json"

Write-Host "Installing skills..." -ForegroundColor White
Install-Skills

Write-Host "Installing agents..." -ForegroundColor White
Install-Files "agents" "agents" "*.md"

if ($Profile -eq "standard") {
    Write-Host "`nStandard install complete." -ForegroundColor Green
    exit 0
}

Write-Host "Installing scripts..." -ForegroundColor White
Install-Files "scripts" "scripts" "*.py"

Write-Host "Installing MCP profiles..." -ForegroundColor White
Install-Files "mcp-profiles" "mcp-profiles" "*"

Write-Host "Installing memory templates..." -ForegroundColor White
Install-MemoryTemplates

New-Item -ItemType File -Path (Join-Path $ClaudeDir ".first-run") -Force | Out-Null

Write-Host "`nFull install complete." -ForegroundColor Green
Write-Host "Run 'claude' to start using the configuration." -ForegroundColor Cyan
