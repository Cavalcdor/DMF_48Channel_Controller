"""
DMF 48-通道控制器主应用程序
PyQt5 界面，整合串口通信、电极网格、寻路算法
"""

import sys
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QStatusBar, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from src import global_cfg
from src.serial_driver import SerialThread
from src.grid_widget import ElectrodeGrid
from src.path_algorithm import bfs_shortest_path, path_to_indices


class DMFControllerWindow(QMainWindow):
    """DMF 48-通道控制器主窗口。"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DMF 48通道控制器")
        self.setGeometry(100, 100, 1200, 800)

        # ============ 初始化模块 ============
        self.serial_thread = SerialThread()
        self.grid_widget = ElectrodeGrid()
        self.is_running = False
        self.current_droplet_index = 0  # 液滴在路径上的当前位置索引
        self.current_path = []  # 当前规划的路径
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.move_droplet_step)

        # ============ 连接串口信号 ============
        self.serial_thread.data_received.connect(self.on_serial_data)
        self.serial_thread.error.connect(self.on_serial_error)
        self.serial_thread.port_opened.connect(self.on_port_opened)

        # ============ 应用全局样式 ============
        self.apply_stylesheet()

        # ============ 创建 UI ============
        self.init_ui()

        # ============ 状态变量 ============
        self.serial_connected = False
        self.droplet_position = None

    def apply_stylesheet(self):
        """应用全局 QSS 样式表。"""
        stylesheet = """
        QMainWindow {
            background-color: #f5f5f5;
        }
        QGroupBox {
            color: #333333;
            background-color: #ffffff;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            padding-left: 10px;
            padding-right: 10px;
            padding-bottom: 10px;
            font-size: 11px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
            font-size: 12px;
            font-weight: bold;
            color: #1a1a1a;
        }
        QPushButton {
            border: none;
            border-radius: 5px;
            padding: 8px 12px;
            font-size: 11px;
            font-weight: bold;
            color: white;
            background-color: #5a7f94;
        }
        QPushButton:hover {
            background-color: #6a8fa4;
        }
        QPushButton:pressed {
            background-color: #4a6f84;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #999999;
        }
        QComboBox {
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            padding: 5px 8px;
            background-color: #ffffff;
            color: #333333;
            font-size: 10px;
        }
        QComboBox:focus {
            border: 2px solid #5a7f94;
        }
        QLabel {
            color: #333333;
            font-size: 10px;
        }
        """
        self.setStyleSheet(stylesheet)

    def init_ui(self):
        """初始化用户界面。"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background-color: #f5f5f5;")

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(15)

        # ============ 左侧控制面板 ============
        left_panel = QVBoxLayout()
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(12)

        # 串口控制组
        serial_group = QGroupBox("串口连接")
        serial_layout = QVBoxLayout()
        serial_layout.setContentsMargins(8, 8, 8, 8)
        serial_layout.setSpacing(8)

        serial_combo_layout = QHBoxLayout()
        serial_combo_layout.setSpacing(6)
        serial_combo_layout.addWidget(QLabel("端口："))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(120)
        serial_combo_layout.addWidget(self.port_combo)
        self.refresh_ports_btn = QPushButton("刷新")
        self.refresh_ports_btn.clicked.connect(self.refresh_serial_ports)
        serial_combo_layout.addWidget(self.refresh_ports_btn)
        serial_layout.addLayout(serial_combo_layout)

        self.connect_btn = QPushButton("连接")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_serial_connection)
        serial_layout.addWidget(self.connect_btn)

        self.serial_status_label = QLabel("状态：未连接")
        self.serial_status_label.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 10px;")
        serial_layout.addWidget(self.serial_status_label)

        serial_group.setLayout(serial_layout)
        left_panel.addWidget(serial_group)

        # 路径规划和运动控制组
        control_group = QGroupBox("路径控制")
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(8, 8, 8, 8)
        control_layout.setSpacing(8)

        # 运动参数
        param_layout = QHBoxLayout()
        param_layout.setSpacing(6)
        param_layout.addWidget(QLabel("步长延迟 (ms)："))
        self.delay_spinbox = QComboBox()
        self.delay_spinbox.addItems(["100", "200", "500", "1000"])
        self.delay_spinbox.setCurrentText("500")
        self.delay_spinbox.setMaximumWidth(80)
        param_layout.addWidget(self.delay_spinbox)
        param_layout.addStretch()
        control_layout.addLayout(param_layout)

        # 运动按钮
        self.run_path_btn = QPushButton("运行路径")
        self.run_path_btn.setStyleSheet("""
            QPushButton {
                background-color: #66bb6a;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7ac776;
            }
            QPushButton:pressed {
                background-color: #558b5a;
            }
        """)
        self.run_path_btn.clicked.connect(self.on_run_path)
        control_layout.addWidget(self.run_path_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef5350;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #f76464;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        control_group.setLayout(control_layout)
        left_panel.addWidget(control_group)

        # 网格操作组
        grid_control_group = QGroupBox("网格操作")
        grid_control_layout = QVBoxLayout()
        grid_control_layout.setContentsMargins(8, 8, 8, 8)
        grid_control_layout.setSpacing(8)

        self.reset_grid_btn = QPushButton("重置网格")
        self.reset_grid_btn.clicked.connect(self.on_reset_grid)
        grid_control_layout.addWidget(self.reset_grid_btn)

        clear_btns_layout = QHBoxLayout()
        clear_btns_layout.setSpacing(6)
        self.clear_starts_btn = QPushButton("清除起点")
        self.clear_starts_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_START))
        clear_btns_layout.addWidget(self.clear_starts_btn)

        self.clear_targets_btn = QPushButton("清除目标")
        self.clear_targets_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_TARGET))
        clear_btns_layout.addWidget(self.clear_targets_btn)

        self.clear_obstacles_btn = QPushButton("清除障碍物")
        self.clear_obstacles_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_OBSTACLE))
        clear_btns_layout.addWidget(self.clear_obstacles_btn)

        grid_control_layout.addLayout(clear_btns_layout)

        grid_control_group.setLayout(grid_control_layout)
        left_panel.addWidget(grid_control_group)

        # 状态信息
        info_group = QGroupBox("信息")
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(8)

        self.info_label = QLabel("就绪")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)

        self.path_info_label = QLabel("路径：无")
        self.path_info_label.setWordWrap(True)
        info_layout.addWidget(self.path_info_label)

        info_group.setLayout(info_layout)
        left_panel.addWidget(info_group)

        left_panel.addStretch()

        # ============ 右侧电极网格 ============
        main_layout.addLayout(left_panel, stretch=1)
        main_layout.addWidget(self.grid_widget, stretch=1)

        central_widget.setLayout(main_layout)

        # ============ 状态栏 ============
        self.statusBar().setStyleSheet("QStatusBar { background-color: #ffffff; color: #333333; border-top: 1px solid #d0d0d0; }")
        self.statusBar().showMessage("就绪")
        self.statusBar().setFont(QFont("Arial", 9))

        # ============ 初始化串口列表 ============
        self.refresh_serial_ports()

    def refresh_serial_ports(self):
        """刷新可用的串口列表。"""
        self.port_combo.clear()
        ports = SerialThread.scan_ports()
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("未发现串口")

    def toggle_serial_connection(self):
        """切换串口连接状态。"""
        if self.connect_btn.isChecked():
            port = self.port_combo.currentText()
            if port == "未发现串口":
                QMessageBox.warning(self, "错误", "未发现串口")
                self.connect_btn.setChecked(False)
                return
            self.serial_thread.open_port(port)
        else:
            self.serial_thread.close_port()
            self.serial_connected = False
            self.serial_status_label.setText("状态：未连接")
            self.serial_status_label.setStyleSheet("color: red;")
            self.statusBar().showMessage("串口已断开连接")

    @pyqtSlot(bool)
    def on_port_opened(self, success):
        """串口打开结果回调。"""
        if success:
            self.serial_connected = True
            self.serial_status_label.setText(f"状态：已连接 ({self.port_combo.currentText()})")
            self.serial_status_label.setStyleSheet("color: green;")
            self.statusBar().showMessage(f"串口已连接：{self.port_combo.currentText()}")
            self.port_combo.setEnabled(False)
            self.refresh_ports_btn.setEnabled(False)
        else:
            self.serial_connected = False
            self.serial_status_label.setText("状态：连接失败")
            self.serial_status_label.setStyleSheet("color: orange;")
            self.statusBar().showMessage("串口连接失败")
            self.connect_btn.setChecked(False)

    @pyqtSlot(str)
    def on_serial_data(self, data):
        """处理串口接收数据。"""
        self.info_label.setText(f"接收：{data}")

    @pyqtSlot(str)
    def on_serial_error(self, error_msg):
        """处理串口错误。"""
        self.statusBar().showMessage(f"错误：{error_msg}")
        QMessageBox.critical(self, "串口错误", error_msg)

    def on_run_path(self):
        """运行路径寻路和液滴移动。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "警告", "串口未连接")
            return

        # 获取起点、目标、障碍物
        start_points = self.grid_widget.get_start_points()
        target_points = self.grid_widget.get_target_points()
        obstacles = set(self.grid_widget.get_obstacle_points())

        if not start_points:
            QMessageBox.warning(self, "警告", "未设置起点")
            return

        if not target_points:
            QMessageBox.warning(self, "警告", "未设置目标")
            return

        # 简单起见，使用第一个起点和第一个目标
        start = start_points[0]
        target = target_points[0]

        # BFS 寻路
        path = bfs_shortest_path(start, target, obstacles)

        if not path:
            QMessageBox.warning(self, "无路径", f"从 {start} 到 {target} 无可达路径")
            return

        # 初始化液滴移动
        self.current_path = path
        self.current_droplet_index = 0
        self.is_running = True

        self.run_path_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.grid_widget.setEnabled(False)

        # 显示路径信息
        indices = path_to_indices(path)
        self.path_info_label.setText(f"路径：{len(path)} 步，索引：{indices[:5]}...")
        self.statusBar().showMessage(f"正在执行路径：{len(path)} 步")

        # 启动液滴移动定时器
        delay_ms = int(self.delay_spinbox.currentText())
        self.move_timer.start(delay_ms)

    def on_stop(self):
        """停止液滴移动。"""
        self.is_running = False
        self.move_timer.stop()
        self.run_path_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.grid_widget.setEnabled(True)
        self.statusBar().showMessage("路径执行已停止")
        self.info_label.setText("已停止")

    def move_droplet_step(self):
        """液滴单步移动。"""
        if not self.is_running or not self.current_path:
            self.move_timer.stop()
            return

        if self.current_droplet_index >= len(self.current_path):
            # 路径完成
            self.move_timer.stop()
            self.is_running = False
            self.run_path_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.grid_widget.setEnabled(True)
            self.statusBar().showMessage("路径执行完成")
            self.info_label.setText("路径已完成")
            return

        # 获取当前步骤的电极
        current_pos = self.current_path[self.current_droplet_index]
        current_index = ElectrodeGrid.coord_to_index(current_pos[0], current_pos[1])

        # 关闭前一个位置的电极
        if self.current_droplet_index > 0:
            prev_pos = self.current_path[self.current_droplet_index - 1]
            prev_index = ElectrodeGrid.coord_to_index(prev_pos[0], prev_pos[1])
            self.serial_thread.send_cmd(f"OFF,{prev_index}")

        # 打开当前位置的电极
        self.serial_thread.send_cmd(f"ON,{current_index}")

        # 更新状态
        self.info_label.setText(f"步骤 {self.current_droplet_index + 1}/{len(self.current_path)}：({current_pos[0]}, {current_pos[1]})")
        self.statusBar().showMessage(f"移动到 ({current_pos[0]}, {current_pos[1]})，索引：{current_index}")

        self.current_droplet_index += 1

    def on_reset_grid(self):
        """重置网格所有单元格为 Idle。"""
        self.grid_widget.reset_grid()
        self.statusBar().showMessage("网格已重置")

    def on_clear_state(self, state):
        """清除指定状态的所有单元格。"""
        self.grid_widget.clear_state(state)
        state_name = ElectrodeGrid.STATE_NAMES[state]
        self.statusBar().showMessage(f"已清除所有 {state_name} 单元格")

    def closeEvent(self, event):
        """窗口关闭事件。"""
        if self.serial_connected:
            self.serial_thread.close_port()
        if self.move_timer.isActive():
            self.move_timer.stop()
        event.accept()


def main():
    """主函数。"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    window = DMFControllerWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
