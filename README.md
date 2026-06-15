# DMF 48通道数字微流控控制器上位机

<div align="center">

**商业级微流控液滴操控可视化控制平台**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15%2B-green)](https://pypi.org/project/PyQt5/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Download](https://img.shields.io/badge/Download-Installer-brightgreen)](https://github.com/Cavalcdor/DMF_48Channel_Controller/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-brightgreen)](https://www.microsoft.com/windows)

**📥 下载安装包**：前往 [GitHub Releases](https://github.com/Cavalcdor/DMF_48Channel_Controller/releases) 获取最新版安装包  
**📖 安装指南**：详见 [INSTALL.md](INSTALL.md)

</div>

---

## 📖 项目简介

基于 Python + PyQt5 构建的 **DMF（数字微流控）48通道控制器上位机**，提供电极网格可视化、A\* 智能寻路、多液滴并行路径规划与串口实时控制等核心功能，面向微流控液滴操控实验场景。

## ✨ 功能特性

### 🖥️ 现代化 UI
- **深色顶栏 + 三栏布局**：左侧操作面板、中央网格视图、右侧状态面板
- **配色系统**：统一色板、圆角控件、柔和的交互反馈
- **实时状态指示**：顶栏显示串口连接状态与运行状态

### 🔌 串口通讯
- 自动扫描本机串口，连接状态实时监控
- 支持协议：`ON,ch` / `OFF,ch` / `ALLON` / `ALLOFF` / `TEST` / `LIST` / `HELP`
- 快捷指令 + 自定义指令输入

### 🧩 可视化电极网格
- 自定义行列数（2×2 至 16×16），默认 6×8（48 电极）
- 四种状态：空闲 / 起点(蓝) / 目标(橙) / 障碍物(深灰)
- 交互模式：起点/终点模式 ↔ 障碍物模式
- 智能点击：空闲格自动设为起点或目标，已设格点击取消
- 圆角渲染 + 动态缩放

### 🧠 路径规划
- **A\* 算法**（曼哈顿距离启发式）四方向寻路
- **多液滴并行规划**（最多 8 个液滴），贪心排序避免路径冲突
- 失败诊断：区分障碍物阻挡、其他液滴占用、起点等于终点等场景
- **规划路径**：仅计算预览，不下发串口
- **运行路径**：计算后自动串口步进执行

### 💧 液滴管理
- 支持 1～8 个液滴，独立编号与路径颜色标识
- 导航切换：◀上一个 / 下一个▶ / ⏹回到液滴1
- 清除操作：✕清除当前（单个）/ ✕清除所有（全部）
- 新建/重置网格自动回退到液滴 1

### ⚡ 路径执行
- 可配置步长延迟（100 / 200 / 500 / 1000 ms）
- 定时器驱动逐级开关电极（ON 当前步、OFF 上一步）
- 停止按钮中断全部继电器

### 📊 信息面板
- 右侧图例 + 路径规划结果详情
- 液滴配对状态总览

## 🛠️ 技术架构

```
DMF_48Channel_Controller/
├── main.py                  # 主窗口：UI 布局、信号/槽、路径执行
├── requirements.txt         # 依赖清单
├── README.md
├── LICENSE
├── assets/
│   └── style.qss            # QSS 样式表（未使用，样式内联于 main.py）
└── src/
    ├── global_cfg.py        # 全局配置（行列数、串口参数）
    ├── grid_widget.py       # 电极网格组件（QWidget/paintEvent/交互）
    ├── path_algorithm.py    # A* 寻路 + 多液滴规划 + 冲突诊断
    └── serial_driver.py     # 串口驱动（QThread + 异步接收）
```

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动
python main.py
```

## 🎮 使用流程

```
连接串口 → 配置网格 → 设置起点/终点 → 设置障碍物 → 规划路径 → 运行路径
```

1. **连接串口** — 下拉选择端口，点击「连接」
2. **配置网格** — 调整行/列数，点击「新建网格」
3. **设置液滴** — 切换液滴编号，在网格上点击设置起点（蓝）和终点（橙）
4. **设置障碍物** — 切换到障碍物模式，标记不可通行电极
5. **规划路径** — 点击「规划路径」预览路径
6. **运行路径** — 确认无误后点击「运行路径」自动执行

### 补充说明

- 新建/重置网格后自动回到液滴 1，无需手动切换
- 调整网格大小时行列参数会同步到全局配置，确保寻路和索引映射正确
- 「清除障碍物」只清黑色格子；「清除当前」只清当前液滴的蓝/橙格；「清除所有」清全部液滴配置

## 📄 License

[MIT](LICENSE)