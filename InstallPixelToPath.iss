[Setup]
AppName=PixelToPath
AppVersion=3.0.0
DefaultDirName={pf}\PixelToPath
DefaultGroupName=PixelToPath
OutputDir=output
OutputBaseFilename=Setup_PixelToPath
SetupIconFile=PixelToPath\_internal\interface\assets\app_icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
; Interface graphique (build PyInstaller onedir)
Source: "PixelToPath\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
; CLI Pro (build PyInstaller onedir séparé — console visible, binaire ptp.exe)
Source: "ptp\*"; DestDir: "{app}\cli"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PixelToPath"; Filename: "{app}\PixelToPath.exe"; IconFilename: "{app}\_internal\interface\assets\app_icon.ico"
Name: "{commondesktop}\PixelToPath"; Filename: "{app}\PixelToPath.exe"; IconFilename: "{app}\_internal\interface\assets\app_icon.ico"; Tasks: desktopicon
; CLI : ouvre un terminal DANS le dossier cli — `ptp convert … -o sortie`
Name: "{group}\PixelToPath CLI"; Filename: "{sys}\cmd.exe"; Parameters: "/k ""{app}\cli\ptp.exe"" --help"; WorkingDir: "{app}\cli"; IconFilename: "{app}\_internal\interface\assets\app_icon.ico"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Icônes supplémentaires:"

[Run]
Filename: "{app}\PixelToPath.exe"; Description: "Lancer PixelToPath"; Flags: nowait postinstall skipifsilent
