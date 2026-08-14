param(
    [string]$OutputRoot = (Join-Path $PSScriptRoot "..\assets\game\scenery")
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$outputPath = [System.IO.Path]::GetFullPath($OutputRoot)
if (-not $outputPath.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output directory must stay inside the project: $projectRoot"
}

$api = "https://clashofclans.fandom.com/api.php"
$sourcePage = "Scenery"
$homeVillageGallerySection = 3
$headers = @{ "User-Agent" = "CoCVillageEditorAssetDownloader/1.0" }
$catalogPath = Join-Path $projectRoot "assets\js\scenery-catalog.js"

function ConvertTo-Slug([string]$value) {
    $slug = $value.ToLowerInvariant() -replace "[^a-z0-9]+", "-"
    return $slug.Trim("-")
}

function Get-SceneryId([string]$fileName) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($fileName) -replace "_", " "
    $name = $name -replace "^Map ", ""
    $name = $name -replace "(?i) Scenery$", ""
    $name = $name -replace "(?i) (Full|Closeup)$", ""
    $name = $name -replace "FireAndIce", "Fire And Ice"
    return ConvertTo-Slug $name
}

function ConvertTo-DisplayName([string]$id) {
    return (($id -split "-" | ForEach-Object {
        if ($_ -match "^\d+(st|nd|rd|th)$") { $_ }
        elseif ($_ -eq "a") { "A" }
        else { (Get-Culture).TextInfo.ToTitleCase($_) }
    }) -join " ")
}

function Test-OriginalContainer([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $signature = New-Object byte[] 12
        $read = $stream.Read($signature, 0, $signature.Length)
        if ($read -lt 4) { return $false }
        switch ([System.IO.Path]::GetExtension($path).ToLowerInvariant()) {
            ".png"  { return $signature[0] -eq 0x89 -and $signature[1] -eq 0x50 -and $signature[2] -eq 0x4E -and $signature[3] -eq 0x47 }
            ".gif"  { return $signature[0] -eq 0x47 -and $signature[1] -eq 0x49 -and $signature[2] -eq 0x46 -and $signature[3] -eq 0x38 }
            ".jpg"  { return $signature[0] -eq 0xFF -and $signature[1] -eq 0xD8 }
            ".jpeg" { return $signature[0] -eq 0xFF -and $signature[1] -eq 0xD8 }
            ".webp" { return $signature[0] -eq 0x52 -and $signature[1] -eq 0x49 -and $signature[2] -eq 0x46 -and $signature[3] -eq 0x46 -and $signature[8] -eq 0x57 -and $signature[9] -eq 0x45 -and $signature[10] -eq 0x42 -and $signature[11] -eq 0x50 }
            default { return $false }
        }
    } finally {
        $stream.Dispose()
    }
}

function Get-ExistingCatalog {
    $result = @{}
    if (-not (Test-Path -LiteralPath $catalogPath)) { return $result }
    $raw = Get-Content -Raw -LiteralPath $catalogPath
    $json = $raw -replace "^\s*window\.SCENERY_CATALOG\s*=\s*", "" -replace ";\s*$", ""
    foreach ($item in ($json | ConvertFrom-Json)) { $result[$item.id] = $item }
    return $result
}

function Get-ImageInfo([string[]]$files) {
    $result = @()
    for ($offset = 0; $offset -lt $files.Count; $offset += 25) {
        $end = [Math]::Min($offset + 24, $files.Count - 1)
        $titles = (($files[$offset..$end] | ForEach-Object { "File:$_" }) -join "|")
        $url = "${api}?action=query&format=json&formatversion=2&prop=imageinfo&iiprop=url%7Csize%7Cmime&titles=$([uri]::EscapeDataString($titles))"
        $query = Invoke-RestMethod -Uri $url -Headers $headers
        foreach ($page in $query.query.pages) {
            if ($page.imageinfo -and -not $page.missing) {
                $info = $page.imageinfo[0]
                $result += [pscustomobject]@{
                    File = ($page.title -replace "^File:", "")
                    Url = $info.url
                    Bytes = [int64]$info.size
                    Width = [int]$info.width
                    Height = [int]$info.height
                    Mime = $info.mime
                }
            }
        }
    }
    return $result
}

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
$parseUrl = "${api}?action=parse&format=json&formatversion=2&prop=images&page=$sourcePage&section=$homeVillageGallerySection"
$gallery = (Invoke-RestMethod -Uri $parseUrl -Headers $headers).parse
$sourceFiles = @($gallery.images | Where-Object { $_ -match "(?i)\.(jpg|jpeg|png|webp)$" } | Select-Object -Unique)
$imageInfo = @(Get-ImageInfo $sourceFiles)
$oldCatalog = Get-ExistingCatalog
$manifest = @()
$counter = 0

foreach ($asset in ($imageInfo | Sort-Object File)) {
    $counter++
    $id = Get-SceneryId $asset.File
    $sourceBase = [System.IO.Path]::GetFileNameWithoutExtension($asset.File)
    $variant = if ($sourceBase -match "(?i)Closeup$") { "closeup" } elseif ($sourceBase -match "(?i)Full$") { "full" } else { "default" }
    $extension = [System.IO.Path]::GetExtension($asset.File).ToLowerInvariant()
    $suffix = if ($variant -eq "default") { "" } else { "-$variant" }
    $localName = "$id$suffix$extension"
    $destination = Join-Path $outputPath $localName
    Write-Output "[$counter/$($imageInfo.Count)] $($asset.File) -> $localName"

    if (-not (Test-OriginalContainer $destination)) {
        $originalUrl = if ($asset.Url.Contains("?")) { "$($asset.Url)&format=original" } else { "$($asset.Url)?format=original" }
        Invoke-WebRequest -Uri $originalUrl -Headers $headers -OutFile $destination
        if (-not (Test-OriginalContainer $destination)) {
            throw "Original-format verification failed for $($asset.File)"
        }
    }

    $manifest += [pscustomobject]@{
        id = $id
        name = if ($oldCatalog.ContainsKey($id)) { $oldCatalog[$id].name } else { ConvertTo-DisplayName $id }
        variant = $variant
        file = $localName
        sourceFile = $asset.File
        source = $asset.Url
        mime = $asset.Mime
        width = $asset.Width
        height = $asset.Height
        sourceBytes = $asset.Bytes
        downloadedBytes = (Get-Item -LiteralPath $destination).Length
    }
}

$catalog = @()
foreach ($group in ($manifest | Group-Object id | Sort-Object Name)) {
    $preferred = $group.Group | Where-Object variant -eq "closeup" | Select-Object -First 1
    if (-not $preferred) { $preferred = $group.Group | Where-Object variant -eq "default" | Select-Object -First 1 }
    if (-not $preferred) { $preferred = $group.Group | Select-Object -First 1 }
    $old = $oldCatalog[$group.Name]
    $grid = if ($group.Name -eq "skeleton-kingdom") {
        [pscustomobject]@{ top = @(0.498, 0.225); right = @(0.691, 0.422); bottom = @(0.499, 0.625); left = @(0.316, 0.423) }
    } elseif ($old -and $old.grid) { $old.grid } else {
        [pscustomobject]@{ top = @(0.51, 0.10); right = @(0.85, 0.48); bottom = @(0.51, 0.87); left = @(0.19, 0.52) }
    }
    $catalog += [pscustomobject]@{ id = $group.Name; name = $preferred.name; file = $preferred.file; grid = $grid }
}

$manifestPath = Join-Path $outputPath "manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
"window.SCENERY_CATALOG=$($catalog | ConvertTo-Json -Depth 6 -Compress);" | Set-Content -LiteralPath $catalogPath -Encoding UTF8

$downloaded = @(Get-ChildItem -LiteralPath $outputPath -File | Where-Object { $_.Name -notin @("manifest.json", "SOURCE.md", ".gitkeep") })
$totalBytes = ($downloaded | Measure-Object Length -Sum).Sum
Write-Output "COMPLETE"
Write-Output "Sceneries: $($catalog.Count)"
Write-Output "Source images: $($manifest.Count)"
Write-Output "Downloaded files: $($downloaded.Count)"
Write-Output "Downloaded bytes: $totalBytes"
Write-Output "Output: $outputPath"
