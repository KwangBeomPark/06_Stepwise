; Script for Stepwise (PL Suite App06)
; Standard Per-User installer for PL Suite applications (App01 ~ App10).

#ifndef MyAppVersion
#define MyAppVersion "0.3.0"
#endif

#define MyAppName "Stepwise"
#define MyAppPublisher "KwangBeomPark"
#define MyAppURL "https://github.com/KwangBeomPark/06_Stepwise"
#define MyAppExeName "Stepwise.exe"

[Setup]
AppId={{C782B3E1-628D-4C10-9E1D-3A20B71E86E2}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\Stepwise
DefaultGroupName=Stepwise
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release\dist
OutputBaseFilename=App06_Stepwise-Setup_v{#MyAppVersion}
SetupIconFile=..\assets\icons\stepwise.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
CloseApplications=yes
CloseApplicationsFilter=Stepwise.exe

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; UserSetting directory preservation (never deleted on uninstall)
Name: "{app}\UserSetting"; Flags: uninsneveruninstall

[Files]
Source: "..\dist\Stepwise\*"; DestDir: "{app}"; Excludes: "UserSetting\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"

[Registry]
; Associate .swm with Stepwise in Current User (Non-Admin)
Root: HKCU; Subkey: "Software\Classes\.swm"; ValueType: string; ValueName: ""; ValueData: "Stepwise.Macro"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Stepwise.Macro"; ValueType: string; ValueName: ""; ValueData: "Stepwise Macro Package"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Stepwise.Macro\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\Stepwise.Macro\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
