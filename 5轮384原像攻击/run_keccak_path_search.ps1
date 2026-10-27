param(
    [string]$Solver = "",
    [string]$Cnf = "",
    [string]$Weights = "",
    [string]$OutputDir = "keccak_path_results",
    [string]$TransitionLimits = "25,20,20",
    [int]$TotalWeightLimit = 65,
    [int]$Count = 10,
    [int]$StartRound = 0,
    [switch]$GenerateDdtCnf
)

$ErrorActionPreference = "Stop"
$codeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$limitTag = $TransitionLimits -replace ',', '_'
if ([string]::IsNullOrWhiteSpace($Cnf)) {
    if ($StartRound -ge 0) { $Cnf = "keccak_internal_diff_sat_r$StartRound`_ddt_w$limitTag.cnf" }
    else { $Cnf = "keccak_internal_diff_sat_anyround_ddt_w$limitTag.cnf" }
}
if ([string]::IsNullOrWhiteSpace($Weights)) {
    if ($StartRound -ge 0) { $Weights = "keccak_internal_diff_sat_r$StartRound`_ddt_w$limitTag.weights.json" }
    else { $Weights = "keccak_internal_diff_sat_anyround_ddt_w$limitTag.weights.json" }
}
$cnfPath = Join-Path $codeDir $Cnf
$weightsPath = Join-Path $codeDir $Weights
$outputPath = Join-Path $codeDir $OutputDir

if ([string]::IsNullOrWhiteSpace($Solver)) {
    $candidates = @("cryptominisat5", "kissat", "cadical", "minisat")
    foreach ($candidate in $candidates) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            $Solver = (Get-Command $candidate).Source
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($Solver)) {
    throw "No SAT solver found. Use -Solver C:\path\to\cryptominisat5.exe"
}

$python = "C:\Users\Lenovo\.conda\envs\dpa37\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
$needsDdtBuild = $GenerateDdtCnf -or
    -not (Test-Path -LiteralPath $cnfPath) -or
    -not (Test-Path -LiteralPath $weightsPath)
if (-not $needsDdtBuild) {
    try {
        $metadata = Get-Content -LiteralPath $weightsPath -Raw | ConvertFrom-Json
        if ($metadata.lane_indexing -ne "x+5*y" -or
            $metadata.period_bits -ne 32 -or
            $metadata.linear_z_modulus -ne 32 -or
            $metadata.iota_encoding -ne "rc_low32_xor_high32" -or
            (@($metadata.cp_kernel_states) -join ",") -ne "c1,c2" -or
            $metadata.weight_limit_scope -ne "per_transition_and_total" -or
            ((@($metadata.transition_weight_limits) -join ",") -ne $TransitionLimits) -or
            $metadata.total_weight_limit -ne $TotalWeightLimit -or
            $metadata.iota_rc_start -ne 1 -or
            $metadata.iota_start_round -ne $(if ($StartRound -ge 0) { $StartRound } else { $null })) {
            $needsDdtBuild = $true
        }
    } catch { $needsDdtBuild = $true }
}
if ($needsDdtBuild) {
    $generatorArgs = @((Join-Path $codeDir "keccak_ddt_path_sat.py"),
        "--out", $cnfPath, "--weights", $weightsPath, "--limit", "30",
        "--transition-limits", $TransitionLimits, "--total-weight-limit", "$TotalWeightLimit")
    if ($StartRound -ge 0) { $generatorArgs += @("--start-round", "$StartRound") }
    & $python @generatorArgs
    if ($LASTEXITCODE -ne 0) { throw "DDT CNF generation failed with exit code $LASTEXITCODE" }
}
if (-not (Test-Path -LiteralPath $cnfPath)) { throw "CNF not found: $cnfPath" }
if (-not (Test-Path -LiteralPath $weightsPath)) { throw "Weight metadata not found: $weightsPath" }
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
Write-Host "solver: $Solver"
Write-Host "cnf: $cnfPath"
Write-Host "running SAT search..."

& $python (Join-Path $codeDir "enumerate_keccak_paths.py") `
    --solver $Solver --cnf $cnfPath --weights $weightsPath `
    --outdir $outputPath --count $Count --max-total-weight $TotalWeightLimit
if ($LASTEXITCODE -ne 0) {
    throw "Path enumeration failed with exit code $LASTEXITCODE"
}
Write-Host "output: $outputPath"
