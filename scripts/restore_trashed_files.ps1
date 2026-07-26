# Restores files that were soft-deleted (renamed to .trashed-<timestamp>-<name>)
# by a file manager's trash feature, but only where no live copy already
# exists at the real filename - so it won't clobber newer work.
#
# Run from the mathplatform\ project root, e.g.:
#   cd C:\Users\DarkSeid\Desktop\mathplatform
#   .\scripts\restore_trashed_files.ps1

Get-ChildItem -Recurse -Filter ".trashed-*" | ForEach-Object {
    $orig = $_.Name -replace '^\.trashed-\d+-', ''
    $target = Join-Path $_.DirectoryName $orig
    if (Test-Path $target) {
        Write-Host "SKIP (live copy already exists): $target"
    } else {
        Rename-Item $_.FullName $orig
        Write-Host "RESTORED: $target"
    }
}
