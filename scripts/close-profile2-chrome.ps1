# close-profile2-chrome.ps1
# 關閉 Selenium 相關的 chrome.exe（Profile 2 與 Chrome-Selenium 兩種 profile），
# 並一併清掉 chromedriver.exe 與卡住的 python.exe (selenium_login_test.py / main.py)。
# 先用 CloseMainWindow() 優雅關閉 Chrome（避免累積 variations_crash_streak），
# 殘留再 Stop-Process -Force。只關自動化相關 process。
#
# 重要：此腳本通常由 main.py 自己呼叫做預清理，必須排除「呼叫者」的整條父鏈
# （pwsh.exe → python.exe），否則會把正在啟動的 main.py 一起殺掉，使用者會看到
# 完全沒輸出就回到 prompt 的詭異現象（subprocess 父被 SIGKILL 等同於程式靜默死亡）。

# 蒐集需保護的 PID：本腳本自己 + 一路往上的父行程鏈
$selfPids = @{}
$cur = $PID
while ($cur) {
    $selfPids[[int]$cur] = $true
    $parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$cur" -ErrorAction SilentlyContinue).ParentProcessId
    if (-not $parent -or $parent -eq 0 -or $selfPids.ContainsKey([int]$parent)) { break }
    $cur = $parent
}

$chromes = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object {
        $_.CommandLine -like "*Profile 2*" -or
        $_.CommandLine -like "*Chrome-Selenium*" -or
        $_.CommandLine -like "*--remote-debugging-port*" -or
        $_.CommandLine -like "*--test-type=webdriver*"
    }
$drivers = Get-CimInstance Win32_Process -Filter "Name='chromedriver.exe'"
$pys = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {
        ($_.CommandLine -like "*selenium_login_test.py*" -or
         $_.CommandLine -like "*\sssh-automation\main.py*" -or
         $_.CommandLine -like "*/sssh-automation/main.py*") -and
        -not $selfPids.ContainsKey([int]$_.ProcessId)
    }

# 階段 1：對 Chrome 主程序送 CloseMainWindow（優雅關閉）
if ($chromes) {
    Write-Host ("Stage 1: graceful close for {0} chrome.exe..." -f $chromes.Count)
    foreach ($p in $chromes) {
        $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
        if ($proc -and $proc.MainWindowHandle -ne 0) {
            try { $proc.CloseMainWindow() | Out-Null } catch {}
        }
    }
    Start-Sleep -Milliseconds 1500
}

# 階段 2：殘留的 chrome / chromedriver / python 強制終止
$remaining = @()
foreach ($p in $chromes) {
    $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    if ($proc) { $remaining += $proc }
}
foreach ($p in $drivers) {
    $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    if ($proc) { $remaining += $proc }
}
foreach ($p in $pys) {
    $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    if ($proc) { $remaining += $proc }
}
if ($remaining.Count -gt 0) {
    Write-Host ("Stage 2: force kill {0} stuck process(es)..." -f $remaining.Count)
    foreach ($proc in $remaining) {
        Write-Host ("  - PID {0} {1}" -f $proc.Id, $proc.ProcessName)
        try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch {
            Write-Host ("    FAILED: {0}" -f $_.Exception.Message)
        }
    }
} elseif ($chromes -or $drivers -or $pys) {
    Write-Host "All processes closed gracefully."
} else {
    Write-Host "No Selenium-related process running."
}

# 清掉 force-kill 後殘留的 profile lock 檔，避免下次 Chrome 啟動時當作 profile in use
foreach ($selDir in @("$env:LOCALAPPDATA\Chrome-Selenium\User Data", "$env:LOCALAPPDATA\Chrome-Selenium-v2\User Data")) {
    if (Test-Path $selDir) {
        Remove-Item "$selDir\lockfile" -Force -ErrorAction SilentlyContinue
        Remove-Item "$selDir\Default\LOCK" -Force -ErrorAction SilentlyContinue
        Remove-Item "$selDir\Default\Singleton*" -Force -ErrorAction SilentlyContinue
        Write-Host "Cleared lock files in $selDir"
    }
}
