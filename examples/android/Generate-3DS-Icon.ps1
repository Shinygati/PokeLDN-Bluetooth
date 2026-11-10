param([string]$Destination = (Join-Path $PSScriptRoot 'n3ds_plugin/n3ds-console.png'))
Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap 192,192
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::Transparent)
function Fill-Box($color,$x,$y,$width,$height) {
    $brush = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml($color))
    $graphics.FillRectangle($brush,$x,$y,$width,$height)
    $brush.Dispose()
}
function Dot($color,$x,$y,$diameter) {
    $brush = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml($color))
    $graphics.FillEllipse($brush,$x,$y,$diameter,$diameter)
    $brush.Dispose()
}
# Wide upper 3D screen, hinge, touch screen, circle pad, D-pad and ABXY cluster.
Fill-Box '#90a4ae' 12 12 168 82
Fill-Box '#202830' 16 16 160 74
Fill-Box '#080e14' 35 24 122 59
Fill-Box '#37b6ee' 42 29 108 47
Fill-Box '#b0e9ff' 46 33 100 4
Dot '#11171b' 92 18 5
foreach ($x in 24,164) { foreach ($y in 40,49,58) { Dot '#8797a4' $x $y 3 } }
Fill-Box '#617583' 21 94 150 9
Fill-Box '#b3c1cb' 19 103 154 77
Fill-Box '#344650' 23 107 146 69
Fill-Box '#101921' 59 113 74 55
Fill-Box '#8ed7e9' 64 118 64 45
Dot '#b9c5cd' 29 115 21
Dot '#687c89' 33 119 13
Fill-Box '#101820' 35 143 10 26
Fill-Box '#101820' 27 151 26 10
foreach ($position in @(@(149,127),@(139,137),@(159,137),@(149,147))) {
    Dot '#b4c7d4' $position[0] $position[1] 8
}
Fill-Box '#7c909e' 81 171 29 3
Dot '#69e685' 163 170 3
$bitmap.Save($Destination,[System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
