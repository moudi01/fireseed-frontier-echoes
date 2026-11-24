$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$workspace = Split-Path -Parent (Split-Path -Parent $project)
$toolchain = Join-Path $workspace '.toolchain/godot/editor/Godot_v4.7.2-stable_win64_console.exe'
$python = Join-Path $workspace 'local/p03_sol4_20261105/dist/p03-windows-x64-write-candidate5/runtime/python.exe'
$build = Join-Path $project 'build'
$tag = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
$release = Join-Path $build "windows-$tag"
New-Item -ItemType Directory -Path $release | Out-Null
New-Item -ItemType File -Path (Join-Path $build '.gdignore') -Force | Out-Null
foreach ($script in @('main.gd', 'smoke.gd')) {
    & $toolchain --headless --path $project --log-file (Join-Path $release 'script-check.log') --check-only --script "res://$script"
    if ($LASTEXITCODE -ne 0) { throw "Script validation failed: $script ($LASTEXITCODE)" }
}
& $python -B (Join-Path $project 'sidecar/stage.py') (Join-Path $release 'sidecar')
if ($LASTEXITCODE -ne 0) { throw "Python runtime staging failed ($LASTEXITCODE)" }
& $toolchain --headless --path $project --log-file (Join-Path $release 'export.log') --export-release 'Windows Desktop' (Join-Path $release 'P05.exe')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $release 'P05.exe'))) { throw "Godot export failed ($LASTEXITCODE)" }
Get-Item -LiteralPath $release | Select-Object -ExpandProperty FullName
