# -----------------------------------------------------------------
#  MathPlatform - shared "hacker" console theme + animations
#
#  Dot-sourced by start.ps1 / stop.ps1 / status.ps1 / restart.ps1 so
#  all four launcher scripts look and feel like one consistent tool
#  instead of four differently-styled ones.
#
#  Set $env:MATHPLATFORM_NO_ANIMATION=1 before running to skip the
#  matrix intro and typewriter effects (e.g. when scripted/CI) while
#  keeping the colours and layout - everything still runs, just instant.
# -----------------------------------------------------------------

$Global:HackerAnimationsOn = ($env:MATHPLATFORM_NO_ANIMATION -ne '1')

function Initialize-HackerConsole {
    param([string]$Title = 'MathPlatform')
    try {
        $Host.UI.RawUI.BackgroundColor = 'Black'
        $Host.UI.RawUI.ForegroundColor = 'Green'
        $Host.UI.RawUI.WindowTitle = $Title
        Clear-Host
    } catch {
        # Some hosts (ISE, redirected output) don't allow re-colouring -
        # degrade gracefully rather than crashing the whole launcher over it.
    }
}

# A brief "matrix rain" curtain before the real banner - the classic
# hacker-terminal flourish. Skips instantly if animations are off or the
# console is too small / non-interactive to draw into safely.
function Show-MatrixIntro {
    param([int]$DurationMs = 1100)
    if (-not $Global:HackerAnimationsOn) { return }
    try {
        $width = [Math]::Max(40, [Math]::Min(100, $Host.UI.RawUI.WindowSize.Width))
    } catch { return }
    $glyphs = @('0','1','7','9','$','#','%','&','*','/','\','?','X','Z','Q','+','=')
    $sw = [Diagnostics.Stopwatch]::StartNew()
    try {
        while ($sw.ElapsedMilliseconds -lt $DurationMs) {
            $line = New-Object System.Text.StringBuilder
            for ($i = 0; $i -lt $width; $i++) {
                if ((Get-Random -Minimum 0 -Maximum 7) -eq 0) {
                    [void]$line.Append(($glyphs | Get-Random))
                } else {
                    [void]$line.Append(' ')
                }
            }
            Write-Host $line.ToString() -ForegroundColor DarkGreen
            Start-Sleep -Milliseconds 35
        }
    } catch { }
    Clear-Host
}

# Prints the boxed "MATHPLATFORM" banner. $Subtitle is the per-script
# tagline (e.g. "BOOTING SYSTEM", "SHUTTING DOWN", "SYSTEM STATUS").
function Write-HackerBanner {
    param(
        [string]$Subtitle = '',
        [int]$Width = 62
    )
    $bar = '=' * $Width
    Write-Host $bar -ForegroundColor DarkGreen
    Write-Host ('||' + (' ' * ($Width - 4)) + '||') -ForegroundColor DarkGreen
    $title = 'M A T H P L A T F O R M'
    $pad = [Math]::Max(0, [Math]::Floor(($Width - 4 - $title.Length) / 2))
    Write-Host ('||' + (' ' * $pad) + $title + (' ' * ($Width - 4 - $pad - $title.Length)) + '||') -ForegroundColor Green
    if ($Subtitle) {
        $subPad = [Math]::Max(0, [Math]::Floor(($Width - 4 - $Subtitle.Length) / 2))
        Write-Host ('||' + (' ' * $subPad) + $Subtitle + (' ' * ($Width - 4 - $subPad - $Subtitle.Length)) + '||') -ForegroundColor Cyan
    }
    Write-Host ('||' + (' ' * ($Width - 4)) + '||') -ForegroundColor DarkGreen
    Write-Host $bar -ForegroundColor DarkGreen
    Write-Host ''
}

# Types text out character-by-character for a terminal-hacking feel.
# Used sparingly (banners / final messages) so it never blocks anything
# that's actually waiting on real work.
function Write-Typewriter {
    param(
        [string]$Text,
        [string]$Color = 'Green',
        [int]$DelayMs = 6
    )
    if (-not $Global:HackerAnimationsOn) {
        Write-Host $Text -ForegroundColor $Color
        return
    }
    foreach ($ch in $Text.ToCharArray()) {
        Write-Host -NoNewline $ch -ForegroundColor $Color
        Start-Sleep -Milliseconds $DelayMs
    }
    Write-Host ''
}

function Write-Step($msg) { Write-Host "[>>] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

# Runs $Action repeatedly (polling for something to become true) while
# animating a spinner + elapsed-time counter on a single line, instead
# of the console sitting silently for up to $TimeoutSec. Returns whatever
# $Action last returned.
function Wait-WithSpinner {
    param(
        [Parameter(Mandatory)] [scriptblock]$Action,
        [string]$Label = 'Working',
        [int]$TimeoutSec = 45,
        [int]$PollMs = 1000
    )
    $spinChars = @('|', '/', '-', '\')
    $elapsed = 0
    $frame = 0
    while ($true) {
        $result = & $Action
        if ($result) {
            Write-Host ("`r" + (' ' * 70) + "`r") -NoNewline
            return $result
        }
        if ($elapsed -ge $TimeoutSec) {
            Write-Host ("`r" + (' ' * 70) + "`r") -NoNewline
            return $false
        }
        if ($Global:HackerAnimationsOn) {
            $spin = $spinChars[$frame % $spinChars.Length]
            Write-Host ("`r[ $spin ] $Label... ${elapsed}s") -NoNewline -ForegroundColor Yellow
        }
        Start-Sleep -Milliseconds $PollMs
        $elapsed++
        $frame++
    }
}

# A short "boot sequence" of already-known-good checkmarks, purely for
# pacing/feel right after the banner - e.g. "[ OK ] Console online",
# "[ OK ] Scripts loaded". Cheap, instant unless animations are on.
function Show-BootSequence {
    param([string[]]$Lines)
    foreach ($line in $Lines) {
        Write-Ok $line
        if ($Global:HackerAnimationsOn) { Start-Sleep -Milliseconds 120 }
    }
    Write-Host ''
}
