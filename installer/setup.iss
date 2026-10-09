; Script for Stepwise (PL Suite App06)
; Standard Per-User installer for PL Suite applications (App01 ~ App10).

#ifndef MyAppVersion
#define MyAppVersion "0.3.1"
#endif

#define MyAppName "Stepwise"
#define MyAppPublisher "KwangBeomPark"
#define MyAppURL "https://github.com/KwangBeomPark/06_Stepwise"
#define MyAppExeName "Stepwise.exe"
#ifndef MyAppSourceDir
#define MyAppSourceDir "..\dist\Stepwise"
#endif
#ifndef MyAppOutputDir
#define MyAppOutputDir "..\build\installer-preview"
#endif

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
OutputDir={#MyAppOutputDir}
OutputBaseFilename=App06_Stepwise_Setup_v{#MyAppVersion}
SetupIconFile=..\assets\icons\stepwise.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
CloseApplicationsFilter=Stepwise.exe
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; UserSetting directory preservation (never deleted on uninstall)
Name: "{app}\UserSetting"; Flags: uninsneveruninstall

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Excludes: "UserSetting\*,macros\*,results\*"; Flags: ignoreversion recursesubdirs createallsubdirs; BeforeInstall: CheckStepwiseFiles

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

[Code]
var
  StepwiseFilesChecked: Boolean;

procedure CheckStepwiseFiles;
var
  AppPath: String;
  AppFile: TFileStream;
begin
  if StepwiseFilesChecked then Exit;
  { This runs before the first file copy, after Restart Manager's normal close request. }
  AppPath := ExpandConstant('{app}\{#MyAppExeName}');
  if FileExists(AppPath) then begin
    try
      AppFile := TFileStream.Create(AppPath, fmOpenReadWrite or fmShareExclusive);
      AppFile.Free;
    except
      RaiseException('Stepwise is still running or unavailable. Stop the macro, close Stepwise, and retry installation.');
    end;
  end;
  StepwiseFilesChecked := True;
end;
