<#
.SYNOPSIS
    Install Claude Code Configuration on Windows.
.DESCRIPTION
    Copies hooks, agents, skills, rules, and memory templates to ~/.claude/.
    Creates backup of existing configuration before overwriting.
.PARAMETER Profile
    Installation profile: minimal (hooks only), standard (hooks+agents+rules), full (everything).
.PARAMETER Link
    Use symbolic links instead of copies (requires admin or Developer Mode).
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

Write-Host "Claude Code Configuration Installer (Windows)" -ForegroundColor Cyan
Write-Host "Profile: $Profile | Link mode: $Link" -ForegroundColor Gray
Write-Host ""

# Backup existing config
if (Test-Path $ClaudeDir) {
    $BackupDir = "$ClaudeDir.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "Backing up existing config to $BackupDir..." -ForegroundColor Yellow
    Copy-Item -Path $ClaudeDir -Destination $BackupDir -Recurse -Force
}

# Ensure target directories exist
$Dirs = @("hooks", "rules", "agents", "skills", "memory", "mcp-profiles")
foreach ($Dir in $Dirs) {
    $Target = Join-Path $ClaudeDir $Dir
    if (-not (Test-Path $Target)) {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
    }
}

function Install-Files {
    param([string]$Source, [string]$Dest, [string]$Pattern = "*")

    $SourcePath = Join-Path $ScriptDir $Source
    if (-not (Test-Path $SourcePath)) {
        Write-Host "  Skipping $Source (not found)" -ForegroundColor DarkGray
        return
    }

    $Files = Get-ChildItem -Path $SourcePath -Filter $Pattern -File -ErrorAction SilentlyContinue
    $DestPath = Join-Path $ClaudeDir $Dest

    foreach ($File in $Files) {
        $Target = Join-Path $DestPath $File.Name
        if ($Link) {
            if (Test-Path $Target) { Remove-Item $Target -Force }
            New-Item -ItemType SymbolicLink -Path $Target -Target $File.FullName -Force | Out-Null
        } else {
            Copy-Item -Path $File.FullName -Destination $Target -Force
        }
    }
    Write-Host "  $Source -> $Dest ($($Files.Count) files)" -ForegroundColor Green
}

# Profile: minimal — hooks only
Write-Host "Installing hooks..." -ForegroundColor White
Install-Files "hooks" "hooks" "*.py"

if ($Profile -eq "minimal") {
    Write-Host "`nMinimal install complete." -ForegroundColor Green
    exit 0
}

# Profile: standard — hooks + agents + rules + claude-md
Write-Host "Installing agents..." -ForegroundColor White
Install-Files "agents" "agents" "*.md"

Write-Host "Installing rules..." -ForegroundColor White
Install-Files "rules" "rules" "*.md"

Write-Host "Installing CLAUDE.md..." -ForegroundColor White
$ClaudeMdSrc = Join-Path $ScriptDir "claude-md" "CLAUDE.md"
if (Test-Path $ClaudeMdSrc) {
    $Content = Get-Content $ClaudeMdSrc -Raw
    $Content = $Content -replace '\$HOME', $env:USERPROFILE
    $Content = $Content -replace '~/', "$($env:USERPROFILE -replace '\\','/')/"
    Set-Content -Path (Join-Path $ClaudeDir "CLAUDE.md") -Value $Content
    Write-Host "  CLAUDE.md installed (paths adjusted)" -ForegroundColor Green
}

Write-Host "Installing memory templates..." -ForegroundColor White
Install-Files "memory" "memory" "*.md"

if ($Profile -eq "standard") {
    Write-Host "`nStandard install complete." -ForegroundColor Green
    exit 0
}

# Profile: full — everything
Write-Host "Installing skills..." -ForegroundColor White
$SkillsPath = Join-Path $ScriptDir "skills"
if (Test-Path $SkillsPath) {
    Copy-Item -Path "$SkillsPath\*" -Destination (Join-Path $ClaudeDir "skills") -Recurse -Force
    $SkillCount = (Get-ChildItem -Path $SkillsPath -Recurse -File).Count
    Write-Host "  skills ($SkillCount files)" -ForegroundColor Green
}

Write-Host "Installing MCP profiles..." -ForegroundColor White
Install-Files "mcp-profiles" "mcp-profiles" "*"

Write-Host "Installing scripts..." -ForegroundColor White
$ScriptsPath = Join-Path $ClaudeDir "scripts"
if (-not (Test-Path $ScriptsPath)) { New-Item -ItemType Directory -Path $ScriptsPath -Force | Out-Null }
Install-Files "scripts" "scripts" "*.py"

Write-Host "`nFull install complete." -ForegroundColor Green
Write-Host "Run 'claude' to start using the configuration." -ForegroundColor Cyan
