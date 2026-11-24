[CmdletBinding(DefaultParameterSetName = 'New')]
param(
    [Parameter(ParameterSetName = 'New')]
    [ValidateSet('chapter', 'chapter-book-readers', 'chapter-books', 'archive-review', 'archive', 'town', 'overlook', 'scouting-exit', 'road', 'root', 'ado', 'ado-warning', 'ado-roll-call', 'ado-report', 'ado-remembrance', 'ado-return', 'guard', 'trench', 'dry-island', 'tidal-yard', 'north-levee', 'wetland-map', 'shallow-bay', 'north-gap', 'watchtower-gate', 'missing-search', 'missing-pair', 'transfer-yard', 'spear', 'skeletons', 'spoils', 'handbook', 'bookstore', 'book-slot-swap', 'book-target', 'book-research', 'construction', 'logistics', 'consumables')]
    [string]$Scene = 'ado',
    [Parameter(Mandatory, ParameterSetName = 'Resume')]
    [string]$Resume,
    [Parameter(Mandatory, ParameterSetName = 'Recover')]
    [string]$Recover,
    [Parameter(Mandatory, ParameterSetName = 'Inspect')]
    [string]$Inspect,
    [Parameter(ParameterSetName = 'New')]
    [Parameter(ParameterSetName = 'Resume')]
    [Parameter(ParameterSetName = 'Recover')]
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'playtest.cmd'
$launchArgs = @('--scene', $Scene)
if ($PSCmdlet.ParameterSetName -eq 'Resume') {
    $launchArgs = @('--resume', $Resume)
} elseif ($PSCmdlet.ParameterSetName -eq 'Recover') {
    $launchArgs = @('--recover', $Recover)
} elseif ($PSCmdlet.ParameterSetName -eq 'Inspect') {
    $result = & $launcher '--inspect' $Inspect
    if ($LASTEXITCODE -ne 0) { throw "Playtest inspection failed ($LASTEXITCODE)" }
    $result | ConvertFrom-Json
    return
}
if ($PrepareOnly) {
    $result = & $launcher @launchArgs '--prepare-only'
    if ($LASTEXITCODE -ne 0) { throw "Playtest setup failed ($LASTEXITCODE)" }
    $result | ConvertFrom-Json
} else {
    & $launcher @launchArgs
    if ($LASTEXITCODE -ne 0) { throw "Playtest exited with code $LASTEXITCODE" }
}
