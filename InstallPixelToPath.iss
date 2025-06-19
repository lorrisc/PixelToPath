[Setup]
AppName=PixelToPath
AppVersion=1.0.0
DefaultDirName={pf}\PixelToPath
DefaultGroupName=PixelToPath
OutputDir=output
OutputBaseFilename=Setup_PixelToPath
SetupIconFile=PixelToPath\_internal\interface\assets\app_icon.ico
Compression=lzma
SolidCompression=yes

[Files]
Source: "PixelToPath\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PixelToPath"; Filename: "{app}\PixelToPath.exe"; IconFilename: "{app}\_internal\interface\assets\app_icon.ico"
Name: "{commondesktop}\PixelToPath"; Filename: "{app}\PixelToPath.exe"; IconFilename: "{app}\_internal\interface\assets\app_icon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Icônes supplémentaires:"
