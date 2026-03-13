# MCP Profile Switcher for Claude Code
# Usage: .\switch-profile.ps1 core|science|deploy
# Or add to PowerShell profile as aliases

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("core", "science", "deploy")]
    [string]$Profile
)

$profilePath = "$env:USERPROFILE\.claude\mcp-profiles\$Profile.json"
$configPath = "$env:USERPROFILE\.claude.json"

if (-not (Test-Path $profilePath)) {
    Write-Host "Profile not found: $profilePath" -ForegroundColor Red
    exit 1
}

# Read current config and profile
$config = Get-Content $configPath -Raw | ConvertFrom-Json
$profile = Get-Content $profilePath -Raw | ConvertFrom-Json

# Replace mcpServers section
$config.mcpServers = $profile.mcpServers

# Write back
$config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8

$serverCount = ($profile.mcpServers.PSObject.Properties | Measure-Object).Count
Write-Host "MCP profile switched to: $Profile ($serverCount servers)" -ForegroundColor Green
Write-Host "Restart Claude Code to apply changes." -ForegroundColor Yellow
