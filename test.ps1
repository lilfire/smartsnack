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
    # Find best installed nvm version >= required.
    # nvm list output may contain ANSI codes, markers like *, and extra whitespace —
    # strip everything except the version number.
    $versions = nvm list | ForEach-Object {
        $line = $_ -replace '\e\[[0-9;]*m', ''   # strip ANSI escape codes
        $line = $line -replace '[* ]', ''          # strip markers and spaces
        if ($line -match '^(\d+\.\d+\.\d+)$') { $matches[1] }
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

    # The nvm symlink directory (where node.exe/npm.cmd live) may not yet be in
    # the registry PATH that we just read.  Add it explicitly so npm resolves.
    $nvmSymlink = $env:NVM_SYMLINK
    if (-not $nvmSymlink) {
        $nvmSymlink = [Environment]::GetEnvironmentVariable('NVM_SYMLINK', 'Machine')
    }
    if (-not $nvmSymlink) {
        $nvmSymlink = [Environment]::GetEnvironmentVariable('NVM_SYMLINK', 'User')
    }
    if ($nvmSymlink -and ($env:Path -split ';' | ForEach-Object { $_.TrimEnd('\') }) -notcontains $nvmSymlink.TrimEnd('\')) {
        $env:Path = "$nvmSymlink;$env:Path"
    }
}

# Verify npm is accessible before running tests
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm not found in PATH after nvm switch. Check your nvm-windows installation."
    Write-Error "Current PATH: $env:Path"
    exit 1
}

npm test
