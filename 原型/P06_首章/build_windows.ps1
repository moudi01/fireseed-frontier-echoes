$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$workspace = Split-Path -Parent (Split-Path -Parent $project)
$toolchain = Join-Path $workspace '.toolchain/godot/editor/Godot_v4.7.2-stable_win64_console.exe'
$python = Join-Path $workspace 'local/p03_sol4_20261105/dist/p03-windows-x64-write-candidate5/runtime/python.exe'
$licenseTool = Join-Path $workspace '_tools/package_godot_licenses.py'
$template = Join-Path $workspace '.toolchain/godot/templates/windows_release_x86_64.exe'
& $python -X utf8 -B $licenseTool preflight --template $template
if ($LASTEXITCODE -ne 0) { throw "P06 Windows notice preflight failed ($LASTEXITCODE)" }
$build = Join-Path $project 'build'
$tag = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
$release = Join-Path $build "windows-$tag"
New-Item -ItemType Directory -Path $release | Out-Null
New-Item -ItemType File -Path (Join-Path $build '.gdignore') -Force | Out-Null
& $toolchain --headless --path $project --log-file (Join-Path $release 'import.log') --import
if ($LASTEXITCODE -ne 0) { throw "Godot asset import failed: $LASTEXITCODE" }
foreach ($script in @('main.gd', 'smoke.gd')) {
    $scriptLog = Join-Path $release 'script-check.log'
    & $toolchain --headless --path $project --log-file $scriptLog --check-only --script "res://$script"
    $scriptExit = $LASTEXITCODE
    if ($scriptExit -ne 0 -or (Select-String -LiteralPath $scriptLog -Pattern 'SCRIPT ERROR|Parse Error|Compile Error')) {
        throw "Script validation failed: $script ($scriptExit). See $scriptLog"
    }
}
& $python -B (Join-Path $project 'sidecar/stage.py') (Join-Path $release 'sidecar') --release-id (Split-Path -Leaf $release)
if ($LASTEXITCODE -ne 0) { throw "Python runtime staging failed ($LASTEXITCODE)" }
& $toolchain --headless --path $project --log-file (Join-Path $release 'export.log') --export-release 'Windows Desktop' (Join-Path $release 'P06.exe')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $release 'P06.exe'))) { throw "Godot export failed ($LASTEXITCODE)" }
Copy-Item -LiteralPath (Join-Path $project 'sidecar/恢复存档.cmd') -Destination $release
& $python -X utf8 -B $licenseTool attach --output $release
if ($LASTEXITCODE -ne 0) { throw "P06 Windows notice staging or verification failed ($LASTEXITCODE)" }
Get-Item -LiteralPath $release | Select-Object -ExpandProperty FullName
