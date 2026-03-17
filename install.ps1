# CypherPulse Installation Script for Windows
# Run in PowerShell as Administrator

$ErrorActionPreference = "Stop"

$RepoUrl    = "https://github.com/tibor-ai/cypherpulse.git"
$DefaultDir = "$env:USERPROFILE\cypherpulse"
$MinPython  = [version]"3.9.0"

function msg  { param($t) Write-Host $t }
function ok   { param($t) Write-Host "[OK]  $t" -ForegroundColor Green }
function warn { param($t) Write-Host "[!]   $t" -ForegroundColor Yellow }
function die  { param($t) Write-Host "[ERR] $t" -ForegroundColor Red; exit 1 }

msg ""
msg "=================================================="
msg "  CypherPulse Installer"
msg "=================================================="
msg ""

# ---------- install location ----------
$input = Read-Host "Install directory [default: $DefaultDir]"
$InstallDir = if ($input.Trim() -ne "") { $input.Trim() } else { $DefaultDir }
msg "Installing to: $InstallDir"

# ---------- python ----------
function Test-PythonVersion {
    try {
        $v = & python --version 2>&1
        $ver = [version]($v -replace "Python ", "")
        return $ver -ge $MinPython
    } catch { return $false }
}

if (Test-PythonVersion) {
    $pyVer = (& python --version 2>&1) -replace "Python ", ""
    ok "Python $pyVer found"
} else {
    warn "Python 3.9+ not found. Installing..."
    $installed = $false

    try {
        winget --version | Out-Null
        winget install --silent --accept-package-agreements --accept-source-agreements Python.Python.3.12
        if ($LASTEXITCODE -eq 0) { $installed = $true; ok "Python installed via winget" }
    } catch {}

    if (-not $installed) {
        try {
            choco --version | Out-Null
            choco install python -y
            if ($LASTEXITCODE -eq 0) { $installed = $true; ok "Python installed via Chocolatey" }
        } catch {}
    }

    if (-not $installed) {
        $url = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
        $tmp = "$env:TEMP\python-installer.exe"
        try {
            Invoke-WebRequest -Uri $url -OutFile $tmp
            Start-Process -FilePath $tmp -Args "/quiet InstallAllUsers=1 PrependPath=1" -Wait
            Remove-Item $tmp
            $installed = $true
            ok "Python installed from python.org"
        } catch { die "Failed to install Python. Install manually from https://www.python.org/downloads/windows/" }
    }

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    Start-Sleep -Seconds 2

    if (Test-PythonVersion) {
        ok "Python ready"
    } else {
        warn "Python was installed but PATH needs a new shell to take effect."
        warn "Close this window, open a new PowerShell, and re-run the installer."
        exit 0
    }
}

msg ""

# ---------- clone / update ----------
if (Test-Path "$InstallDir\.git") {
    $upd = Read-Host "Existing install found. Update it? [Y/n]"
    if ($upd -ne "n" -and $upd -ne "N") {
        Push-Location $InstallDir
        try {
            if (Get-Command git -ErrorAction SilentlyContinue) {
                git pull origin main
                ok "Repository updated"
            } else { warn "Git not found, skipping update" }
        } catch { warn "Git pull failed, skipping update" }
        Pop-Location
    }
} else {
    msg "Cloning repository..."
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone $RepoUrl $InstallDir
    } else {
        warn "Git not found. Downloading ZIP..."
        $zip = "$env:TEMP\cypherpulse.zip"
        try {
            Invoke-WebRequest -Uri "https://github.com/tibor-ai/cypherpulse/archive/refs/heads/main.zip" -OutFile $zip
            Expand-Archive -Path $zip -DestinationPath "$env:TEMP\cp-tmp" -Force
            Move-Item "$env:TEMP\cp-tmp\cypherpulse-main" $InstallDir
            Remove-Item $zip, "$env:TEMP\cp-tmp" -Recurse -ErrorAction SilentlyContinue
        } catch { die "Failed to download repository" }
    }
    ok "Repository ready"
}

Set-Location $InstallDir
msg ""

# ---------- virtualenv + deps ----------
msg "Setting up Python environment..."

if (-not (Test-Path "venv")) {
    python -m venv venv
    if (-not $?) { die "Failed to create virtual environment" }
}

& ".\venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet
if (-not $?) { die "Failed to install dependencies" }

& ".\venv\Scripts\pip.exe" install -e . --quiet 2>$null
ok "Dependencies installed"

# ---------- config: API key + username ----------
msg ""
msg "=================================================="
msg "  Setup"
msg "=================================================="

$EnvFile = "$InstallDir\.env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item "config.example.env" $EnvFile
}

# Check for existing real values
$existingKey  = (Select-String -Path $EnvFile -Pattern "^TWITTER_API_KEY=(.+)" | Select-Object -First 1).Matches.Groups[1].Value
$existingUser = (Select-String -Path $EnvFile -Pattern "^TWITTER_USERNAME=(.+)" | Select-Object -First 1).Matches.Groups[1].Value

$hasConfig = ($existingKey -and $existingKey -ne "your_api_key_here" -and
              $existingUser -and $existingUser -ne "your_username_here")

if ($hasConfig) {
    msg ""
    msg "Existing configuration found:"
    msg "  API key : $($existingKey.Substring(0, [Math]::Min(8, $existingKey.Length)))..."
    msg "  Username: $existingUser"
    msg ""
    $keep = Read-Host "Keep existing config? [Y/n]"
    if ($keep -eq "n" -or $keep -eq "N") { $hasConfig = $false }
}

if (-not $hasConfig) {
    msg ""
    msg "Get your free API key at: https://twitterapi.io/?ref=quenosai"
    msg ""

    # Validate API key
    while ($true) {
        $ApiKey = Read-Host "twitterapi.io API key"
        $ApiKey = $ApiKey.Trim()
        if ($ApiKey -eq "") { warn "API key cannot be empty. Try again." }
        elseif ($ApiKey -eq "your_api_key_here") { warn "Enter your actual API key, not the placeholder." }
        else { break }
    }

    msg ""

    # Validate username
    while ($true) {
        $TwitterUser = (Read-Host "Your X/Twitter username (without @)").Trim().TrimStart("@")
        if ($TwitterUser -eq "") { warn "Username cannot be empty. Try again." }
        elseif ($TwitterUser -notmatch '^[A-Za-z0-9_]+$') { warn "Invalid characters. Use only letters, numbers, and underscores." }
        else { break }
    }

    # Write values to .env
    $envContent = Get-Content $EnvFile -Raw
    if ($envContent -match "TWITTER_API_KEY=") {
        $envContent = $envContent -replace "TWITTER_API_KEY=.*", "TWITTER_API_KEY=$ApiKey"
    } else {
        $envContent += "`nTWITTER_API_KEY=$ApiKey"
    }
    if ($envContent -match "TWITTER_USERNAME=") {
        $envContent = $envContent -replace "TWITTER_USERNAME=.*", "TWITTER_USERNAME=$TwitterUser"
    } else {
        $envContent += "`nTWITTER_USERNAME=$TwitterUser"
    }
    Set-Content -Path $EnvFile -Value $envContent -NoNewline
    ok "Config saved"
} else {
    $ApiKey = $existingKey
    $TwitterUser = $existingUser
}

# ---------- optional scheduling ----------
msg ""
msg "--------------------------------------------------"
msg "  Automated data collection"
msg "--------------------------------------------------"
$sched = Read-Host "Schedule automatic data collection? [Y/n]"

if ($sched -ne "n" -and $sched -ne "N") {
    msg ""
    msg "How often?"
    msg "  1) Hourly"
    msg "  2) Every 6 hours"
    msg "  3) Daily at 9 AM (recommended)"
    msg "  4) Custom"
    msg ""
    $freq = Read-Host "Choice [1-4, default 3]"
    if ([string]::IsNullOrWhiteSpace($freq)) { $freq = "3" }

    $cp = "$InstallDir\venv\Scripts\cypherpulse.exe"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-WindowStyle Hidden -NonInteractive -Command `"& '$cp' scan; & '$cp' collect`""

    switch ($freq) {
        "1" {
            $trigger  = New-ScheduledTaskTrigger -Once -At "9:00AM" -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue)
            $freqDesc = "hourly"
        }
        "2" {
            $trigger  = New-ScheduledTaskTrigger -Once -At "9:00AM" -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration ([TimeSpan]::MaxValue)
            $freqDesc = "every 6 hours"
        }
        "4" {
            msg ""
            msg "Custom options:"
            msg "  1) Daily at custom time"
            msg "  2) Weekly on specific day"
            $ct = Read-Host "Option [1-2]"
            if ($ct -eq "2") {
                $day  = Read-Host "Day (e.g. Monday)"
                $time = Read-Host "Time (e.g. 9:00AM)"
                $trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $day -At $time
                $freqDesc = "weekly on $day at $time"
            } else {
                $time = Read-Host "Time (e.g. 2:30PM)"
                $trigger  = New-ScheduledTaskTrigger -Daily -At $time
                $freqDesc = "daily at $time"
            }
        }
        default {
            $trigger  = New-ScheduledTaskTrigger -Daily -At "9:00AM"
            $freqDesc = "daily at 9 AM"
        }
    }

    try {
        Register-ScheduledTask -TaskName "CypherPulse" -Action $action -Trigger $trigger -Force | Out-Null
        ok "Scheduled task added ($freqDesc)"
    } catch {
        warn "Could not create scheduled task (needs Administrator). Set it up later — see README."
    }
} else {
    msg "Skipped. To add later, see README."
}

# ---------- initial data collection ----------
msg ""
msg "=================================================="
msg "  Fetching your initial data..."
msg "=================================================="
msg ""

$cp = "$InstallDir\venv\Scripts\cypherpulse.exe"

msg "Scanning your recent tweets..."
try {
    & $cp scan
    ok "Scan complete"
} catch { die "Failed to scan tweets. Check your API key and username in $EnvFile" }

msg ""
msg "Collecting engagement metrics..."
try {
    & $cp collect
    ok "Metrics collected"
} catch { warn "Metrics collection failed. Run 'cypherpulse collect' manually after a few minutes." }

# ---------- launch dashboard ----------
msg ""
$launch = Read-Host "Open the dashboard now in your browser? [Y/n]"
if ($launch -ne "n" -and $launch -ne "N") {
    msg "Starting dashboard at http://localhost:8080 ..."
    msg "(Press Ctrl+C to stop)"
    msg ""
    & $cp serve
}

# ---------- done ----------
msg ""
msg "=================================================="
msg "  CypherPulse is ready!"
msg "=================================================="
msg ""
msg "To run manually:"
msg "  cd $InstallDir"
msg "  .\venv\Scripts\Activate.ps1"
msg "  cypherpulse scan      # fetch new tweets"
msg "  cypherpulse collect   # snapshot metrics"
msg "  cypherpulse serve     # open dashboard"
msg ""
