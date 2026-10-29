param(
    [switch]$Installer,
    [switch]$InstallInnoSetup,
    [switch]$SkipAppBuild,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Get-AppConstant {
    param([Parameter(Mandatory = $true)][string]$Name)

    $text = Get-Content -Path (Join-Path $root "main.py") -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?m)^$Name\s*=\s*`"([^`"]+)`"")
    if (-not $match.Success) {
        throw "Could not find $Name in main.py."
    }
    return $match.Groups[1].Value
}

function Get-IsccPath {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    return $null
}

function Ensure-AppIcon {
    $pngPath = Join-Path $root "logo.png"
    $icoPath = Join-Path $root "logo.ico"

    if (-not (Test-Path $pngPath)) {
        throw "Expected icon source at $pngPath."
    }

    & $python -c "from PySide6.QtGui import QImage; import sys; img = QImage(sys.argv[1]); ok = (not img.isNull()) and img.save(sys.argv[2]); raise SystemExit(0 if ok else 1)" $pngPath $icoPath
    if (-not (Test-Path $icoPath)) {
        throw "Icon generation completed but $icoPath was not found."
    }
}

function Get-BuildPython {
    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return "python"
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter()][string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        $argText = if ($Arguments.Count -gt 0) { " " + ($Arguments -join " ") } else { "" }
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath$argText"
    }
}

if ($Clean) {
    foreach ($path in @("build", "dist", "installer-dist")) {
        $full = Join-Path $root $path
        if (Test-Path $full) {
            try {
                Remove-Item -Path $full -Recurse -Force
            }
            catch {
                if ($path -eq "installer-dist") {
                    Write-Warning "Could not fully clean $full. Continuing because a previous installer may still be open."
                }
                else {
                    throw
                }
            }
        }
    }
}

$python = Get-BuildPython

if (-not $SkipAppBuild) {
Invoke-CheckedCommand -FilePath $python -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-CheckedCommand -FilePath $python -Arguments @("-m", "pip", "install", "-r", (Join-Path $root "requirements-build.txt"))
Ensure-AppIcon
Invoke-CheckedCommand -FilePath $python -Arguments @("-m", "PyInstaller", "--noconfirm", "--clean", (Join-Path $root "Rai.spec"))
}

$appName = Get-AppConstant -Name "APP_NAME"
$appVersion = Get-AppConstant -Name "APP_VERSION"
$distDir = Join-Path $root ("dist\" + $appName)
$exePath = Join-Path $distDir ($appName + ".exe")

if (-not (Test-Path $exePath)) {
    throw "Build completed but $exePath was not found."
}

Write-Host "Built executable: $exePath"

if ($Installer -or $InstallInnoSetup) {
    $iscc = Get-IsccPath
    $installerBaseName = "$appName-Setup-$appVersion-" + (Get-Date -Format "yyyyMMdd-HHmmss")

    if ((-not $iscc) -and $InstallInnoSetup) {
        Invoke-CheckedCommand -FilePath "winget" -Arguments @("install", "--id", "JRSoftware.InnoSetup", "-e", "--accept-package-agreements", "--accept-source-agreements")
        $iscc = Get-IsccPath
    }

    if (-not $iscc) {
        throw "Inno Setup compiler not found. Install JRSoftware.InnoSetup or rerun with -InstallInnoSetup."
    }

    $previousPassword = $env:RAI_INSTALLER_PASSWORD
    try {
        if ([string]::IsNullOrWhiteSpace($env:RAI_INSTALLER_PASSWORD)) {
            $securePassword = Read-Host "Password for this release's installer" -AsSecureString
            $env:RAI_INSTALLER_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
        }
        if ([string]::IsNullOrWhiteSpace($env:RAI_INSTALLER_PASSWORD) -or $env:RAI_INSTALLER_PASSWORD -match '[\r\n]') {
            throw "Installer password must be nonempty and on one line."
        }
        Invoke-CheckedCommand -FilePath $iscc -Arguments @("/DMyAppName=$appName", "/DMyAppVersion=$appVersion", "/DMyDistDir=$distDir", "/DMyOutputBaseFilename=$installerBaseName", (Join-Path $root "RaiInstaller.iss"))
    }
    finally {
        $env:RAI_INSTALLER_PASSWORD = $previousPassword
    }

    $installerPath = Join-Path $root ("installer-dist\" + $installerBaseName + ".exe")
    if (-not (Test-Path $installerPath)) {
        throw "Installer build completed but $installerPath was not found."
    }

    Write-Host "Built installer: $installerPath"
}
