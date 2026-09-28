# Build the Windows executable locally:
#   pyinstaller packaging/list2audio.spec --noconfirm
# Output: dist/list2audio.exe

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

python -m pip install -e ".[dev]"
pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests failed" }

pyinstaller packaging/list2audio.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "build failed" }

dist\list2audio.exe --version
Write-Host "OK: dist\list2audio.exe" -ForegroundColor Green
