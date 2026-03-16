# CypherPulse Installation Script for Windows
# Run in PowerShell as Administrator

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/tibor-ai/cypherpulse.git"
$InstallDir = "$env:USERPROFILE\cypherpulse"
$MinPythonVersion = [version]"3.9.0"

Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   CypherPulse Installation" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check Python version
function Test-PythonVersion {
    try {
        $pythonCmd = Get-Command python -ErrorAction Stop
        $versionOutput = & python --version 2>&1
        $versionString = $versionOutput -replace "Python ", ""
        $version = [version]$versionString
        
        if ($version -ge $MinPythonVersion) {
            Write-Host "✓ Python $versionString found" -ForegroundColor Green
            return $true
        } else {
            Write-Host "⚠ Python $versionString found (need 3.9+)" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "⚠ Python not found" -ForegroundColor Yellow
        return $false
    }
}

# Install Python if needed
if (-not (Test-PythonVersion)) {
    Write-Host ""
    Write-Host "Python 3.9+ is required but not found." -ForegroundColor Yellow
    Write-Host "Installing Python automatically..." -ForegroundColor Cyan
    Write-Host ""
    
    $pythonInstalled = $false
    
    # Try winget first (Windows 11 and some Windows 10 versions)
    try {
        $wingetVersion = winget --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Attempting installation via winget..." -ForegroundColor Cyan
            
            winget install --silent --accept-package-agreements --accept-source-agreements Python.Python.3.12
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✓ Python installed via winget" -ForegroundColor Green
                $pythonInstalled = $true
            } else {
                Write-Host "⚠ winget installation failed, trying alternative method..." -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "⚠ winget not available, trying alternative method..." -ForegroundColor Yellow
    }
    
    # Try Chocolatey if winget failed
    if (-not $pythonInstalled) {
        try {
            $chocoVersion = choco --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Attempting installation via Chocolatey..." -ForegroundColor Cyan
                
                choco install python -y
                
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "✓ Python installed via Chocolatey" -ForegroundColor Green
                    $pythonInstalled = $true
                } else {
                    Write-Host "⚠ Chocolatey installation failed, trying direct download..." -ForegroundColor Yellow
                }
            }
        } catch {
            Write-Host "⚠ Chocolatey not available, trying direct download..." -ForegroundColor Yellow
        }
    }
    
    # Direct download from python.org if both package managers failed
    if (-not $pythonInstalled) {
        Write-Host "Downloading Python installer from python.org..." -ForegroundColor Cyan
        
        try {
            $url = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
            $installer = "$env:TEMP\python-installer.exe"
            
            Write-Host "Downloading from $url..." -ForegroundColor Gray
            Invoke-WebRequest -Uri $url -OutFile $installer
            
            Write-Host "Running silent installer..." -ForegroundColor Gray
            Start-Process -FilePath $installer -Args "/quiet InstallAllUsers=1 PrependPath=1" -Wait
            
            Remove-Item $installer
            Write-Host "✓ Python installer completed" -ForegroundColor Green
            $pythonInstalled = $true
        } catch {
            Write-Host "✗ Failed to download and install Python: $_" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please install Python manually from https://www.python.org/downloads/windows/" -ForegroundColor Yellow
            exit 1
        }
    }
    
    # Refresh PATH environment variable
    Write-Host ""
    Write-Host "Refreshing PATH environment..." -ForegroundColor Cyan
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    # Re-check Python version
    Start-Sleep -Seconds 2
    if (Test-PythonVersion) {
        Write-Host "✓ Python is now ready" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "⚠ Python was installed but is not yet available in this session." -ForegroundColor Yellow
        Write-Host "Please close this PowerShell window and open a NEW one," -ForegroundColor Yellow
        Write-Host "then re-run this installation script." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "This is necessary for the PATH changes to take effect." -ForegroundColor Gray
        exit 0
    }
}

Write-Host ""

# Clone or update repository
if (Test-Path $InstallDir) {
    Write-Host "📁 CypherPulse directory already exists at $InstallDir" -ForegroundColor Yellow
    $update = Read-Host "Update existing installation? (y/N)"
    
    if ($update -eq "y" -or $update -eq "Y") {
        Write-Host "Updating repository..." -ForegroundColor Cyan
        Push-Location $InstallDir
        
        try {
            if (Get-Command git -ErrorAction SilentlyContinue) {
                git pull origin main
            } else {
                Write-Host "⚠ Git not found, skipping update" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "⚠ Git pull failed, skipping update" -ForegroundColor Yellow
        }
        
        Pop-Location
    } else {
        Write-Host "Skipping repository update" -ForegroundColor Gray
    }
} else {
    Write-Host "📦 Downloading CypherPulse..." -ForegroundColor Cyan
    
    # Try git first, fall back to ZIP download
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Host "Using git to clone repository..." -ForegroundColor Gray
        git clone $RepoUrl $InstallDir
    } else {
        Write-Host "Git not found, downloading ZIP..." -ForegroundColor Yellow
        
        $zipUrl = "https://github.com/tibor-ai/cypherpulse/archive/refs/heads/main.zip"
        $zipPath = "$env:TEMP\cypherpulse.zip"
        
        try {
            Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
            Expand-Archive -Path $zipPath -DestinationPath "$env:TEMP\cypherpulse-temp" -Force
            Move-Item "$env:TEMP\cypherpulse-temp\cypherpulse-main" $InstallDir
            Remove-Item $zipPath
            Remove-Item "$env:TEMP\cypherpulse-temp" -Recurse
        } catch {
            Write-Host "✗ Failed to download repository" -ForegroundColor Red
            exit 1
        }
    }
}

Set-Location $InstallDir
Write-Host ""

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "🐍 Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
    
    if (-not $?) {
        Write-Host "✗ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}

# Activate and install dependencies
Write-Host "📚 Installing dependencies..." -ForegroundColor Cyan

& "$InstallDir\venv\Scripts\Activate.ps1"

python -m pip install --upgrade pip | Out-Null
python -m pip install -r requirements.txt

if (-not $?) {
    Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Install package in development mode
python -m pip install -e . 2>&1 | Out-Null

Write-Host ""

# Copy config file if needed
if (-not (Test-Path ".env")) {
    Write-Host "⚙️  Creating .env file from template..." -ForegroundColor Cyan
    Copy-Item "config.example.env" ".env"
    Write-Host "✓ .env file created" -ForegroundColor Green
} else {
    Write-Host "✓ .env file already exists (not overwriting)" -ForegroundColor Green
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "⏰ Set up automatic data collection?" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$schedule = Read-Host "Would you like CypherPulse to run automatically? (recommended) [Y/n]"

if ($schedule -ne "n" -and $schedule -ne "N") {
    Write-Host ""
    Write-Host "How often should CypherPulse collect data?" -ForegroundColor Cyan
    Write-Host "  1 = Hourly (best for active accounts)" -ForegroundColor White
    Write-Host "  2 = Every 6 hours" -ForegroundColor White
    Write-Host "  3 = Daily at 9 AM (default, recommended)" -ForegroundColor White
    Write-Host "  4 = Custom schedule" -ForegroundColor White
    Write-Host ""
    
    $freqChoice = Read-Host "Choose frequency [1-4] (default: 3)"
    if ([string]::IsNullOrEmpty($freqChoice)) { $freqChoice = "3" }
    
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-WindowStyle Hidden -Command `"cd $InstallDir; .\venv\Scripts\activate; cypherpulse scan; cypherpulse collect`""
    
    switch ($freqChoice) {
        "1" {
            $trigger = New-ScheduledTaskTrigger -Once -At "9:00AM" -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue)
            $freqDesc = "hourly"
        }
        "2" {
            $trigger = New-ScheduledTaskTrigger -Once -At "9:00AM" -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration ([TimeSpan]::MaxValue)
            $freqDesc = "every 6 hours"
        }
        "3" {
            $trigger = New-ScheduledTaskTrigger -Daily -At "9:00AM"
            $freqDesc = "daily at 9 AM"
        }
        "4" {
            Write-Host ""
            Write-Host "Custom scheduling options:" -ForegroundColor Cyan
            Write-Host "  1 = Daily at custom time" -ForegroundColor White
            Write-Host "  2 = Weekly on specific day" -ForegroundColor White
            Write-Host "  3 = Hourly (with custom start time)" -ForegroundColor White
            
            $customType = Read-Host "Choose option [1-3]"
            
            switch ($customType) {
                "1" {
                    $customTime = Read-Host "Enter time (e.g., 2:30PM)"
                    $trigger = New-ScheduledTaskTrigger -Daily -At $customTime
                    $freqDesc = "daily at $customTime"
                }
                "2" {
                    $customDay = Read-Host "Enter day (e.g., Monday)"
                    $customTime = Read-Host "Enter time (e.g., 9:00AM)"
                    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $customDay -At $customTime
                    $freqDesc = "weekly on $customDay at $customTime"
                }
                "3" {
                    $customTime = Read-Host "Enter start time (e.g., 9:00AM)"
                    $trigger = New-ScheduledTaskTrigger -Once -At $customTime -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue)
                    $freqDesc = "hourly starting at $customTime"
                }
                default {
                    $trigger = New-ScheduledTaskTrigger -Daily -At "9:00AM"
                    $freqDesc = "daily at 9 AM"
                }
            }
        }
        default {
            $trigger = New-ScheduledTaskTrigger -Daily -At "9:00AM"
            $freqDesc = "daily at 9 AM"
        }
    }
    
    try {
        Register-ScheduledTask -TaskName "CypherPulse" -Action $action -Trigger $trigger -Force | Out-Null
        Write-Host ""
        Write-Host "✓ Scheduled task added. CypherPulse will collect data automatically ($freqDesc)." -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "⚠ Failed to create scheduled task. You may need to run PowerShell as Administrator." -ForegroundColor Yellow
        Write-Host "You can set this up later — see README for instructions." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "You can set this up later — see README for instructions." -ForegroundColor Gray
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✓ Installation complete!" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Get your API key from https://twitterapi.io/?ref=quenosai" -ForegroundColor White
Write-Host ""
Write-Host "2. Edit your configuration:" -ForegroundColor White
Write-Host "   notepad $InstallDir\.env" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Update these values with your actual credentials:" -ForegroundColor White
Write-Host "   TWITTER_API_KEY=<your_actual_api_key>" -ForegroundColor Gray
Write-Host "   TWITTER_USERNAME=<your_actual_username>" -ForegroundColor Gray
Write-Host ""
Write-Host "   Get your API key from: https://twitterapi.io/?ref=quenosai" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Start the dashboard:" -ForegroundColor White
Write-Host "   cd $InstallDir" -ForegroundColor Yellow
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "   cypherpulse serve" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Then open: http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "════════════════════════════════════════════════════" -ForegroundColor Cyan
