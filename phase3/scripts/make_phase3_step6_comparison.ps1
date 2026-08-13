$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$items = @(
    @{ Path = 'results\phase3_step6\libero_reference\libero_agentview.png'; Label = 'LIBERO external' },
    @{ Path = 'results\phase3_step6\scene_gate_state00_dynamic\isaac_external.png'; Label = 'Isaac external' },
    @{ Path = 'results\phase3_step6\libero_reference\libero_robot0_eye_in_hand.png'; Label = 'LIBERO wrist' },
    @{ Path = 'results\phase3_step6\scene_gate_state00_dynamic\isaac_wrist.png'; Label = 'Isaac wrist' }
)
$cell = 360
$labelHeight = 42
$canvas = New-Object System.Drawing.Bitmap ($cell * 2), (($cell + $labelHeight) * 2)
$graphics = [System.Drawing.Graphics]::FromImage($canvas)
$graphics.Clear([System.Drawing.Color]::White)
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$font = New-Object System.Drawing.Font 'Arial', 18, ([System.Drawing.FontStyle]::Bold)
$brush = [System.Drawing.Brushes]::Black
try {
    for ($index = 0; $index -lt $items.Count; $index++) {
        $column = $index % 2
        $row = [math]::Floor($index / 2)
        $x = $column * $cell
        $y = $row * ($cell + $labelHeight)
        $graphics.DrawString($items[$index].Label, $font, $brush, $x + 8, $y + 8)
        $image = [System.Drawing.Image]::FromFile((Join-Path $project $items[$index].Path))
        try { $graphics.DrawImage($image, $x, $y + $labelHeight, $cell, $cell) }
        finally { $image.Dispose() }
    }
    $output = Join-Path $project 'assets\images\phase3_step6_libero_vs_isaac.png'
    $canvas.Save($output, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $font.Dispose()
    $graphics.Dispose()
    $canvas.Dispose()
}
