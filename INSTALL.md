# DMF 48通道控制器 — 安装指南

<div align="center">

**版本 2.0.0 | 发布者：Charles WENG | © 2026**

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://python.org)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15%2B-green)](https://pypi.org/project/PyQt5/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-brightgreen)](https://www.microsoft.com/windows)

</div>

---

## 📦 安装包概览

### 文件信息

| 项目 | 内容 |
|------|------|
| **文件名** | `DMF_48Channel_Controller_Setup_v2.0.0_Windows_x86_CharlesWENG.exe` |
| **版本** | v2.0.0 |
| **架构** | Windows x86（兼容 32/64 位系统） |
| **大小** | ~38.4 MB |
| **发布者** | Charles WENG |
| **数字微流控** | DMF 48通道数字微流控控制器上位机 |

---

## ✨ 安装程序功能清单

### 1️⃣ 核心安装能力

| 功能 | 说明 |
|------|------|
| **标准安装流程** | 图形化向导界面，选择安装目录 → 快捷方式 → 完成安装 |
| **静默安装支持** | 可通过命令行 `/SILENT` 或 `/VERYSILENT` 参数实现无人值守部署 |
| **自定义安装路径** | 默认 `%ProgramFiles%\DMF 48通道控制器`，支持手动更改 |
| **桌面快捷方式** | 可选：安装时创建桌面图标（默认勾选） |
| **开始菜单分组** | 自动创建「DMF 48通道控制器」程序组，含主程序和卸载入口 |

### 2️⃣ 兼容性保障

| 功能 | 说明 |
|------|------|
| **Windows 10/11** | 全面支持 Windows 10 1809+ 及 Windows 11 |
| **32/64 位兼容** | 单文件 x86 构建，兼容所有 Windows 架构 |
| **管理员权限** | 安装过程中自动请求管理员权限，确保写入 Program Files |
| **运行中检测** | 安装前自动检测并关闭正在运行的应用程序，避免文件占用 |

### 3️⃣ 卸载能力

| 功能 | 说明 |
|------|------|
| **控制面板卸载** | 在「设置 → 应用」中可找到并卸载 |
| **开始菜单卸载** | 通过开始菜单中的「卸载 DMF 48通道控制器」快捷方式卸载 |
| **残留清理** | 卸载时自动删除用户数据目录（`%APPDATA%` 和 `%LOCALAPPDATA%`） |
| **进程终止** | 卸载前自动终止正在运行的主程序进程 |

### 4️⃣ 安装后体验

| 功能 | 说明 |
|------|------|
| **安装完成自动启动** | 可选：安装完成后立即运行程序（默认勾选） |
| **版本信息嵌入** | EXE 文件属性中包含完整的版本号、公司名、版权信息 |
| **自定义图标** | 芯片风格应用图标，涵盖程序文件、快捷方式、安装程序本身 |

---

## 🚀 安装步骤

### 方法一：图形界面安装（推荐）

1. **下载安装包**

   从 [GitHub Releases](https://github.com/Cavalcdor/DMF_48Channel_Controller/releases) 页面下载最新版安装包：
   ```
   DMF_48Channel_Controller_Setup_v2.0.0_Windows_x86_CharlesWENG.exe
   ```

2. **运行安装程序**

   双击运行安装包，可能弹出 **Windows 保护** 提示，点击「更多信息」→「仍要运行」即可。

3. **跟随向导安装**

   ```
   ① 欢迎页面  →  ② 选择安装目录  →  ③ 选择快捷方式  →  ④ 准备安装  →  ⑤ 完成
   ```

   - **安装目录**：建议保持默认（`C:\Program Files\DMF 48通道控制器`）
   - **快捷方式**：勾选「创建桌面快捷方式」以便快速启动
   - **完成后启动**：勾选「启动 DMF 48通道控制器」即可在安装完成自动打开

4. **启动软件**

   安装完成后，可通过以下方式启动：
   - 桌面快捷方式：双击 `DMF 48通道控制器`
   - 开始菜单：`DMF 48通道控制器` → `DMF 48通道控制器`
   - 安装目录：`{安装路径}\DMF_48Channel_Controller.exe`

### 方法二：静默安装（IT 批量部署）

```batch
:: 静默安装（显示进度条，无需交互）
DMF_48Channel_Controller_Setup_v2.0.0_Windows_x86_CharlesWENG.exe /SILENT

:: 完全静默安装（后台静默完成）
DMF_48Channel_Controller_Setup_v2.0.0_Windows_x86_CharlesWENG.exe /VERYSILENT

:: 静默安装 + 指定目录 + 创建桌面图标
DMF_48Channel_Controller_Setup_v2.0.0_Windows_x86_CharlesWENG.exe /VERYSILENT /DIR="D:\Apps\DMF_Controller" /TASKS="desktopicon"
```

### 方法三：便携版（免安装直接运行）

如果您不想安装，也可以直接下载便携版：

1. 从 GitHub Releases 获取 `DMF_48Channel_Controller.exe`
2. 将文件复制到任意目录（如 U 盘）
3. 双击直接运行，无需安装

---

## 🗑️ 卸载方法

### 通过 Windows 设置

1. 打开「设置」→「应用」→「应用和功能」
2. 搜索「DMF 48通道控制器」
3. 点击「卸载」→ 确认

### 通过开始菜单

1. 打开「开始菜单」→「DMF 48通道控制器」
2. 点击「卸载 DMF 48通道控制器」
3. 确认卸载

> **注意**：卸载将自动删除所有用户配置文件和缓存数据。

---

## ⚙️ 系统要求

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| **操作系统** | Windows 10 (1809+) | Windows 11 |
| **处理器** | 1 GHz 双核 | 2 GHz 双核及以上 |
| **内存** | 512 MB | 2 GB 以上 |
| **硬盘空间** | 200 MB | 500 MB |
| **串口** | 1 个可用串口（控制器通讯用） | — |
| **显示器** | 1280 × 720 | 1920 × 1080 及以上 |
| **依赖运行时** | — | 无需安装 Python，已静态编译 |

---

## 🔧 高级：从源代码构建

如需自行构建安装包，请参阅 `build_app.py`：

```bash
# 安装构建依赖
pip install pyinstaller

# 完整构建（图标 + exe + 安装包）
python build_app.py

# 仅构建 exe（不生成安装包）
python build_app.py --exe-only

# 清理构建产物
python build_app.py --clean
```

构建要求：
- Python 3.12+
- PyInstaller 6.x
- Inno Setup 6（用于生成安装包，可选）
- 无需安装 Visual Studio（不包含 C 扩展编译）

---

## 📋 常见问题

### Q: Windows 提示"Windows protected your PC"？
A: 点击「More info」→「Run anyway」。这是因为安装包未做代码签名，属正常现象。

### Q: 安装后无法运行？
A: 请尝试：
1. 右键 → 「以管理员身份运行」
2. 检查是否被杀毒软件拦截
3. 重新安装最新版本

### Q: 如何确认版本号？
A: 在软件中点击「关于」菜单，或在 EXE 文件上右键 → 属性 → 详细信息查看。

### Q: 安装包体积为什么是 38MB？
A: 因为使用了 PyInstaller 将 Python 解释器 + PyQt5 库 + 所有依赖静态编译为单个独立 EXE 文件，无需用户安装 Python 环境。

---

<div align="center">

**Charles WENG** · [GitHub](https://github.com/Cavalcdor/DMF_48Channel_Controller) · © 2026 All Rights Reserved

</div>
