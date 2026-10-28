param([switch]$SkipDependencyInstall, [switch]$BackendOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$desktopRoot = Join-Path $projectRoot 'desktop'
$frontendRoot = Join-Path $projectRoot 'frontend'
$buildPython = Join-Path $projectRoot '.venv-desktop-build\Scripts\python.exe'
Set-Location -LiteralPath $projectRoot
$buildTemp = Join-Path $desktopRoot 'build\temp'
New-Item -ItemType Directory -Path $buildTemp -Force | Out-Null
$env:TEMP = $buildTemp
$env:TMP = $buildTemp
$env:ELECTRON_CACHE = Join-Path $desktopRoot 'build\electron-cache'
$env:ELECTRON_BUILDER_CACHE = Join-Path $desktopRoot 'build\electron-builder-cache'
New-Item -ItemType Directory -Path $env:ELECTRON_CACHE,$env:ELECTRON_BUILDER_CACHE -Force | Out-Null
# @electron/get uses the Windows LocalAppData path even when ELECTRON_CACHE is set.
$env:LOCALAPPDATA = Join-Path $desktopRoot 'build\localappdata'
New-Item -ItemType Directory -Path $env:LOCALAPPDATA -Force | Out-Null
if (-not (Test-Path -LiteralPath $buildPython)) { python -m venv (Join-Path $projectRoot '.venv-desktop-build') }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.venv-desktop-build\Lib\site-packages\pip\__init__.py'))) {
    & $buildPython -m ensurepip --upgrade --default-pip
    if ($LASTEXITCODE -ne 0) { throw 'Desktop build environment could not initialize pip.' }
}
if (-not $SkipDependencyInstall) {
    & $buildPython -m pip install 'numpy==2.5.3' 'pillow==12.3.0' 'pyinstaller==6.22.3'
    if ($LASTEXITCODE -ne 0) { throw 'Python desktop build dependencies failed to install.' }
    Push-Location $frontendRoot
    try { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend npm ci failed.' } } finally { Pop-Location }
    Push-Location $desktopRoot
    try { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Electron npm ci failed.' } } finally { Pop-Location }
}
Push-Location $frontendRoot
try { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } } finally { Pop-Location }
& $buildPython (Join-Path $PSScriptRoot 'generate_desktop_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Desktop icon generation failed.' }
$manifest = Join-Path $desktopRoot 'build\desktop_provenance.json'
New-Item -ItemType Directory -Path (Split-Path $manifest) -Force | Out-Null
& $buildPython (Join-Path $PSScriptRoot 'write_desktop_provenance.py') $manifest
if ($LASTEXITCODE -ne 0) { throw 'Build provenance could not be recorded.' }
& $buildPython -m PyInstaller --noconfirm --clean --onedir --console `
    --name QuantumLaboratoryCore `
    --distpath (Join-Path $desktopRoot 'build') `
    --workpath (Join-Path $desktopRoot 'build\pyi-work') `
    --specpath (Join-Path $desktopRoot 'build') `
    --paths $projectRoot `
    --add-data "${frontendRoot}\dist;frontend\dist" `
    --add-data "${projectRoot}\data\references\hensen_2015\original_files;data\references\hensen_2015\original_files" `
    --add-data "${projectRoot}\data\references\hensen_2016\original_files;data\references\hensen_2016\original_files" `
    --add-data "${projectRoot}\results\stage5b\experiment;results\stage5b\experiment" `
    --add-data "${manifest};." `
    (Join-Path $PSScriptRoot 'desktop_backend.py')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
if ($BackendOnly) { return }
Push-Location $desktopRoot
try { npm run dist; if ($LASTEXITCODE -ne 0) { throw 'Electron installer build failed.' } } finally { Pop-Location }
$artifacts = @('QuantumLaboratory-Setup.exe', 'QuantumLaboratory-Portable.exe')
$checksums = foreach ($artifact in $artifacts) {
    $file = Join-Path $desktopRoot "release\$artifact"
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing release artifact: $artifact" }
    $hash = Get-FileHash -LiteralPath $file -Algorithm SHA256
    "{0}  {1}" -f $hash.Hash.ToLowerInvariant(), $artifact
}
Set-Content -LiteralPath (Join-Path $desktopRoot 'release\SHA256SUMS.txt') -Value $checksums -Encoding ascii
Get-Item (Join-Path $desktopRoot 'release\QuantumLaboratory-*.exe') | Select-Object Name,Length
