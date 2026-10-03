param(
    [string]$SteamRoot = 'D:\steam',
    [ValidateSet('Auto','WebApi','Public')]
    [string]$Source = 'Auto',
    [string]$ApiKey = $env:STEAM_API_KEY,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$userData = Join-Path $SteamRoot 'userdata'
$loginUsers = Join-Path $SteamRoot 'config\loginusers.vdf'

if (-not (Test-Path -LiteralPath $loginUsers)) { throw "Steam loginusers.vdf not found: $loginUsers" }
$loginText = Get-Content -Raw -LiteralPath $loginUsers
$steamId = [regex]::Match($loginText, '"(7656119\d+)"\s*\{\s*"AccountName"[^}]*?"AutoLogin"\s+"1"', [Text.RegularExpressions.RegexOptions]::Singleline).Groups[1].Value
if (-not $steamId) { throw 'Could not determine the auto-login Steam account.' }
$accountId = [int64]$steamId - 76561197960265728
$configDir = Join-Path $userData "$accountId\config"
$localConfig = Join-Path $configDir 'localconfig.vdf'
if (-not (Test-Path -LiteralPath $localConfig)) { throw "Steam local config not found: $localConfig" }

$steam = Get-Process -Name steam -ErrorAction SilentlyContinue
if ($Apply -and $steam) { throw 'Steam is running. Exit Steam completely, then run again with -Apply.' }

$installed = @{}
$libraryFolders = @($SteamRoot)
$libraryVdf = Join-Path $SteamRoot 'steamapps\libraryfolders.vdf'
if (Test-Path -LiteralPath $libraryVdf) {
    $libraryText = Get-Content -Raw -LiteralPath $libraryVdf
    foreach ($m in [regex]::Matches($libraryText, '"path"\s+"([^"]+)"')) {
        $path = $m.Groups[1].Value -replace '\\\\','\\'
        if ($path -and ($libraryFolders -notcontains $path)) { $libraryFolders += $path }
    }
}
foreach ($library in $libraryFolders) {
foreach ($manifest in Get-ChildItem -LiteralPath (Join-Path $library 'steamapps') -Filter 'appmanifest_*.acf' -ErrorAction SilentlyContinue) {
    $text = Get-Content -Raw -LiteralPath $manifest.FullName
    $id = [regex]::Match($text, '"appid"\s+"(\d+)"').Groups[1].Value
    $name = [regex]::Match($text, '"name"\s+"([^"]*)"').Groups[1].Value
    if ($id -and $name) { $installed[$id] = [pscustomobject]@{ appid=$id; name=$name; installed=$true } }
}
}

$steamGames = @()
$steamId64 = $steamId
function Get-WebApiGames([string]$key, [string]$sid) {
    if (-not $key) { throw 'STEAM_API_KEY is not set.' }
    $uri = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=$([uri]::EscapeDataString($key))&steamid=$sid&format=json&include_appinfo=1&include_played_free_games=1"
    $resp = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 30
    if (-not $resp.response.games) { throw 'Web API returned no games (profile may be private or key invalid).' }
    return @($resp.response.games | ForEach-Object {
        [pscustomobject]@{ appid=([string]$_.appid); name=([string]$_.name); playtime_forever=[int]$_.playtime_forever; rtime_last_played=$_.rtime_last_played; installed=$installed.ContainsKey([string]$_.appid) }
    })
}
function Get-PublicGames([string]$sid) {
    $uri = "https://steamcommunity.com/profiles/$sid/games/?xml=1"
    $xml = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 30
    $items = @($xml.profile.games.game)
    if (-not $items) { throw 'Public profile returned no games (profile/game details may be private).' }
    return @($items | ForEach-Object {
        $id = [string]$_.appid
        [pscustomobject]@{ appid=$id; name=([string]$_.name); playtime_forever=[int]$_.hoursPlayed; rtime_last_played=$null; installed=$installed.ContainsKey($id) }
    })
}

$sourceUsed = $null; $sourceError = $null
if ($Source -in @('Auto','WebApi')) {
    try { $steamGames = Get-WebApiGames $ApiKey $steamId64; $sourceUsed = 'WebApi' }
    catch { $sourceError = $_.Exception.Message; if ($Source -eq 'WebApi') { throw } }
}
if (-not $steamGames -and $Source -in @('Auto','Public')) {
    try { $steamGames = Get-PublicGames $steamId64; $sourceUsed = 'Public' }
    catch { if (-not $sourceError) { $sourceError = $_.Exception.Message }; throw "Could not read the full Steam library. WebApi/Public error: $sourceError" }
}
if (-not $steamGames) { throw 'No games were returned by the selected source.' }

$games = @($steamGames | Sort-Object appid -Unique)

# Conservative first pass: categories are additive and only use installed games.
$collections = [ordered]@{}
foreach ($g in $games) {
    $initial = ($g.name.TrimStart() -replace '[^\p{L}\p{Nd}]','')[0].ToString().ToUpperInvariant()
    if (-not $initial) { $initial = '#' }
    $key = "auto-initial-$initial"
    if (-not $collections.Contains($key)) { $collections[$key] = [ordered]@{ id=$key; name="首字母 / $initial"; added=@(); removed=@() } }
    $collections[$key].added += [int64]$g.appid
}

$out = [pscustomobject]@{
    steam_root=$SteamRoot; account_id=$accountId; generated_at=(Get-Date).ToString('o');
    source=$sourceUsed; source_error=$sourceError; owned_games=$games.Count; installed_games=@($games | Where-Object installed).Count; collections=$collections.Values
}
$preview = Join-Path $PSScriptRoot 'steam_categories_preview.json'
$out | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $preview
Write-Output "Preview written: $preview"
Write-Output "Account: $steamId ($accountId); source: $sourceUsed; owned games: $($games.Count); installed: $(@($games | Where-Object installed).Count)"
if ($sourceError) { Write-Output "Fallback note: $sourceError" }
Write-Output "No Steam files were changed."

if ($Apply) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = "$localConfig.$stamp.bak"
    Copy-Item -LiteralPath $localConfig -Destination $backup
    $text = Get-Content -Raw -LiteralPath $localConfig

    function Find-MatchingBrace([string]$s, [int]$open) {
        $depth = 0; $quoted = $false; $esc = $false
        for ($i=$open; $i -lt $s.Length; $i++) {
            $ch = $s[$i]
            if ($quoted) {
                if ($esc) { $esc = $false }
                elseif ($ch -eq '\\') { $esc = $true }
                elseif ($ch -eq '"') { $quoted = $false }
                continue
            }
            if ($ch -eq '"') { $quoted = $true; continue }
            if ($ch -eq '{') { $depth++ }
            elseif ($ch -eq '}') { $depth--; if ($depth -eq 0) { return $i } }
        }
        return -1
    }

    foreach ($g in $games) {
        $needle = '"' + $g.appid + '"'
        $pos = 0; $found = $false
        while (($m = [regex]::Match($text.Substring($pos), '(?m)^\s*"' + [regex]::Escape($g.appid) + '"\s*\{')).Success) {
            $start = $pos + $m.Index
            $open = $pos + $m.Index + $m.Value.LastIndexOf('{')
            $close = Find-MatchingBrace $text $open
            if ($close -lt 0) { break }
            $block = $text.Substring($open + 1, $close - $open - 1)
            if ($block -notmatch '(?m)^\s*"tags"\s*\{') {
                $initial = ($g.name.TrimStart() -replace '[^\p{L}\p{Nd}]','')[0].ToString().ToUpperInvariant()
                if (-not $initial) { $initial = '#' }
                $tagBlock = "`r`n`t`t`t`t`t`t" + '"tags"' + "`r`n`t`t`t`t`t`t{`r`n`t`t`t`t`t`t`t" + '"0"' + "`t`t" + '"自动 / 首字母 / ' + $initial + '"' + "`r`n`t`t`t`t`t`t`t" + '"1"' + "`t`t" + '"自动 / 已安装"' + "`r`n`t`t`t`t`t`t}`r`n"
                $text = $text.Insert($close, $tagBlock)
            }
            $found = $true; break
        }
        if (-not $found) { Write-Warning "App $($g.appid) not found in localconfig.vdf (likely not owned by this account)." }
    }
    Set-Content -LiteralPath $localConfig -Value $text -Encoding UTF8
    Write-Output "Backup: $backup"
    Write-Output "Applied tags to $($games.Count) installed games. Restart Steam to see the categories."
}
