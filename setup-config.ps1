param(
    [string]$RobloxVersionsPath = (Join-Path $env:LOCALAPPDATA "Roblox\Versions"),
    [string]$ConfigPath = (Join-Path $PSScriptRoot "config.json")
)

$ErrorActionPreference = "SilentlyContinue"

# Inisialisasi default config jika belum ada
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    $defaultCfg = [pscustomobject]@{
        mcpServers = [pscustomobject]@{}
    }
    $json = ConvertTo-Json -InputObject $defaultCfg -Depth 10
    [System.IO.File]::WriteAllText($ConfigPath, "$json`n", (New-Object System.Text.UTF8Encoding($false)))
}

# Deteksi opsional Roblox Studio MCP (jika terpasang)
$studioMcp = Get-ChildItem -Path (Join-Path $RobloxVersionsPath "version-*\StudioMCP.exe") -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($studioMcp) {
    try {
        $configuration = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        if (-not $configuration.PSObject.Properties["mcpServers"]) {
            $configuration | Add-Member -MemberType NoteProperty -Name mcpServers -Value ([pscustomobject]@{})
        }
        $robloxServer = [pscustomobject]@{
            command = $studioMcp.FullName
            args = @("--stdio")
        }
        if ($configuration.mcpServers.PSObject.Properties["roblox"]) {
            $configuration.mcpServers.roblox = $robloxServer
        } else {
            $configuration.mcpServers | Add-Member -MemberType NoteProperty -Name roblox -Value $robloxServer
        }
        $json = ConvertTo-Json -InputObject $configuration -Depth 20
        [System.IO.File]::WriteAllText($ConfigPath, "$json`n", (New-Object System.Text.UTF8Encoding($false)))
        Write-Host "Roblox Studio MCP detected: $($studioMcp.FullName)"
    } catch {
        Write-Host "Notice: Skipped updating Roblox MCP config."
    }
} else {
    Write-Host "Roblox Studio MCP not installed (optional). VS Code & Workspace MCP will be used."
}
exit 0
