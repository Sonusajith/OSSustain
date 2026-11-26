# Dot-source this script in the terminal that will start Spring Boot.
$ossustainEnvPath = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
if (-not (Test-Path -LiteralPath $ossustainEnvPath -PathType Leaf)) {
    throw "Private .env is missing. Copy .env.example to .env and fill in its required values."
}

foreach ($ossustainLine in Get-Content -LiteralPath $ossustainEnvPath) {
    $ossustainEntry = $ossustainLine.Trim()
    if (-not $ossustainEntry -or $ossustainEntry.StartsWith("#")) { continue }
    if ($ossustainEntry.StartsWith("export ")) { $ossustainEntry = $ossustainEntry.Substring(7).TrimStart() }
    if ($ossustainEntry -notmatch '^([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') { continue }

    $ossustainName = $Matches[1]
    $ossustainValue = $Matches[2].Trim()
    if ($ossustainValue.Length -ge 2 -and
        (($ossustainValue.StartsWith('"') -and $ossustainValue.EndsWith('"')) -or
         ($ossustainValue.StartsWith("'") -and $ossustainValue.EndsWith("'")))) {
        $ossustainValue = $ossustainValue.Substring(1, $ossustainValue.Length - 2)
    }
    [Environment]::SetEnvironmentVariable($ossustainName, $ossustainValue, "Process")
}
