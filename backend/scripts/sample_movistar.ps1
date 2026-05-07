$ErrorActionPreference = "Stop"

$dataDir = "C:\Users\enrique.garrido\Downloads\data"
$outDir  = "C:\Users\enrique.garrido\Downloads\data\sample"
$N = 500

$archivos = [ordered]@{
    "DOCUMENTOS_SCRECSA_20260305.txt"  = 5
    "CONTACTO_SCRECSA_20260305.txt"    = 1
    "ABONADOS_SCRECSA_20260305.txt"    = 1
    "GESTIONES_SCRECSA_20260305.txt"   = 0
    "MOVIMIENTOS_SCRECSA_20260305.txt" = 5
}

$principal = "DOCUMENTOS_SCRECSA_20260305.txt"

if (-not (Test-Path -Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

$ids = New-Object 'System.Collections.Generic.HashSet[string]'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$rutaPrincipal = Join-Path $dataDir $principal
$colPrincipal  = $archivos[$principal]

Write-Host ("Leyendo {0} NUM_IDENT desde {1} ..." -f $N, $principal) -ForegroundColor Cyan

$reader = New-Object System.IO.StreamReader($rutaPrincipal, [System.Text.Encoding]::UTF8)
try {
    $null = $reader.ReadLine()
    while (-not $reader.EndOfStream -and $ids.Count -lt $N) {
        $linea = $reader.ReadLine()
        if ([string]::IsNullOrWhiteSpace($linea)) { continue }
        $partes = $linea.Split(';')
        if ($partes.Length -le $colPrincipal) { continue }
        $valor = $partes[$colPrincipal].Trim()
        if ($valor.Length -gt 0) {
            [void]$ids.Add($valor)
        }
    }
}
finally {
    $reader.Close()
}

Write-Host ("Capturados {0} NUM_IDENT unicos" -f $ids.Count) -ForegroundColor Green

foreach ($entry in $archivos.GetEnumerator()) {
    $nombre = $entry.Key
    $colIdx = $entry.Value

    $rutaIn   = Join-Path $dataDir $nombre
    $nombreOut = [System.IO.Path]::GetFileNameWithoutExtension($nombre) + "_sample.txt"
    $rutaOut  = Join-Path $outDir $nombreOut

    if (-not (Test-Path -Path $rutaIn)) {
        Write-Host ("Saltado (no existe): {0}" -f $nombre) -ForegroundColor Yellow
        continue
    }

    $reader = New-Object System.IO.StreamReader($rutaIn, [System.Text.Encoding]::UTF8)
    $writer = New-Object System.IO.StreamWriter($rutaOut, $false, $utf8NoBom)

    $coincidencias = 0
    $leidas = 0
    try {
        $header = $reader.ReadLine()
        if ($null -ne $header) {
            $writer.WriteLine($header)
        }
        while (-not $reader.EndOfStream) {
            $linea = $reader.ReadLine()
            if ($null -eq $linea) { continue }
            $leidas++
            $partes = $linea.Split(';')
            if ($partes.Length -le $colIdx) { continue }
            $valor = $partes[$colIdx].Trim()
            if ($ids.Contains($valor)) {
                $writer.WriteLine($linea)
                $coincidencias++
            }
        }
    }
    finally {
        $writer.Flush()
        $writer.Close()
        $reader.Close()
    }

    $tamanoMB = [math]::Round((Get-Item $rutaOut).Length / 1MB, 2)
    Write-Host ("{0}: {1} matches / {2} leidas / {3} MB" -f $nombre, $coincidencias, $leidas, $tamanoMB)
}

Write-Host ("Listo. Samples en: {0}" -f $outDir) -ForegroundColor Cyan
