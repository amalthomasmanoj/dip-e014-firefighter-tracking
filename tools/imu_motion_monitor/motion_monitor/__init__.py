"""独立的大腿 IMU 运动方向 / 低姿态监测原型。
Standalone thigh-IMU motion-direction and low-posture monitor prototype.

本包只依赖 Python 标准库，不导入 DIP 根目录的任何模块。
This package uses only the Python standard library and imports nothing from the DIP root.
"""

from .core import Monitor, MonitorConfig, Status

__all__ = ["Monitor", "MonitorConfig", "Status"]
