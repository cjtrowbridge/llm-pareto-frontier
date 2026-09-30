# fetch_sources.ps1
#
# Reads models.csv from the repo root and, for every model row,
# creates taxonomy/<lab-slug>/<model-slug>/ and fetches the raw content of
# both source urls:
#   whitepaper.<ext>  - the model's whitepaper / technical source
#   livebench.csv     - the shared LiveBench table behind the source url
#
# The folder slugs are derived from the csv fields exactly as
# scripts/pareto_pipeline.py derives them: Get-Slug mirrors slugify()
# (lowercase, runs of alphanumerics with version dots preserved, single
# '-' separators) and Get-ModelSlug mirrors expected_model_slug() (the
# model slug with a trailing run of budget words removed, then the
# non-empty budget appended). See the Naming conventions section of
# AGENTS.md.
#
# Each distinct url is downloaded only once; repeats copy from a temp
# cache. Existing files are never overwritten, so this is safe to re-run.
# Failures are reported at the end and do not abort the run.
#
# Usage (from the repo root):
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch_sources.ps1

$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$modelsCsv = Join-Path $repoRoot 'models.csv'
$cacheDir = Join-Path $env:TEMP ('llm-pareto-frontier-' + (Get-Random))

New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null

# Maps a url to the temp file holding its content, so repeated urls
# (e.g. one technical report shared by a whole model family) are only
# downloaded once.
$downloadCache = @{}

# Urls already known to fail, so a shared bad url is not retried on
# every row that uses it.
$failedUrls = New-Object System.Collections.Generic.List[string]

function Get-RawUrl {
    # Convert a github or huggingface /blob/ page url into its raw
    # content url. Any other url is returned unchanged.
    param([string] $Url)

    $raw = $Url -replace 'https://github\.com/([^/]+)/([^/]+)/blob/', 'https://raw.githubusercontent.com/$1/$2/'
    $raw = $raw -replace 'https://huggingface\.co/([^/]+)/([^/]+)/blob/', 'https://huggingface.co/$1/$2/resolve/'
    return $raw
}

function Get-SlugTokens {
    # Split a name into slug tokens: lowercase it, keep runs of
    # alphanumerics (a '.' counts toward a run only when it sits between
    # two alphanumerics, so version numbers like 5.1 survive), and treat
    # every other character as a run boundary. Mirrors _slug_tokens() in
    # scripts/pareto_pipeline.py.
    param([string] $Name)

    $s = $Name.ToLowerInvariant()
    $n = $s.Length
    $tokens = New-Object System.Collections.Generic.List[string]
    $cur = New-Object System.Collections.Generic.List[char]
    for ($i = 0; $i -lt $n; $i++) {
        $c = $s[$i]
        $keep = [char]::IsLetterOrDigit($c) -or
            ($c -eq '.' -and $i -gt 0 -and $i -lt ($n - 1) -and
             [char]::IsLetterOrDigit($s[$i - 1]) -and
             [char]::IsLetterOrDigit($s[$i + 1]))
        if ($keep) {
            [void]$cur.Add($c)
        }
        elseif ($cur.Count -gt 0) {
            [void]$tokens.Add((-join $cur.ToArray()))
            $cur.Clear()
        }
    }
    if ($cur.Count -gt 0) {
        [void]$tokens.Add((-join $cur.ToArray()))
    }
    return $tokens.ToArray()
}

function Get-Slug {
    # Derive the canonical folder slug for a lab (or any name): the runs
    # of Get-SlugTokens joined with a single '-'. Mirrors slugify() in
    # scripts/pareto_pipeline.py.
    param([string] $Name)
    return ([string]::Join('-', (@(Get-SlugTokens $Name))))
}

function Get-ModelSlug {
    # Derive the canonical model folder slug: slugify the model title
    # after removing a trailing run of the budget's words (end-anchored,
    # so 'max' in a title without a budget stays), then append
    # '-' + budget for a non-empty budget. Mirrors expected_model_slug()
    # in scripts/pareto_pipeline.py.
    param([string] $Title, [string] $Budget)

    $vocab = @('effort', 'xhigh', 'max', 'high', 'thinking', 'reasoning', 'think')
    $words = @()
    if ($Budget -ne '') {
        foreach ($w in $Budget.ToLowerInvariant().Split('-')) {
            if ($vocab -contains $w) {
                $words += $w
            }
        }
    }
    if ($words.Count -eq 0) {
        return (Get-Slug $Title)
    }

    $tokens = @(Get-SlugTokens $Title)
    $end = $tokens.Count
    while ($end -gt 0 -and $words -contains $tokens[$end - 1]) {
        $end--
    }
    if ($end -eq 0) {
        $base = ''
    }
    else {
        $base = [string]::Join('-', $tokens[0..($end - 1)])
    }
    if ($base -eq '') {
        return $Budget
    }
    return ($base + '-' + $Budget)
}

function Write-Source {
    # Ensure $Dest holds the content of $Url (downloaded once, then cached).
    # An existing $Dest is never overwritten and no fetch is performed for
    # it. Returns $true when $Dest holds content, $false when the fetch
    # failed.
    param([string] $Url, [string] $Dest)

    if (Test-Path -LiteralPath $Dest) {
        return $true
    }

    if ($failedUrls.Contains($Url)) {
        return $false
    }

    if (-not $downloadCache.ContainsKey($Url)) {
        $cacheFile = Join-Path $cacheDir ([guid]::NewGuid().ToString('N'))
        try {
            Invoke-WebRequest -Uri $Url -OutFile $cacheFile -UseBasicParsing -MaximumRedirection 6
        }
        catch {
            $failedUrls.Add($Url)
            Write-Host ('  fetch failed: ' + $Url)
            return $false
        }
        $downloadCache[$Url] = $cacheFile
    }

    Copy-Item -LiteralPath $downloadCache[$Url] -Destination $Dest -Force
    return $true
}

$failedSources = New-Object System.Collections.Generic.List[string]
$rows = Import-Csv -Path $modelsCsv

foreach ($row in $rows) {
    $lab = Get-Slug $row.lab
    $model = Get-ModelSlug -Title $row.model_title -Budget $row.budget
    $taxonomyRoot = Join-Path $repoRoot 'taxonomy'
    $modelDir = Join-Path (Join-Path $taxonomyRoot $lab) $model

    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

    $whitepaperUrl = Get-RawUrl $row.whitepaper
    if ($whitepaperUrl -match '\.pdf(\?|$)') {
        $whitepaperExt = 'pdf'
    }
    else {
        $whitepaperExt = 'html'
    }
    $whitepaperPath = Join-Path $modelDir ('whitepaper.' + $whitepaperExt)

    if (-not (Write-Source -Url $whitepaperUrl -Dest $whitepaperPath)) {
        $failedSources.Add(($row.lab + ' / ' + $row.model_title + ' / ' + $row.whitepaper))
    }

    $livebenchPath = Join-Path $modelDir 'livebench.csv'
    if (-not (Write-Source -Url (Get-RawUrl $row.livebench_source) -Dest $livebenchPath)) {
        $failedSources.Add(($row.lab + ' / ' + $row.model_title + ' / ' + $row.livebench_source))
    }

    $relative = $modelDir.Substring($repoRoot.Length).TrimStart('\')
    Write-Host ('built ' + $relative)
}

Remove-Item -LiteralPath $cacheDir -Recurse -Force -ErrorAction SilentlyContinue

if ($failedSources.Count -gt 0) {
    Write-Host ''
    Write-Host ('could not fetch ' + $failedSources.Count + ' source(s):')
    foreach ($failed in $failedSources) {
        Write-Host ('  ' + $failed)
    }
    exit 1
}

Write-Host ''
Write-Host 'all sources fetched'