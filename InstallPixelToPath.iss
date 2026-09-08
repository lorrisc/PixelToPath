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
; Path modifié par le [Code] ci-dessous : diffuse WM_SETTINGCHANGE en fin
; d'installation → les NOUVEAUX terminaux voient `ptp` sans se déconnecter.
ChangesEnvironment=yes

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

[Code]
// ── PATH : rend `ptp` appelable de n'importe quel terminal ──────────────────
// Équivalent Windows du lien ~/.local/bin/ptp de l'installateur Linux :
// {app}\cli est ajouté au Path SYSTÈME (install admin, {pf}) dans
// Session Manager\Environment, puis retiré à la désinstallation.
// Lecture : RegQueryStringValue rend les données BRUTES des deux types
// REG_SZ/REG_EXPAND_SZ (%SystemRoot% non étendu — vérifié sous Inno 6.7).
// Écriture : toujours REG_EXPAND_SZ (type standard du Path système ; passer
// un littéral en expand est inoffensif, l'inverse casserait l'expansion).

const
  EnvironmentKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  WM_SETTINGCHANGE = $001A;

procedure EnvChanged;
var
  S: string;
begin
  // Nouveaux terminaux = enfants d'Explorer : il doit recharger son
  // environnement, sinon `ptp` reste introuvable jusqu'à déconnexion.
  S := 'Environment';
  SendBroadcastNotifyMessage(WM_SETTINGCHANGE, 0, CastStringToInteger(S));
end;

procedure EnvWritePath(Paths: string);
begin
  RegWriteExpandStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path', Paths);
end;

procedure EnvAddPath(Path: string);
var
  OrigPaths: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path',
      OrigPaths) then
    OrigPaths := '';
  // Déjà présent → no-op (réinstallation, mise à jour au-dessus de l'existant).
  if Pos(';' + Uppercase(Path) + ';', ';' + Uppercase(OrigPaths) + ';') > 0 then
    exit;
  if OrigPaths = '' then
    OrigPaths := Path
  else
    OrigPaths := OrigPaths + ';' + Path;
  EnvWritePath(OrigPaths);
end;

procedure EnvRemovePath(Path: string);
var
  OrigPaths, Rest, NewPaths, Part: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path',
      OrigPaths) then
    exit;
  Rest := OrigPaths;
  NewPaths := '';
  while Length(Rest) > 0 do
  begin
    if Pos(';', Rest) > 0 then
    begin
      Part := Copy(Rest, 1, Pos(';', Rest) - 1);
      Rest := Copy(Rest, Pos(';', Rest) + 1, MaxInt);
    end
    else
    begin
      Part := Rest;
      Rest := '';
    end;
    // Comparaison insensible à la casse (PATH de cmd) ; ordre et casse des
    // autres entrées conservés à l'identique.
    if (Part <> '') and (Uppercase(Part) <> Uppercase(Path)) then
    begin
      if NewPaths = '' then
        NewPaths := Part
      else
        NewPaths := NewPaths + ';' + Part;
    end;
  end;
  // Rien retiré (Path absent de la liste) → ne pas réécrire la valeur.
  if NewPaths = OrigPaths then
    exit;
  EnvWritePath(NewPaths);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    EnvAddPath(ExpandConstant('{app}\cli'));
    EnvChanged;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    EnvRemovePath(ExpandConstant('{app}\cli'));
    EnvChanged;
  end;
end;

