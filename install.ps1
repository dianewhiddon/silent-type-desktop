[CmdletBinding()]
param(
    [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    [switch]$Cuda,
    [switch]$NoShortcut,
    [switch]$SkipModels
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) { throw 'Install 64-bit Python 3.12, or supply its path with -Python.' }
& $Python -c "import sys, struct; sys.exit(0 if sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8 else 1)"
if ($LASTEXITCODE -ne 0) { throw '64-bit Python 3.12 is required.' }

# Preflight the shortcut before modifying the environment.
$ShortcutPath = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Silent Type Desktop.lnk'
$AppPythonw = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$LegacyLauncher = '"' + (Join-Path $PSScriptRoot 'start-silent-type.vbs') + '"'
if (-not $NoShortcut) {
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Ours = ($Shortcut.TargetPath -eq $AppPythonw -and $Shortcut.Arguments -eq '-m silent_type') -or $Shortcut.Arguments -eq $LegacyLauncher
    if ((Test-Path -LiteralPath $ShortcutPath) -and -not $Ours) {
        throw 'A shortcut belongs to another installation. Use -NoShortcut or remove that shortcut yourself.'
    }
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the app environment.' }
}
$AppPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $AppPython -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)"
if ($LASTEXITCODE -ne 0) { throw 'The existing environment uses another Python version. Rename .venv and retry.' }
& $AppPython -m pip install --upgrade pip==26.2.1
if ($LASTEXITCODE -ne 0) { throw 'Could not update the package installer.' }
$Lock = if ($Cuda) { 'requirements-cuda.lock' } else { 'requirements-cpu.lock' }
$TorchIndex = if ($Cuda) { 'https://download.pytorch.org/whl/cu130' } else { 'https://download.pytorch.org/whl/cpu' }
& $AppPython -m pip install --require-hashes --only-binary=:all: --extra-index-url $TorchIndex -r $Lock
if ($LASTEXITCODE -ne 0) { throw 'App dependencies did not install.' }
& $AppPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
if (-not $SkipModels) {
    Write-Output 'Downloading models from their original hosts. See THIRD_PARTY.md for separate checkpoint terms.'
    & $AppPython download_model.py
    if ($LASTEXITCODE -ne 0) { throw 'Model installation failed.' }
    & $AppPython doctor.py
    if ($LASTEXITCODE -ne 0) { throw 'Read the diagnostic result before starting the app.' }
}
& $AppPython -m silent_type.icon
if ($LASTEXITCODE -ne 0) { throw 'Could not draw the app icon.' }
if (-not $NoShortcut) {
    $Shortcut.TargetPath = $AppPythonw
    $Shortcut.Arguments = '-m silent_type'
    $Shortcut.WorkingDirectory = $PSScriptRoot
    $Shortcut.Description = 'Camera-only silent typing'
    $Shortcut.IconLocation = (Join-Path $PSScriptRoot 'silent_type\silent-type.ico') + ',0'
    $Shortcut.Save()
}
if ($SkipModels) {
    Write-Output 'Dependencies installed. Run install.ps1 without -SkipModels before using the app.'
} else {
    Write-Output 'Installed. Open Silent Type Desktop from Start. Startup remains off.'
}
