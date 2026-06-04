from PyQt5.QtCore import QThread, pyqtSignal
import serial
import serial.tools.list_ports
import time
from . import global_cfg


class SerialThread(QThread):
    """基于 QThread 的异步串口类。

    Signals:
    - data_received(str): 接收到的 Arduino 文本（已去除换行）
    - error(str): 错误信息
    - port_opened(bool): 打开串口成功发 True，失败发 False

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ser = None
        self._running = False
        self._port = None

    @staticmethod
    def scan_ports():
        """扫描本机串口，返回设备名列表（例如 ['COM1', 'COM3']）。"""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def is_open(self):
        return self._ser is not None and getattr(self._ser, 'is_open', False)

    def open_port(self, port):
        """打开指定串口并启动接收线程（使用 global_cfg 中的波特率和超时）。"""
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
        """关闭串口并停止线程。"""
        self._running = False
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

    def send_cmd(self, cmd):
        """发送指令，自动添加换行符（\n）。返回 True/False 表示是否发送成功。"""
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

    def run(self):
        """线程主循环：实时读取串口返回数据并通过信号发出。"""
        while self._running:
            try:
                if self._ser and getattr(self._ser, 'is_open', False):
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
