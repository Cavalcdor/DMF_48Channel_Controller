"""
全局配置文件
DMF 48通道控制器配置参数
"""

# ============ 电极阵列配置 ============
# 电极网格的行数和列数
ELECTRODE_ROWS = 6  # 行数
ELECTRODE_COLS = 8  # 列数
TOTAL_ELECTRODES = 48  # 总电极数

# ============ 串口通信配置 ============
# 串口参数
SERIAL_BAUDRATE = 115200  # 波特率
SERIAL_TIMEOUT = 1  # 串口超时时间（秒）

# ============ 其他配置 ============
# 可根据需要添加更多配置参数
DEFAULT_VOLTAGE = 100  # 默认电压值
PWM_FREQUENCY = 1000  # PWM频率（Hz）
