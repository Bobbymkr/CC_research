$ErrorActionPreference = "Stop"

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDir = Join-Path $baseDir "generated"
$dotCommand = Get-Command dot -ErrorAction Stop

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$figureNames = @(
    "raasa_control_loop",
    "raasa_multinode_k3s",
    "raasa_validation_progression"
)

foreach ($name in $figureNames) {
    $inputPath = Join-Path $baseDir "$name.dot"
    $svgPath = Join-Path $outputDir "$name.svg"
    $pdfPath = Join-Path $outputDir "$name.pdf"

    & $dotCommand.Source -Tsvg $inputPath -o $svgPath
    & $dotCommand.Source -Tpdf $inputPath -o $pdfPath
}

Write-Host "Rendered DOT figures into: $outputDir"
