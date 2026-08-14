param(
    [string]$OutputRoot = (Join-Path $PSScriptRoot "..\assets\game\buildings-source")
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$resolvedProject = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputRoot)
if (-not $resolvedOutput.StartsWith($resolvedProject, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output directory must stay inside the project: $resolvedProject"
}

$api = "https://clashofclans.fandom.com/api.php"
$headers = @{ "User-Agent" = "CoCVillageEditorAssetDownloader/1.0" }
$categories = [ordered]@{
    army = "Army Buildings/Home Village"
    defensive = "Defensive Buildings/Home Village"
    resource = "Resource Buildings/Home Village"
    other = "Other Buildings/Home Village"
}

function Get-WikiParse([string]$page, [string]$props = "images|wikitext") {
    $url = "${api}?action=parse&format=json&formatversion=2&prop=$([uri]::EscapeDataString($props))&page=$([uri]::EscapeDataString($page))"
    return (Invoke-RestMethod -Uri $url -Headers $headers).parse
}

function ConvertTo-Slug([string]$value) {
    $slug = $value.ToLowerInvariant() -replace "/home village", "" -replace "[^a-z0-9]+", "-"
    return $slug.Trim("-")
}

function Get-Stem([string]$fileName) {
    $base = [System.IO.Path]::GetFileNameWithoutExtension($fileName) -replace " ", "_"
    $base = $base -replace "(?i)(?:[_-]?level)?\d+(?:[-_]?[a-z0-9]+)?$", ""
    return $base.TrimEnd("_", "-")
}

function Get-TitleStem([string]$page) {
    $name = ($page -split "/")[-1]
    $name = $name -replace "\s*\([^)]*\)\s*$", ""
    $name = $name -replace "['.]", ""
    return ($name -replace "[^A-Za-z0-9-]+", "_").Trim("_")
}

function Get-Tiles([string]$page, [string]$category) {
    $parsed = Get-WikiParse $page "wikitext"
    $matches = [regex]::Matches($parsed.wikitext, "(?is)\[\[File:([^|\]]+).*?\|link=([^|\]]+)")
    foreach ($match in $matches) {
        $file = $match.Groups[1].Value.Trim()
        $link = $match.Groups[2].Value.Trim()
        if ($link -and $file -and $link -notmatch "^(Category|File):") {
            [pscustomobject]@{ Category = $category; Page = $link; SeedFile = $file }
        }
    }
}

function Test-AssetName([string]$fileName, [string[]]$stems, [string]$seedFile) {
    $extension = [System.IO.Path]::GetExtension($fileName)
    if ($extension -notmatch "(?i)^\.(png|webp|jpg|jpeg|gif)$") { return $false }
    if ($fileName -match "(?i)(info|concept|comparison|chiefjourney|beta|ui|icon|button|logo|loading|thumbnail|upgrade_chart|scenery)") { return $false }

    $normalized = ($fileName -replace " ", "_")
    foreach ($stem in $stems) {
        if (-not $stem) { continue }
        $escaped = [regex]::Escape($stem)
        if ($normalized -match "(?i)^$escaped(?:[_-]?(?:level)?)?\d" -or
            $normalized -match "(?i)^$escaped.*(?:active|ruin|broken|empty)" -or
            $normalized -eq ($seedFile -replace " ", "_")) {
            return $true
        }
    }
    return $false
}

function Get-ImageInfo([string[]]$files) {
    $results = @()
    for ($offset = 0; $offset -lt $files.Count; $offset += 25) {
        $end = [Math]::Min($offset + 24, $files.Count - 1)
        $titles = (($files[$offset..$end] | ForEach-Object { "File:$_" }) -join "|")
        $url = "${api}?action=query&format=json&formatversion=2&prop=imageinfo&iiprop=url%7Csize&titles=$([uri]::EscapeDataString($titles))"
        $query = Invoke-RestMethod -Uri $url -Headers $headers
        foreach ($page in $query.query.pages) {
            if ($page.imageinfo -and -not $page.missing) {
                $info = $page.imageinfo[0]
                $results += [pscustomobject]@{
                    File = ($page.title -replace "^File:", "")
                    Url = $info.url
                    Bytes = [int64]$info.size
                    Width = $info.width
                    Height = $info.height
                }
            }
        }
    }
    return $results
}

function Test-OriginalContainer([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $signature = New-Object byte[] 12
        $read = $stream.Read($signature, 0, $signature.Length)
        if ($read -lt 4) { return $false }
        $extension = [System.IO.Path]::GetExtension($path).ToLowerInvariant()
        switch ($extension) {
            ".png"  { return $signature[0] -eq 0x89 -and $signature[1] -eq 0x50 -and $signature[2] -eq 0x4E -and $signature[3] -eq 0x47 }
            ".gif"  { return $signature[0] -eq 0x47 -and $signature[1] -eq 0x49 -and $signature[2] -eq 0x46 -and $signature[3] -eq 0x38 }
            ".jpg"  { return $signature[0] -eq 0xFF -and $signature[1] -eq 0xD8 }
            ".jpeg" { return $signature[0] -eq 0xFF -and $signature[1] -eq 0xD8 }
            ".webp" { return $signature[0] -eq 0x52 -and $signature[1] -eq 0x49 -and $signature[2] -eq 0x46 -and $signature[3] -eq 0x46 -and $signature[8] -eq 0x57 -and $signature[9] -eq 0x45 -and $signature[10] -eq 0x42 -and $signature[11] -eq 0x50 }
            default { return $true }
        }
    } finally {
        $stream.Dispose()
    }
}

New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null

$entries = @()
foreach ($category in $categories.GetEnumerator()) {
    $entries += Get-Tiles $category.Value $category.Key
}

# Decorations and obstacles are collections of cosmetic objects rather than levelled buildings.
$entries = $entries | Where-Object { $_.Page -notin @("Decorations/Home Village", "Obstacles/Home Village") }

# The overview points to a trap collection; expand it to every individual Home Village trap.
$trapOverview = $entries | Where-Object { $_.Page -eq "Traps/Home Village" } | Select-Object -First 1
if ($trapOverview) {
    $entries = $entries | Where-Object { $_.Page -ne "Traps/Home Village" }
    $entries += Get-Tiles "Traps/Home Village" "traps"
}

$entries = $entries | Sort-Object Page -Unique
$manifest = @()
$buildingIndex = 0

foreach ($entry in $entries) {
    $buildingIndex++
    Write-Output "[$buildingIndex/$($entries.Count)] Inspecting $($entry.Page)"
    try {
        $parsed = Get-WikiParse $entry.Page "images"
    } catch {
        Write-Warning "Could not inspect $($entry.Page): $($_.Exception.Message)"
        continue
    }

    $seedStem = Get-Stem $entry.SeedFile
    $titleStem = Get-TitleStem $entry.Page
    $stems = @($seedStem, $titleStem) | Where-Object { $_ } | Select-Object -Unique
    $assetFiles = @($parsed.images | Where-Object { Test-AssetName $_ $stems $entry.SeedFile } | Select-Object -Unique)
    if ($assetFiles.Count -eq 0 -and $entry.SeedFile) {
        $assetFiles = @($entry.SeedFile)
    }

    $imageInfo = @(Get-ImageInfo $assetFiles)
    if ($imageInfo.Count -eq 0) {
        Write-Warning "No downloadable building assets found for $($entry.Page)"
        continue
    }

    $categoryDir = Join-Path $resolvedOutput $entry.Category
    $buildingDir = Join-Path $categoryDir (ConvertTo-Slug $entry.Page)
    New-Item -ItemType Directory -Path $buildingDir -Force | Out-Null

    foreach ($asset in $imageInfo) {
        $safeName = $asset.File -replace '[<>:"/\\|?*]', "_"
        $destination = Join-Path $buildingDir $safeName
        if (-not (Test-OriginalContainer $destination)) {
            $originalUrl = if ($asset.Url.Contains("?")) { "$($asset.Url)&format=original" } else { "$($asset.Url)?format=original" }
            Invoke-WebRequest -Uri $originalUrl -Headers $headers -OutFile $destination
            if (-not (Test-OriginalContainer $destination)) {
                throw "Original-format verification failed for $($asset.File)"
            }
        }
        $manifest += [pscustomobject]@{
            category = $entry.Category
            page = $entry.Page
            file = $asset.File
            path = $destination.Substring($resolvedProject.Length + 1).Replace("\", "/")
            source = $asset.Url
            bytes = $asset.Bytes
            width = $asset.Width
            height = $asset.Height
        }
    }
}

$manifestPath = Join-Path $resolvedOutput "manifest.json"
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$totalBytes = ($manifest | Measure-Object -Property bytes -Sum).Sum
$downloadedFiles = Get-ChildItem -LiteralPath $resolvedOutput -File -Recurse | Where-Object { $_.Name -ne "manifest.json" }
$downloadedBytes = ($downloadedFiles | Measure-Object -Property Length -Sum).Sum
Write-Output "COMPLETE"
Write-Output "Buildings/pages: $($entries.Count)"
Write-Output "Manifest assets: $($manifest.Count)"
Write-Output "Downloaded files: $($downloadedFiles.Count)"
Write-Output "Source bytes: $totalBytes"
Write-Output "Downloaded bytes: $downloadedBytes"
Write-Output "Output: $resolvedOutput"
