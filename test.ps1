param(
    [switch]$Frontend,
    [switch]$Backend,
    [switch]$E2E
)

# If no flag is passed, run everything. Otherwise run only the selected suites.
$runAll = -not ($Frontend -or $Backend -or $E2E)
$runFrontend = $runAll -or $Frontend
$runBackend  = $runAll -or $Backend
$runE2E      = $runAll -or $E2E

# --- Result tracking & suite runner -----------------------------------------

$results = [System.Collections.Generic.List[pscustomobject]]::new()

function Add-SuiteResult {
    param($Name, $Status, $ExitCode, $Duration, $Passed, $Failed, $Skipped)
    $results.Add([pscustomobject]@{
        Name     = $Name
        Status   = $Status
        ExitCode = $ExitCode
        Duration = $Duration
        Passed   = $Passed
        Failed   = $Failed
        Skipped  = $Skipped
    }) | Out-Null
}

# Strip ANSI escape sequences (e.g. color codes) from a line so regex parsers
# can match on the literal text. Vitest colors its summary even when piped,
# which would otherwise break `\s+` matches between words and numbers.
$stripAnsi = { param($s) ([string]$s) -replace '\e\[[0-9;]*m', '' }

# Pytest summary parser. Looks for the trailing summary line, e.g.
#   ===== 5 passed, 2 failed, 1 skipped, 1 error in 3.45s =====
$pytestParser = {
    param($lines)
    $result = @{ Passed = $null; Failed = $null; Skipped = $null }
    if (-not $lines) { return $result }
    $lines = $lines | ForEach-Object { & $stripAnsi $_ }
    $summary = $lines | Where-Object { $_ -match '=+\s.*\b(passed|failed|error)\b.*\sin\s' } | Select-Object -Last 1
    if ($summary) {
        if ($summary -match '(\d+)\s+passed')  { $result.Passed  = [int]$matches[1] }
        if ($summary -match '(\d+)\s+failed')  { $result.Failed  = [int]$matches[1] }
        if ($summary -match '(\d+)\s+skipped') { $result.Skipped = [int]$matches[1] }
        if ($summary -match '(\d+)\s+error') {
            $existing = if ($null -ne $result.Failed) { $result.Failed } else { 0 }
            $result.Failed = $existing + [int]$matches[1]
        }
    }
    return $result
}

# Vitest summary parser. Looks for the `Tests` summary row, e.g.
#        Tests  5 failed | 42 passed | 1 skipped (48)
$vitestParser = {
    param($lines)
    $result = @{ Passed = $null; Failed = $null; Skipped = $null }
    if (-not $lines) { return $result }
    $lines = $lines | ForEach-Object { & $stripAnsi $_ }
    $summary = $lines | Where-Object { $_ -match '^\s*Tests\s+\d' } | Select-Object -Last 1
    if ($summary) {
        if ($summary -match '(\d+)\s+passed')  { $result.Passed  = [int]$matches[1] }
        if ($summary -match '(\d+)\s+failed')  { $result.Failed  = [int]$matches[1] }
        if ($summary -match '(\d+)\s+skipped') { $result.Skipped = [int]$matches[1] }
    }
    return $result
}

function Invoke-Suite {
    param(
        [string]$Name,
        [scriptblock]$Command,
        [scriptblock]$Parser
    )
    Write-Host ""
    Write-Host "==== Running $Name ====" -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $captured = & $Command 2>&1 | Tee-Object -Variable teed
    $sw.Stop()
    $code = $LASTEXITCODE
    # $captured is the assigned value; $teed is what Tee-Object stored. Prefer $teed
    # since Tee-Object guarantees a string-like list even on a single-line stream.
    $lines = if ($teed) { $teed } else { $captured }
    $counts = & $Parser $lines
    $status = if ($code -eq 0) { 'PASSED' } else { 'FAILED' }
    Add-SuiteResult -Name $Name -Status $status -ExitCode $code -Duration $sw.Elapsed `
        -Passed $counts.Passed -Failed $counts.Failed -Skipped $counts.Skipped
}

# ----------------------------------------------------------------------------

if ($runFrontend) {
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

    Invoke-Suite -Name 'Frontend (vitest)' -Command { npm test } -Parser $vitestParser
}

if ($runBackend -or $runE2E) {
    # Verify python is accessible before running Python-based tests
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "python not found in PATH."
        exit 1
    }

    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($runBackend) {
    Invoke-Suite -Name 'Backend (pytest)' -Command { python -m pytest --ignore=tests/e2e } -Parser $pytestParser
}

if ($runE2E) {
    Invoke-Suite -Name 'E2E (pytest)' -Command { python -m pytest tests/e2e } -Parser $pytestParser
}

# --- Final summary ----------------------------------------------------------

Write-Host ""
Write-Host "================ TEST SUMMARY ================" -ForegroundColor Cyan
$fmt = "{0,-20} {1,-8} {2,5} {3,10} {4,8} {5,8} {6,9}"
Write-Host ($fmt -f 'Suite','Status','Exit','Duration','Passed','Failed','Skipped')
Write-Host ($fmt -f ('-'*20),('-'*8),('-'*5),('-'*10),('-'*8),('-'*8),('-'*9))
foreach ($r in $results) {
    $dur = '{0:mm\:ss\.f}' -f $r.Duration
    $p = if ($null -ne $r.Passed)  { $r.Passed }  else { '-' }
    $f = if ($null -ne $r.Failed)  { $r.Failed }  else { '-' }
    $s = if ($null -ne $r.Skipped) { $r.Skipped } else { '-' }
    $color = if ($r.Status -eq 'PASSED') { 'Green' } else { 'Red' }
    Write-Host ($fmt -f $r.Name, $r.Status, $r.ExitCode, $dur, $p, $f, $s) -ForegroundColor $color
}
Write-Host "==============================================" -ForegroundColor Cyan

$failed = @($results | Where-Object { $_.Status -eq 'FAILED' })
if ($failed.Count -gt 0) {
    Write-Host ("{0} suite(s) failed." -f $failed.Count) -ForegroundColor Red
    exit 1
}
Write-Host "All suites passed." -ForegroundColor Green
exit 0
