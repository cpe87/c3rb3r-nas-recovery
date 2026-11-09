$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$candidates = [System.Collections.Generic.List[string]]::new()
if (Test-Path -LiteralPath '.venv\Scripts\python.exe') { $candidates.Add((Join-Path $PSScriptRoot '.venv\Scripts\python.exe')) }
$launcher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($launcher) {
    $found = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -eq 0 -and $found) { $candidates.Add([string]$found) }
}
foreach ($name in @('python.exe','python3.exe')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\Microsoft\WindowsApps\*') { $candidates.Add($command.Source) }
}
foreach ($pattern in @("$env:LOCALAPPDATA\Programs\Python\Python*\python.exe", "$env:ProgramFiles\Python*\python.exe", "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")) {
    Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object { $candidates.Add($_.FullName) }
}
$runtime = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    & $candidate -c 'import sys, tkinter, venv; assert sys.version_info >= (3,11)' 2>$null
    if ($LASTEXITCODE -eq 0) { $runtime = $candidate; break }
}
if (-not $runtime) {
    Write-Host 'No usable Python 3.11+ found. Install Python with Tcl/Tk from https://www.python.org/downloads/windows/ and run setup again.'
    exit 1
}
Write-Host "Using Python: $runtime"
$target = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if ($runtime -ne $target) {
    & $runtime -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit 1 }
}
& $target -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit 1 }
& $target -c 'import tkinter, paramiko, PIL; print("Dependencies OK")'
exit $LASTEXITCODE
