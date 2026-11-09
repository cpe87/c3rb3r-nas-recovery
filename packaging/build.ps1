param([string]$Compiler)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$python=Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python packaging\prepare_bundle.py
if ($LASTEXITCODE -ne 0) { throw 'Bundle preparation failed' }
if (-not (Test-Path -LiteralPath 'packaging\FFmpeg-9.0.2-corresponding-source.zip')) { throw 'Matching FFmpeg source bundle is required' }
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name NAS-Recovery-Public --version-file packaging/version-info.txt --add-data 'engine/*.py:engine' --add-data 'tools:tools' --add-data 'THIRD_PARTY_LICENSES:THIRD_PARTY_LICENSES' --add-data 'README.md:.' --add-data 'LICENSE:.' --add-data 'developer.json:.' --add-data 'release/NAS-Recovery-Public-0.1.3-source.zip:source' --add-data 'packaging/FFmpeg-9.0.2-corresponding-source.zip:source' app.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
if ($Compiler) {
 & $Compiler packaging\installer.iss
 if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
}
