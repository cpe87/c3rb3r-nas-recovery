#define AppVersion "0.1.3"
[Setup]
AppId={{B4F8199C-5419-49DA-961E-DBA1D5188160}
AppName=NAS Recovery Public
AppVersion={#AppVersion}
AppPublisher=cpe87
DefaultDirName={localappdata}\Programs\NAS Recovery Public
DefaultGroupName=NAS Recovery Public
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release
OutputBaseFilename=NAS-Recovery-Public-0.1.3-windows-x64-setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
InfoBeforeFile=INSTALL-NOTES.txt
UninstallDisplayIcon={app}\NAS-Recovery-Public.exe
CloseApplications=no
RestartApplications=no
DisableProgramGroupPage=yes
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
[Files]
Source: "..\dist\NAS-Recovery-Public\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\NAS Recovery Public"; Filename: "{app}\NAS-Recovery-Public.exe"
Name: "{autodesktop}\NAS Recovery Public"; Filename: "{app}\NAS-Recovery-Public.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\NAS-Recovery-Public.exe"; Description: "Launch NAS Recovery Public"; Flags: nowait postinstall skipifsilent unchecked
