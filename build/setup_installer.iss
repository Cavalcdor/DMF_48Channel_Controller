; DMF 48通道控制器 — Inno Setup 安装脚本
; 使用 Inno Setup 6 (https://jrsoftware.org/isinfo.php) 编译

#define MyAppName "DMF 48通道控制器"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Charles WENG"
#define MyAppURL "https://github.com/Cavalcdor/DMF_48Channel_Controller"
#define MyAppExeName "DMF_48Channel_Controller.exe"

[Setup]
; 应用信息
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 安装包基本信息
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=.
OutputBaseFilename=DMF_48Channel_Controller_Setup_v{#MyAppVersion}_Windows_x86_CharlesWENG

; 压缩与安装界面
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableProgramGroupPage=yes

; 图标
SetupIconFile=icon.ico

; 卸载控制面板显示
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}

; 版本信息
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} — 基于 PyQt5 的数字微流控控制器
VersionInfoTextVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: checkedonce

[Files]
; 主程序（PyInstaller 单文件模式输出）
Source: "..\dist\DMF_48Channel_Controller.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 安装完成后可选运行
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
; 卸载后删除可能残留的配置文件
Type: filesandordirs; Name: "{userappdata}\{#MyAppName}"
Type: filesandordirs; Name: "{localappdata}\{#MyAppName}"

[Code]
{ 安装前检查是否正在运行 }
function IsAppRunning: Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  { taskkill /f /im 返回 0=成功杀掉了进程, 128=无此进程 }
  if Exec('taskkill', '/f /im ' + '{#MyAppExeName}', '', SW_HIDE,
          ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

function InitializeSetup: Boolean;
var
  RetVal: Integer;
begin
  Result := True;
  if IsAppRunning then
  begin
    RetVal := SuppressibleMsgBox(
      '检测到应用程序正在运行，是否自动关闭后继续安装？' + #13#13 +
      '选择「是」将自动关闭程序并继续安装。' + #13 +
      '选择「否」将取消安装，请保存数据后重试。',
      mbConfirmation, MB_YESNO, IDYES);
    if RetVal <> IDYES then
      Result := False;
  end;
end;
