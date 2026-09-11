param([ValidateSet(1,2,3)][int]$Nodes = 1, [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
Push-Location $projectDir
try {
    if (-not (Test-Path -LiteralPath '.env')) {
        $configText = [IO.File]::ReadAllText((Join-Path $projectDir '.env.example'))
        foreach ($key in @('POSTGRES_PASSWORD','RABBITMQ_PASSWORD','GRAFANA_PASSWORD')) {
            $bytes = New-Object byte[] 24
            $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
            try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
            $secret = ([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()
            $configText = $configText.Replace("$key=", "$key=$secret")
        }
        [IO.File]::WriteAllText((Join-Path $projectDir '.env'), $configText, [Text.UTF8Encoding]::new($false))
    }
    if ($PrepareOnly) { Write-Output 'Configuración local preparada.'; return }
    $composeArgs = @('compose')
    if ($Nodes -eq 2) { $composeArgs += @('--profile','two') }
    if ($Nodes -eq 3) { $composeArgs += @('--profile','three') }
    if ($Nodes -lt 3) {
        docker compose --profile three stop node-c
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo detener el nodo C.' }
    }
    if ($Nodes -eq 1) {
        docker compose --profile three stop node-b
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo detener el nodo B.' }
    }
    & docker @composeArgs up --build -d --wait --wait-timeout 180
    if ($LASTEXITCODE -ne 0) { throw 'El arranque no superó todas las comprobaciones de salud.' }
    Write-Output 'NodoFlow: http://localhost:14200'
} finally { Pop-Location }
