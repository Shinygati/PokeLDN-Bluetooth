<#
Run a Gen 6/7 Local Distributor in azahar_uds with the card you choose (docs/3ds_local_distributor.md).

  .\tools\uds\run_distributor.ps1 -Azahar "C:\Azahar-UDS" -Card "C:\cards\0566 XYORAS - GF Genesect (US) (ENG).wc6full"
  .\tools\uds\run_distributor.ps1 -Azahar "C:\Azahar-UDS" -Card ... -Record   # record instead of transmitting

-Azahar is the folder holding azahar.exe and its portable "user" folder. -Card is optional: without
it the card already in the distributor stays. -Record sends the distributor's packets to a recorder
in captures\ through the UDP bridge INSTEAD of the ESP32: azahar_uds turns its ESP32 backend off
while the bridge is on, so nothing goes over the air in a -Record run.
#>
param(
    [Parameter(Mandatory = $true)][string]$Azahar,
    [string]$Card,
    [string]$UserDir,
    [switch]$Record,
    [int]$BridgePort = 45710
)
$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "py" }

$exe = @("azahar.exe", "azahar-qt.exe") | ForEach-Object { Join-Path $Azahar $_ } | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) { throw "No azahar.exe in $Azahar" }
if (-not $UserDir) {
    $UserDir = Join-Path $Azahar "user"
    if (-not (Test-Path $UserDir)) { $UserDir = Join-Path $env:APPDATA "Azahar" }
}
if (-not (Test-Path $UserDir)) { throw "No Azahar user folder at $UserDir (pass -UserDir)" }

if ($Card) {
    & $python (Join-Path $repo "tools\uds\distributor_card.py") --dir $UserDir --card $Card
    if ($LASTEXITCODE -ne 0) { throw "The card was not installed." }
} else {
    & $python (Join-Path $repo "tools\uds\distributor_card.py") --dir $UserDir --list
}

if ($Record) {
    $capture = Join-Path $repo ("captures\distributor-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".jsonl")
    Start-Process -FilePath $python -WorkingDirectory $repo -ArgumentList @(
        "tools\uds\bridge_relay.py", "--a", $BridgePort, "--b", "0", "--out", "`"$capture`"", "--quiet-beacons")
    $env:AZAHAR_UDS_BRIDGE = "$BridgePort"
    Write-Host "Recording the distributor's packets to $capture"
    Write-Host "Note: azahar_uds does not use the ESP32 while recording; no 3DS will see this session."
} else {
    Remove-Item Env:AZAHAR_UDS_BRIDGE -ErrorAction SilentlyContinue
}

Write-Host "Starting $exe. Open the distributor, hold X+Y to start distributing, then on the 3DS:"
Write-Host "  Mystery Gift -> Receive Gift -> Get via Local Wireless"
Start-Process -FilePath $exe -WorkingDirectory $Azahar
