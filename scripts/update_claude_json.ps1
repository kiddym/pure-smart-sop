# Update or create user's .claude.json to set hasCompletedOnboarding = true
$home = if ($env:USERPROFILE) { $env:USERPROFILE } elseif ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
$path = Join-Path $home '.claude.json'
$orig = $null
if (Test-Path $path) { $orig = Get-Content -Raw -Path $path }
$valid = $false
$parsed = $null
if ($orig) {
  try {
    $parsed = $orig | ConvertFrom-Json -ErrorAction Stop
    $valid = $true
  } catch {
    $valid = $false
  }
}
if (-not $valid -or -not $parsed) {
  $newObj = @{ installMethod='unknown'; autoUpdates = $true; hasCompletedOnboarding = $true }
} else {
  $parsed | Add-Member -NotePropertyName 'hasCompletedOnboarding' -NotePropertyValue $true -Force
  $newObj = $parsed
}
$json = $newObj | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($path, $json, [System.Text.Encoding]::UTF8)
Write-Output "OS: $([System.Environment]::OSVersion.Platform)"
Write-Output "PATH: $path"
Write-Output "---ORIGINAL---"
if ($orig) { Write-Output $orig } else { Write-Output "<MISSING>" }
Write-Output "---NEW---"
Write-Output $json
