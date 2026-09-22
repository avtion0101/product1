param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Destination,
    [ValidateSet('pdf','docx')][string]$Format = 'pdf'
)
$ErrorActionPreference = 'Stop'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($Source, $false, $true)
    if ($Format -eq 'docx') {
        $document.SaveAs2($Destination, 16)
    } else {
        $document.Repaginate()
        $document.ExportAsFixedFormat($Destination, 17)
    }
} finally {
    if ($null -ne $document) { try { $document.Close(0) } catch {} }
    if ($null -ne $word) { try { $word.Quit() } catch {} }
    if ($null -ne $document) { try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) } catch {} }
    if ($null -ne $word) { try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) } catch {} }
}
