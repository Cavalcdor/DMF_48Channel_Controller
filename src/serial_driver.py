from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import serial
import serial.tools.list_ports
import time
from . import global_cfg

# 虚拟串口名称
VIRTUAL_PORT_NAME = "Virtual (模拟)"


class SerialThread(QThread):
    """基于 QThread 的异步串口类，支持虚拟模拟模式。

    Signals:
    - data_received(str): 接收到的 Arduino 文本（已去除换行）
    - error(str): 错误信息
    - port_opened(bool): 打开串口成功发 True，失败发 False

    虚拟模式（端口名为 VIRTUAL_PORT_NAME）无需真实串口，
    send_cmd 会自动返回模拟响应，方便无硬件时测试。

    使用示例：
        thread = SerialThread()
        thread.data_received.connect(handle_received)
        thread.error.connect(handle_error)
        thread.open_port('COM3')
        thread.send_on(1)
        thread.send_allon()
        thread.close_port()
    """

    data_received = pyqtSignal(str)
    error = pyqtSignal(str)
    port_opened = pyqtSignal(bool)

    # 模拟状态表：记录每个通道 ON/OFF
    # （class-level 仅作类型标注，实际在 __init__ 中初始化为实例变量）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ser = None
        self._running = False
        self._port = None
        self._virtual = False          # 是否虚拟模式
        self._virtual_channels = {}    # 模拟状态表

    @staticmethod
    def scan_ports():
        """扫描本机串口，返回设备名列表（例如 ['COM1', 'COM3']）。"""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def is_open(self):
        if self._virtual:
            return True
        return self._ser is not None and getattr(self._ser, 'is_open', False)

    def open_port(self, port):
        """打开指定串口并启动接收线程（使用 global_cfg 中的波特率和超时）。

        若 port 为 VIRTUAL_PORT_NAME，则进入虚拟模拟模式，无需真实串口。
        """
        # 虚拟模式
        if port == VIRTUAL_PORT_NAME:
            self._virtual = True
            self._port = port
            self._running = True
            self._virtual_channels.clear()
            if not self.isRunning():
                self.start()
            self.port_opened.emit(True)
            # 发送欢迎消息
            self._virtual_delayed_reply("Virtual Serial Ready | 虚拟串口已就绪")
            return

        try:
            if self._ser and getattr(self._ser, 'is_open', False):
                # 先关闭已有串口
                self.close_port()

            self._ser = serial.Serial(port=port,
                                      baudrate=global_cfg.SERIAL_BAUDRATE,
                                      timeout=global_cfg.SERIAL_TIMEOUT)
            self._port = port
            self._running = True
            if not self.isRunning():
                self.start()
            self.port_opened.emit(True)
        except Exception as e:
            self._ser = None
            self._running = False
            self.port_opened.emit(False)
            self.error.emit(str(e))

    def close_port(self):
        """关闭串口（或退出虚拟模式）并停止线程。"""
        self._running = False
        if self._virtual:
            self._virtual = False
            self._port = None
            if self.isRunning():
                self.wait(500)
            return
        try:
            if self._ser:
                try:
                    if getattr(self._ser, 'is_open', False):
                        self._ser.flush()
                        self._ser.close()
                except Exception as e:
                    self.error.emit(str(e))
                self._ser = None
        finally:
            # 等待线程退出（超时 500ms）
            if self.isRunning():
                self.wait(500)

    def _virtual_delayed_reply(self, text, delay_ms=80):
        """虚拟模式下延迟发送回复（模拟串口响应时间）。"""
        if not self._virtual:
            return
        QTimer.singleShot(delay_ms, lambda: (
            self.data_received.emit(text) if self._virtual else None))

    def _virtual_handle_cmd(self, cmd):
        """处理虚拟模式下的指令，生成模拟回复。"""
        cmd = cmd.strip()
        if not cmd:
            return

        parts = cmd.upper().split(',')
        base = parts[0]

        if base == "ON" and len(parts) == 2:
            try:
                ch = int(parts[1])
                self._virtual_channels[ch] = True
                self._virtual_delayed_reply(f"ON,{ch} OK")
            except ValueError:
                self._virtual_delayed_reply(f"ERR: invalid channel {parts[1]}")
        elif base == "OFF" and len(parts) == 2:
            try:
                ch = int(parts[1])
                self._virtual_channels.pop(ch, None)
                self._virtual_delayed_reply(f"OFF,{ch} OK")
            except ValueError:
                self._virtual_delayed_reply(f"ERR: invalid channel {parts[1]}")
        elif base == "ALLON":
            for i in range(48):
                self._virtual_channels[i] = True
            self._virtual_delayed_reply("ALLON OK")
        elif base == "ALLOFF":
            self._virtual_channels.clear()
            self._virtual_delayed_reply("ALLOFF OK")
        elif base == "TEST":
            self._virtual_delayed_reply("TEST OK, System Ready")
            self._virtual_delayed_reply("All channels functional (simulated)", delay_ms=160)
        elif base == "LIST":
            on_list = sorted(self._virtual_channels.keys())
            if on_list:
                self._virtual_delayed_reply(
                    f"Channels ON: {','.join(str(c) for c in on_list)}")
            else:
                self._virtual_delayed_reply("All channels OFF")
            self._virtual_delayed_reply(f"Total ON: {len(on_list)}")
        elif base == "HELP":
            self._virtual_delayed_reply("=== Virtual Serial Help ===")
            self._virtual_delayed_reply(
                "ON,ch / OFF,ch / ALLON / ALLOFF / TEST / LIST / HELP")
        else:
            self._virtual_delayed_reply(f"ECHO: {cmd}")

    def send_cmd(self, cmd):
        """发送指令，自动添加换行符（\n）。返回 True/False 表示是否发送成功。

        虚拟模式下不操作串口，直接模拟回复。
        """
        # 虚拟模式
        if self._virtual:
            if not cmd.endswith('\n'):
                cmd = cmd + '\n'
            self._virtual_handle_cmd(cmd)
            return True

        if not self._ser or not getattr(self._ser, 'is_open', False):
            self.error.emit('Serial port not open')
            return False
        if not cmd.endswith('\n'):
            cmd = cmd + '\n'
        try:
            self._ser.write(cmd.encode('utf-8'))
            return True
        except Exception as e:
            self.error.emit(str(e))
            return False

    # 常用指令快捷方法
    def send_on(self, n):
        return self.send_cmd(f"ON,{n}")

    def send_off(self, n):
        return self.send_cmd(f"OFF,{n}")

    def send_allon(self):
        return self.send_cmd("ALLON")

    def send_alloff(self):
        return self.send_cmd("ALLOFF")

    def run(self):
        """线程主循环：实时读取串口返回数据并通过信号发出。

        虚拟模式下无串口可读，仅维持线程存活（响应由 QTimer 异步发送）。
        """
        while self._running:
            try:
                if self._virtual:
                    # 虚拟模式：无串口可读，低功耗睡眠
                    self.msleep(200)
                elif self._ser and getattr(self._ser, 'is_open', False):
                    # 优先按行读取（Arduino 一般以换行结束数据）
                    try:
                        line = self._ser.readline()
                    except Exception as e:
                        self.error.emit(str(e))
                        line = b''

                    if line:
                        try:
                            text = line.decode('utf-8', errors='replace').rstrip('\r\n')
                        except Exception:
                            text = str(line)
                        self.data_received.emit(text)
                    else:
                        # 无数据时休眠，降低 CPU 占用
                        self.msleep(10)
                else:
                    self.msleep(100)
            except Exception as e:
                self.error.emit(str(e))
                self.msleep(100)
