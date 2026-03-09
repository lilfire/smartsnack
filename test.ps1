# Switch to the correct Node.js version and run tests
$nvmrc = Get-Content .nvmrc -ErrorAction Stop
$required = $nvmrc.Trim()

# Get currently installed nvm versions and pick the newest one >= required
$versions = nvm list | ForEach-Object {
    if ($_ -match '(\d+\.\d+\.\d+)') { $matches[1] }
} | Where-Object {
    [int]($_ -split '\.')[0] -ge [int]$required
} | Sort-Object { [version]$_ } -Descending

if (-not $versions) {
    Write-Error "No Node.js version >= $required found. Run: nvm install $required"
    exit 1
}

$best = $versions[0]
Write-Host "Switching to Node.js $best..."
nvm use $best
npm test
