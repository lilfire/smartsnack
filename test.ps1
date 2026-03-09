# Switch to the correct Node.js version (if needed) and run tests
$nvmrc = Get-Content .nvmrc -ErrorAction Stop
$requiredMajor = [int]$nvmrc.Trim()

# Check current Node.js version
$currentNode = $null
try {
    $currentNode = node --version 2>$null
} catch {}

$needSwitch = $true
if ($currentNode -match '^v?(\d+)') {
    $currentMajor = [int]$matches[1]
    if ($currentMajor -ge $requiredMajor) {
        Write-Host "Already using Node.js $currentNode (>= $requiredMajor), no switch needed."
        $needSwitch = $false
    }
}

if ($needSwitch) {
    # Find best installed nvm version >= required
    $versions = nvm list | ForEach-Object {
        if ($_ -match '(\d+\.\d+\.\d+)') { $matches[1] }
    } | Where-Object {
        [int]($_ -split '\.')[0] -ge $requiredMajor
    } | Sort-Object { [version]$_ } -Descending

    if (-not $versions) {
        Write-Error "No Node.js version >= $requiredMajor found. Run: nvm install $requiredMajor"
        exit 1
    }

    $best = $versions[0]
    Write-Host "Switching to Node.js $best..."
    nvm use $best

    # nvm-windows updates the system PATH but the current process still has the old one.
    # Refresh PATH from the registry so npm/node resolve correctly.
    $machPath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machPath;$userPath"
}

npm test
