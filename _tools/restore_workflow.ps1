param(
    [Parameter(Mandatory=$true)][string]$PackagesFolder,
    [string]$Checkout,
    [string]$AssetsFolder,
    [string[]]$Package,
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (!$Checkout) { $Checkout = Split-Path -Parent $PSScriptRoot }
$root = [IO.Path]::GetFullPath($Checkout).TrimEnd('\')
if (!$AssetsFolder) { $AssetsFolder = $root + '-assets' }
$artRoot = [IO.Path]::GetFullPath($AssetsFolder).TrimEnd('\')
$source = (Resolve-Path -LiteralPath $PackagesFolder).Path
$catalogPath = Join-Path $PSScriptRoot 'workflow-packages.json'
$catalog = Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json
$checked = @{}
function Get-Digest([IO.Stream]$stream) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Get-PathDigest([string]$path) {
    $stream = [IO.File]::OpenRead($path)
    try { return Get-Digest $stream } finally { $stream.Dispose() }
}
function Assert-PlainDirectory([string]$path) {
    if ($checked.ContainsKey($path)) { return }
    if ($path -ne $root -and $path -ne $artRoot) { Assert-PlainDirectory ([IO.Path]::GetDirectoryName($path)) }
    if ([IO.Directory]::Exists($path)) {
        if ([IO.File]::GetAttributes($path) -band [IO.FileAttributes]::ReparsePoint) { throw "Redirected directory: $path" }
    } else { [void][IO.Directory]::CreateDirectory($path) }
    $checked[$path] = $true
}
function Get-TargetPath([string]$rel) {
    if (!$rel -or $rel -match '(^|/)(\.\.?|\.git)(/|$)|(^/)|//|[\\:<>"|?*]') { throw "Invalid path: $rel" }
    $base = $artRoot
    if ($rel -match '^(\.toolchain|local/p03_sol4_20261105|原型/P06_首章|原型/P05_独立样段|游戏/AI觉醒Boss)/') { $base = $root }
    $path = [IO.Path]::GetFullPath([IO.Path]::Combine($base,$rel))
    if (!$path.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected destination: $rel" }
    return $path
}
function Copy-VerifiedFile([string]$from,[string]$to,[string]$digest) {
    $parent = [IO.Path]::GetDirectoryName($to)
    Assert-PlainDirectory $parent
    if ([IO.File]::Exists($to)) {
        if (([IO.File]::GetAttributes($to) -band [IO.FileAttributes]::ReparsePoint) -or (Get-PathDigest $to) -ne $digest) { throw "Existing file differs: $to" }
        return
    }
    $tmp = Join-Path $parent ([IO.Path]::GetRandomFileName())
    try {
        [IO.File]::Copy($from,$tmp)
        if ((Get-PathDigest $tmp) -ne $digest) { throw "Incorrect source: $from" }
        [IO.File]::Move($tmp,$to)
    } finally { if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) } }
}
$selected = @($catalog | Where-Object { !$Package -or $_.name -in $Package })
if (!$selected.Count -or ($Package | Where-Object { $_ -notin $catalog.name })) { throw 'Unknown package name' }
foreach ($part in $selected) {
    $zipPath = Join-Path $source $part.name
    if ((Get-Item -LiteralPath $zipPath).Length -ne $part.size -or (Get-PathDigest $zipPath) -ne $part.sha256) {
        throw "Incorrect archive: $zipPath"
    }
    $zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $reader = [IO.StreamReader]::new($zip.GetEntry('workflow-files.json').Open(), [Text.Encoding]::UTF8)
        try { $rows = ConvertFrom-Json -InputObject $reader.ReadToEnd() } finally { $reader.Dispose() }
        if ($rows.Count -ne $part.files -or $zip.Entries.Count -ne ($part.files+1)) { throw "Incomplete archive: $zipPath" }
        if (!$VerifyOnly) {
            foreach ($row in $rows) {
                $rel = [string]$row[0]
                $dest = Get-TargetPath $rel
                $parent = [IO.Path]::GetDirectoryName($dest)
                Assert-PlainDirectory $parent
                $entry = $zip.GetEntry($rel)
                if (!$entry -or $entry.Length -ne [long]$row[1]) { throw "Missing or incomplete: $rel" }
                if ([IO.File]::Exists($dest)) {
                    if (([IO.File]::GetAttributes($dest) -band [IO.FileAttributes]::ReparsePoint) -or (Get-PathDigest $dest) -ne $row[2]) { throw "Existing file differs: $dest" }
                    continue
                }
                $temp = Join-Path $parent ([IO.Path]::GetRandomFileName())
                try {
                    $inputStream = $entry.Open()
                    try {
                        $outputStream = [IO.File]::Open($temp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
                        try { $inputStream.CopyTo($outputStream) } finally { $outputStream.Dispose() }
                    } finally { $inputStream.Dispose() }
                    if ((Get-PathDigest $temp) -ne $row[2]) { throw "Incorrect restored payload: $rel" }
                    [IO.File]::Move($temp,$dest)
                } finally { if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) } }
            }
        }
        Write-Output ("{0}  {1} files" -f $part.name,$part.files)
    } finally { $zip.Dispose() }
}
if (!$VerifyOnly) {
    $aliases = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'asset-aliases.json') | ConvertFrom-Json
    foreach ($asset in $aliases) {
        $from = Get-TargetPath $asset.source
        if (![IO.File]::Exists($from)) {
            if ($Package) { continue }
            throw "Missing asset for $($asset.path): $from"
        }
        Copy-VerifiedFile $from (Get-TargetPath $asset.path) $asset.sha256
    }
    $guide = Join-Path (Split-Path -Parent $PSScriptRoot) '文档/主用模型.md'
    Copy-VerifiedFile $guide (Get-TargetPath '动画/主用模型.md') (Get-PathDigest $guide)
    Write-Output "Art library: $artRoot"
}
