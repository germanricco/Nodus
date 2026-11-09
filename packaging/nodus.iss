; Inno Setup recipe for the Nodus installer. Run through scripts/build.py, which passes
; the version (/DAppVersion=) and the taskbar ID (/DAppUserModelID=), and expects
; PyInstaller's output in dist/Nodus.
;
; Installs per user (no administrator prompt) into %LOCALAPPDATA%\Programs\Nodus. The
; user's data lives in %APPDATA%\Nodus, outside the program folder, so upgrading or
; uninstalling never touches it.

#ifndef AppVersion
  #error Pass the version with /DAppVersion=x.y.z
#endif
#ifndef AppUserModelID
  #error Pass the taskbar ID with /DAppUserModelID= (nodus.APP_USER_MODEL_ID)
#endif

[Setup]
; Fixed forever: it is how Windows recognizes a new version as the same program.
AppId={{99EAA1B1-94F2-426D-BDC5-B54D9C88418F}
AppName=Nodus
AppVersion={#AppVersion}
AppVerName=Nodus {#AppVersion}
AppPublisher=German Ricco
AppPublisherURL=https://github.com/germanricco/Nodus
AppSupportURL=https://github.com/germanricco/Nodus/issues
AppUpdatesURL=https://github.com/germanricco/Nodus/releases
DefaultDirName={autopf}\Nodus
DefaultGroupName=Nodus
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
SetupIconFile=nodus.ico
UninstallDisplayIcon={app}\Nodus.exe
UninstallDisplayName=Nodus
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; Closes a running Nodus before replacing its files.
CloseApplications=yes
OutputBaseFilename=Nodus-Setup-{#AppVersion}
VersionInfoVersion={#AppVersion}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Files of the previous version that the new one no longer ships.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Nodus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; The same ID the running app declares, so Windows links its window to these shortcuts
; and a pinned Nodus shows the program's icon instead of a blank square.
Name: "{autoprograms}\Nodus"; Filename: "{app}\Nodus.exe"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\Nodus"; Filename: "{app}\Nodus.exe"; Tasks: desktopicon; AppUserModelID: "{#AppUserModelID}"

[Registry]
; Nodus writes this value itself when the user turns on «Abrir Nodus al iniciar Windows».
; ValueType none creates nothing on install; the flag removes the value on uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Nodus"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Nodus.exe"; Description: "{cm:LaunchProgram,Nodus}"; Flags: nowait postinstall skipifsilent
