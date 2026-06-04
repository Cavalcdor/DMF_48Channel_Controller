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
from PyQt5.QtGui import QFont

from src import global_cfg
from src.serial_driver import SerialThread
from src.grid_widget import ElectrodeGrid
from src.path_algorithm import bfs_shortest_path, path_to_indices


class DMFControllerWindow(QMainWindow):
    """DMF 48-通道控制器主窗口。"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DMF 48-Channel Controller")
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

        # ============ 创建 UI ============
        self.init_ui()

        # ============ 状态变量 ============
        self.serial_connected = False
        self.droplet_position = None

    def init_ui(self):
        """初始化用户界面。"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # ============ 左侧控制面板 ============
        left_panel = QVBoxLayout()

        # 串口控制组
        serial_group = QGroupBox("Serial Connection")
        serial_layout = QVBoxLayout()

        serial_combo_layout = QHBoxLayout()
        serial_combo_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(120)
        serial_combo_layout.addWidget(self.port_combo)
        self.refresh_ports_btn = QPushButton("Refresh")
        self.refresh_ports_btn.clicked.connect(self.refresh_serial_ports)
        serial_combo_layout.addWidget(self.refresh_ports_btn)
        serial_layout.addLayout(serial_combo_layout)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_serial_connection)
        serial_layout.addWidget(self.connect_btn)

        self.serial_status_label = QLabel("Status: Disconnected")
        self.serial_status_label.setStyleSheet("color: red;")
        serial_layout.addWidget(self.serial_status_label)

        serial_group.setLayout(serial_layout)
        left_panel.addWidget(serial_group)

        # 路径规划和运动控制组
        control_group = QGroupBox("Path Control")
        control_layout = QVBoxLayout()

        # 运动参数
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("Step Delay (ms):"))
        self.delay_spinbox = QComboBox()
        self.delay_spinbox.addItems(["100", "200", "500", "1000"])
        self.delay_spinbox.setCurrentText("500")
        self.delay_spinbox.setMaximumWidth(80)
        param_layout.addWidget(self.delay_spinbox)
        param_layout.addStretch()
        control_layout.addLayout(param_layout)

        # 运动按钮
        self.run_path_btn = QPushButton("Run Path")
        self.run_path_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.run_path_btn.clicked.connect(self.on_run_path)
        control_layout.addWidget(self.run_path_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)

        control_group.setLayout(control_layout)
        left_panel.addWidget(control_group)

        # 网格操作组
        grid_control_group = QGroupBox("Grid Operations")
        grid_control_layout = QVBoxLayout()

        self.reset_grid_btn = QPushButton("Reset Grid")
        self.reset_grid_btn.clicked.connect(self.on_reset_grid)
        grid_control_layout.addWidget(self.reset_grid_btn)

        clear_btns_layout = QHBoxLayout()
        self.clear_starts_btn = QPushButton("Clear Starts")
        self.clear_starts_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_START))
        clear_btns_layout.addWidget(self.clear_starts_btn)

        self.clear_targets_btn = QPushButton("Clear Targets")
        self.clear_targets_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_TARGET))
        clear_btns_layout.addWidget(self.clear_targets_btn)

        self.clear_obstacles_btn = QPushButton("Clear Obstacles")
        self.clear_obstacles_btn.clicked.connect(lambda: self.on_clear_state(ElectrodeGrid.STATE_OBSTACLE))
        clear_btns_layout.addWidget(self.clear_obstacles_btn)

        grid_control_layout.addLayout(clear_btns_layout)

        grid_control_group.setLayout(grid_control_layout)
        left_panel.addWidget(grid_control_group)

        # 状态信息
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout()

        self.info_label = QLabel("Ready")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)

        self.path_info_label = QLabel("Path: None")
        self.path_info_label.setWordWrap(True)
        info_layout.addWidget(self.path_info_label)

        info_group.setLayout(info_layout)
        left_panel.addWidget(info_group)

        left_panel.addStretch()

        # ============ 右侧电极网格 ============
        main_layout.addLayout(left_panel, stretch=1)
        main_layout.addWidget(self.grid_widget, stretch=2)

        central_widget.setLayout(main_layout)

        # ============ 状态栏 ============
        self.statusBar().showMessage("Idle")

        # ============ 初始化串口列表 ============
        self.refresh_serial_ports()

    def refresh_serial_ports(self):
        """刷新可用的串口列表。"""
        self.port_combo.clear()
        ports = SerialThread.scan_ports()
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("No ports found")

    def toggle_serial_connection(self):
        """切换串口连接状态。"""
        if self.connect_btn.isChecked():
            port = self.port_combo.currentText()
            if port == "No ports found":
                QMessageBox.warning(self, "Error", "No serial ports found")
                self.connect_btn.setChecked(False)
                return
            self.serial_thread.open_port(port)
        else:
            self.serial_thread.close_port()
            self.serial_connected = False
            self.serial_status_label.setText("Status: Disconnected")
            self.serial_status_label.setStyleSheet("color: red;")
            self.statusBar().showMessage("Serial disconnected")

    @pyqtSlot(bool)
    def on_port_opened(self, success):
        """串口打开结果回调。"""
        if success:
            self.serial_connected = True
            self.serial_status_label.setText(f"Status: Connected ({self.port_combo.currentText()})")
            self.serial_status_label.setStyleSheet("color: green;")
            self.statusBar().showMessage(f"Serial connected: {self.port_combo.currentText()}")
            self.port_combo.setEnabled(False)
            self.refresh_ports_btn.setEnabled(False)
        else:
            self.serial_connected = False
            self.serial_status_label.setText("Status: Connection Failed")
            self.serial_status_label.setStyleSheet("color: orange;")
            self.statusBar().showMessage("Serial connection failed")
            self.connect_btn.setChecked(False)

    @pyqtSlot(str)
    def on_serial_data(self, data):
        """处理串口接收数据。"""
        self.info_label.setText(f"Received: {data}")

    @pyqtSlot(str)
    def on_serial_error(self, error_msg):
        """处理串口错误。"""
        self.statusBar().showMessage(f"Error: {error_msg}")
        QMessageBox.critical(self, "Serial Error", error_msg)

    def on_run_path(self):
        """运行路径寻路和液滴移动。"""
        if not self.serial_connected:
            QMessageBox.warning(self, "Warning", "Serial port not connected")
            return

        # 获取起点、目标、障碍物
        start_points = self.grid_widget.get_start_points()
        target_points = self.grid_widget.get_target_points()
        obstacles = set(self.grid_widget.get_obstacle_points())

        if not start_points:
            QMessageBox.warning(self, "Warning", "No start point set")
            return

        if not target_points:
            QMessageBox.warning(self, "Warning", "No target point set")
            return

        # 简单起见，使用第一个起点和第一个目标
        start = start_points[0]
        target = target_points[0]

        # BFS 寻路
        path = bfs_shortest_path(start, target, obstacles)

        if not path:
            QMessageBox.warning(self, "No Path", f"No path found from {start} to {target}")
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
        self.path_info_label.setText(f"Path: {len(path)} steps, Indices: {indices[:5]}...")
        self.statusBar().showMessage(f"Running path: {len(path)} steps")

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
        self.statusBar().showMessage("Path execution stopped")
        self.info_label.setText("Stopped")

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
            self.statusBar().showMessage("Path execution complete")
            self.info_label.setText("Path completed")
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
        self.info_label.setText(f"Step {self.current_droplet_index + 1}/{len(self.current_path)}: ({current_pos[0]}, {current_pos[1]})")
        self.statusBar().showMessage(f"Moving to ({current_pos[0]}, {current_pos[1]}), Index: {current_index}")

        self.current_droplet_index += 1

    def on_reset_grid(self):
        """重置网格所有单元格为 Idle。"""
        self.grid_widget.reset_grid()
        self.statusBar().showMessage("Grid reset")

    def on_clear_state(self, state):
        """清除指定状态的所有单元格。"""
        self.grid_widget.clear_state(state)
        state_name = ElectrodeGrid.STATE_NAMES[state]
        self.statusBar().showMessage(f"Cleared all {state_name} cells")

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
