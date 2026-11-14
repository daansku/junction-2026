# Shared-server host control (Windows). Runs server, cloudflared quick tunnel and hourly backup as
# detached processes that survive the terminal. Logs and pids in $DATA_DIR\logs.
#
#   powershell -File scripts\host.ps1 start            # server + tunnel + backup
#   powershell -File scripts\host.ps1 restart-server   # pull-free restart of the server only (tunnel URL unchanged)
#   powershell -File scripts\host.ps1 stop
#   powershell -File scripts\host.ps1 status           # pids + current tunnel URL
param([ValidateSet("start", "stop", "restart-server", "restart-tunnel", "status")][string]$cmd = "status")

$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not $env:DATA_DIR) { $env:DATA_DIR = Join-Path $env:USERPROFILE "junction-data" }
$logs = Join-Path $env:DATA_DIR "logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$tokFile = Join-Path $env:USERPROFILE ".junction-admin-token"
if (-not (Test-Path $tokFile)) {
    -join ((48..57) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ }) | Out-File -Encoding ascii -NoNewline $tokFile
}
$env:ADMIN_TOKEN = (Get-Content $tokFile -Raw).Trim()
$env:PYTHONUNBUFFERED = "1"

function Start-Bg($name, $exe, $argList) {
    $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $repo -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "$name.out.log") -RedirectStandardError (Join-Path $logs "$name.err.log") -PassThru
    $p.Id | Out-File -Encoding ascii (Join-Path $logs "$name.pid")
    "$name started (pid $($p.Id))"
}

function Stop-Bg($name) {
    $f = Join-Path $logs "$name.pid"
    if (Test-Path $f) {
        $procId = [int](Get-Content $f)
        try { Stop-Process -Id $procId -Force -ErrorAction Stop; "$name stopped (pid $procId)" } catch { "$name not running" }
        Remove-Item $f
    }
}

function Tunnel-Url {
    $log = Join-Path $logs "tunnel.err.log"
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
        if ($m) { return $m.Matches[0].Value }
    }
    return $null
}

switch ($cmd) {
    "start" {
        Start-Bg "server" $py @("-m", "server", "serve", "--port", "8000")
        Start-Bg "tunnel" "cloudflared" @("tunnel", "--no-autoupdate", "--url", "http://localhost:8000")
        Start-Bg "backup" $py @("scripts\backup.py")
        Start-Sleep -Seconds 8
        "tunnel url: $(Tunnel-Url)  (commit it to coordination/API_URL if it changed)"
    }
    "restart-server" {
        Stop-Bg "server"
        Start-Sleep -Seconds 1
        Start-Bg "server" $py @("-m", "server", "serve", "--port", "8000")
    }
    "restart-tunnel" {
        Stop-Bg "tunnel"
        Remove-Item (Join-Path $logs "tunnel.err.log") -ErrorAction SilentlyContinue
        Start-Bg "tunnel" "cloudflared" @("tunnel", "--no-autoupdate", "--url", "http://localhost:8000")
        $url = $null
        for ($i = 0; $i -lt 30 -and -not $url; $i++) { Start-Sleep -Seconds 1; $url = Tunnel-Url }
        if ($url) {
            $url | Out-File -Encoding ascii -NoNewline (Join-Path $repo "coordination\API_URL")
            "tunnel url: $url  (written to coordination/API_URL; commit and push it)"
        } else { "tunnel did not report a URL; see $logs\tunnel.err.log" }
    }
    "stop" { Stop-Bg "server"; Stop-Bg "tunnel"; Stop-Bg "backup" }
    "status" {
        foreach ($n in "server", "tunnel", "backup") {
            $f = Join-Path $logs "$n.pid"
            $alive = $false
            if (Test-Path $f) { $alive = [bool](Get-Process -Id ([int](Get-Content $f)) -ErrorAction SilentlyContinue) }
            "{0,-7} {1}" -f $n, $(if ($alive) { "running" } else { "down" })
        }
        "tunnel url: $(Tunnel-Url)"
    }
}
