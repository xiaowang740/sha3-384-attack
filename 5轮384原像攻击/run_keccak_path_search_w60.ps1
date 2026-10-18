param(
    [string]$Solver = "D:\cryptominisat5.exe",
    [int]$Count = 10,
    [string]$OutputDir = "keccak_path_results_w60"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainScript = Join-Path $scriptDir "run_keccak_path_search.ps1"

& powershell.exe -ExecutionPolicy Bypass -File $mainScript `
    -Solver $Solver `
    -StartRound 0 `
    -MaxTransitionWeight 60 `
    -Count $Count `
    -OutputDir $OutputDir `
    -GenerateDdtCnf

if ($LASTEXITCODE -ne 0) {
    throw "Weight-60 path search failed with exit code $LASTEXITCODE"
}
