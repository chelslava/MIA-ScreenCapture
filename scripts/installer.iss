; Inno Setup script — собирает Windows-инсталлятор из уже готового
; PyInstaller-EXE (dist/MIA-ScreenCapture.exe). Используется в
; .github/workflows/release.yml (job "Build Windows EXE").
;
; Версия передаётся снаружи через /DMyAppVersion=X.Y.Z (см. version.py —
; единственный источник версии пакета). AppId — фиксированный GUID,
; не менять между релизами: по нему Windows понимает, что это
; обновление существующей установки, а не новое приложение.

#define MyAppName "MIA-ScreenCapture"
#define MyAppPublisher "MIA Development Team"
#define MyAppURL "https://github.com/chelslava/MIA-ScreenCapture"
#define MyAppExeName "MIA-ScreenCapture.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{D3BBACFB-B62F-4F55-A35B-591B6F1F5E20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=MIA-ScreenCapture-Setup
SetupIconFile=..\docs\assets\MIA-ScreenCapture.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\MIA-ScreenCapture.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
