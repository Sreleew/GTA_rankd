#requires -Version 5.1
$ErrorActionPreference = 'Stop'

try {
    $targets = @(
        $PSCommandPath,
        (Join-Path $PSScriptRoot 'install.ps1'),
        (Join-Path $PSScriptRoot 'update_from_archive.ps1')
    )
    foreach ($target in $targets) {
        $resolved = Resolve-Path -LiteralPath $target -ErrorAction Stop
        $tokens = $null
        $parseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $resolved.ProviderPath,
            [ref]$tokens,
            [ref]$parseErrors
        ) | Out-Null
        if ($parseErrors -and $parseErrors.Count -gt 0) {
            Write-Host ("Erreur de syntaxe dans {0} :" -f $target) -ForegroundColor Red
            foreach ($parseError in $parseErrors) {
                Write-Host ('Ligne {0}, colonne {1} : {2}' -f $parseError.Extent.StartLineNumber, $parseError.Extent.StartColumnNumber, $parseError.Message) -ForegroundColor Red
            }
            exit 1
        }
    }
    Write-Host 'Verification de syntaxe PowerShell : OK' -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ('Impossible de verifier les scripts PowerShell : {0}' -f $_.Exception.Message) -ForegroundColor Red
    exit 2
}
