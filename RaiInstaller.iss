#ifndef MyAppName
  #define MyAppName "Rai"
#endif

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#ifndef MyDistDir
  #define MyDistDir "dist\\Rai"
#endif

#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename MyAppName + "-Setup-" + MyAppVersion
#endif

#define InstallerPassword GetEnv("RAI_INSTALLER_PASSWORD")
#if InstallerPassword == ""
  #error Set RAI_INSTALLER_PASSWORD before compiling this installer.
#endif

[Setup]
AppId={{3AAFAE54-1D3B-4B73-9AD5-DC7F9976EC78}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer-dist
OutputBaseFilename={#MyOutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
Password={#InstallerPassword}
Encryption=yes
UninstallDisplayIcon={app}\Rai.exe
SetupIconFile=logo.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\Rai.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Rai.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Rai.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
