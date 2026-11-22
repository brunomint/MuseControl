; Inno Setup: instalador do MuseControl para Windows.
; O GitHub Actions monta: iscc /DVersao=2.0.0 empacotar\instalador-windows.iss
; (precisa antes do PyInstaller: pasta dist\MuseControl)

#ifndef Versao
  #define Versao "0.0.0"
#endif

[Setup]
AppId={{6B0F4C1E-3A7D-4C1B-9D55-6D2C8B7E1F40}
AppName=MuseControl
AppVersion={#Versao}
AppPublisher=brunomint
AppPublisherURL=https://github.com/brunomint/MuseControl
DefaultDirName={autopf}\MuseControl
DefaultGroupName=MuseControl
; instala só para o usuário: não pede senha de administrador
PrivilegesRequired=lowest
OutputDir=..\Output
OutputBaseFilename=MuseControl-{#Versao}-instalador-windows
SetupIconFile=musecontrol.ico
UninstallDisplayIcon={app}\MuseControl.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\dist\MuseControl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MuseControl"; Filename: "{app}\MuseControl.exe"
Name: "{group}\Desinstalar o MuseControl"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MuseControl"; Filename: "{app}\MuseControl.exe"; Tasks: atalho

[Run]
Filename: "{app}\MuseControl.exe"; Description: "Abrir o MuseControl agora"; Flags: nowait postinstall skipifsilent

; Os projetos e variáveis ficam em %APPDATA%\MuseControl e NÃO são apagados
; ao desinstalar ou atualizar.
