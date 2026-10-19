"""可选 Tkinter 仪表盘：方向箭头 + 低姿态状态。
Optional Tkinter dashboard: direction arrow plus low-posture state.

运行 / Run:
    python -m motion_monitor.dashboard --port 9000
    python -m motion_monitor.dashboard --port 9100   # with demo_feed

方向箭头以启动时的朝向为 0°，不是绝对罗盘；正角度表示左转（绕 +z 逆时针）。
The arrow uses the start-up heading as 0 degrees, not an absolute compass; positive is a left
turn (counter-clockwise about +z).
"""
from __future__ import annotations

import argparse
import json
import math
import socket
import time
import tkinter as tk
from tkinter import messagebox

from .core import Monitor, MonitorConfig, Status
from .protocol import parse_imu_packet

COLORS = {
    "WARMUP": "#3478c7",
    "UPRIGHT": "#1b8a4b",
    "LOW_CHECKING": "#c58a00",
    "LOW_MOVING": "#d97706",
    "LOW_STILL": "#c62828",
    "NO_DATA": "#6b7280",
}


class Dashboard:
    def __init__(self, root: tk.Tk, args: argparse.Namespace, config: MonitorConfig):
        self.root = root
        self.args = args
        self.monitor = Monitor(config)
        self.start: float | None = None
        self.last_status: Status = self.monitor.tick(time.monotonic())
        self.counts = {"valid": 0, "invalid": 0, "foreign": 0}
        self.peer: tuple[str, int] | None = None

        root.title("Motion Monitor — direction / low posture")
        root.geometry("560x640")
        root.minsize(480, 560)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.canvas = tk.Canvas(root, width=520, height=420, background="#0f172a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        self.state_label = tk.Label(root, text="Waiting for data", font=("Segoe UI", 20, "bold"),
                                    fg="#6b7280", bg="#f3f4f6", pady=8)
        self.state_label.pack(fill="x", padx=12, pady=(8, 0))
        self.detail_label = tk.Label(root, text="", font=("Consolas", 11), justify="left",
                                     anchor="w", bg="#f3f4f6")
        self.detail_label.pack(fill="x", padx=12, pady=(4, 10))

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind((args.bind, args.port))
        except OSError as error:
            messagebox.showerror("UDP bind failed", f"Cannot bind {args.bind}:{args.port}\n{error}")
            root.destroy()
            return
        self.sock.setblocking(False)
        self.root.after(20, self.poll)

    def close(self) -> None:
        try:
            self.sock.close()
        finally:
            self.root.destroy()

    def poll(self) -> None:
        now = time.monotonic()
        for _ in range(200):
            try:
                raw, sender = self.sock.recvfrom(65535)
            except BlockingIOError:
                break
            except OSError:
                break
            if raw.startswith(b"DIP_PING "):
                token = raw[9:]
                if len(token) == 16 and all(c in b"0123456789abcdef" for c in token):
                    try:
                        self.sock.sendto(b"DIP_ACK " + token, sender)
                    except OSError:
                        pass
                continue
            if self.peer is not None and sender != self.peer:
                self.counts["foreign"] += 1
                continue
            try:
                packet = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeError, OverflowError):
                self.counts["invalid"] += 1
                continue
            parsed = parse_imu_packet(packet)
            if parsed is None:
                self.counts["invalid"] += 1
                continue
            if self.peer is None:
                self.peer = sender
            if self.start is None:
                self.start = now
            timestamp_us, sequence, accel, gyro = parsed
            self.last_status = self.monitor.ingest(
                timestamp_us / 1e6, accel, gyro, sequence=sequence, host_s=now
            )
            self.counts["valid"] += 1
        if self.last_status.state != "NO_DATA":
            self.last_status = self.monitor.tick(now)
        self.redraw()
        if self.args.duration and self.start is not None and now - self.start >= self.args.duration:
            self.state_label.config(text="Recording window complete — close the window to exit")
            return
        self.root.after(20, self.poll)

    def redraw(self) -> None:
        status = self.last_status
        self.canvas.delete("all")
        width = max(360, self.canvas.winfo_width())
        height = max(360, self.canvas.winfo_height())
        cx, cy = width / 2.0, height / 2.0 + 6
        radius = min(width, height) * 0.36
        color = COLORS.get(status.state, "#6b7280")
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                outline="#334155", width=2)
        for angle, label in ((0, "0° start"), (90, "90° left"), (180, "180°"), (270, "90° right")):
            rad = math.radians(angle)
            x = cx - (radius + 18) * math.sin(rad)
            y = cy - (radius + 18) * math.cos(rad)
            self.canvas.create_text(x, y, text=label, fill="#94a3b8", font=("Segoe UI", 9))
            self.canvas.create_line(cx, cy, cx - radius * math.sin(rad), cy - radius * math.cos(rad),
                                    fill="#1e293b", width=1, dash=(2, 4))
        self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=color, outline="")
        if status.direction_deg is not None:
            rad = math.radians(status.direction_deg)
            ex = cx - radius * 0.82 * math.sin(rad)
            ey = cy - radius * 0.82 * math.cos(rad)
            self.canvas.create_line(cx, cy, ex, ey, fill=color, width=6, arrow=tk.LAST,
                                    arrowshape=(16, 20, 7))
            self.canvas.create_text(cx, cy - radius - 42,
                                    text=f"direction {status.direction_deg:+.1f}° (relative)",
                                    fill="#e2e8f0", font=("Segoe UI", 12, "bold"))
        else:
            message = "direction unavailable in low posture" if status.low_posture else "direction: waiting for movement"
            self.canvas.create_text(cx, cy - radius - 42, text=message,
                                    fill="#94a3b8", font=("Segoe UI", 11))
        thigh = "--" if status.posture_deg is None else f"{status.posture_deg:.1f}°"
        self.canvas.create_text(cx, cy + radius + 24, text=f"thigh tilt {thigh}",
                                fill="#cbd5e1", font=("Segoe UI", 11))
        self.state_label.config(text=f"{status.state} — {status.label}", fg=color)
        self.detail_label.config(text=(
            f"t={status.t_s:7.1f}s   motion score={status.motion_score:4.2f}   "
            f"still={status.immobile_s:4.1f}s   low={status.low_posture}\n"
            f"gyro={status.gyro_rate_radps:5.3f} rad/s   accel dyn={status.accel_dynamic_mps2:5.2f} m/s²   "
            f"bias={status.bias_quality}\n"
            f"reason={status.reason}   samples={status.samples}   rx={self.counts['valid']} invalid={self.counts['invalid']}"
        ))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tkinter dashboard for motion direction and low-posture status."
    )
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--low-enter-deg", type=float, default=60.0)
    parser.add_argument("--low-exit-deg", type=float, default=50.0)
    parser.add_argument("--immobile-s", type=float, default=5.0)
    parser.add_argument("--motion-gyro", type=float, default=0.12)
    parser.add_argument("--motion-accel", type=float, default=0.35)
    parser.add_argument("--warmup-s", type=float, default=2.0)
    parser.add_argument("--check", action="store_true", help="validate imports and exit without opening a window")
    args = parser.parse_args()
    config = MonitorConfig(
        low_enter_deg=args.low_enter_deg,
        low_exit_deg=args.low_exit_deg,
        immobile_s=args.immobile_s,
        motion_gyro_radps=args.motion_gyro,
        motion_accel_mps2=args.motion_accel,
        warmup_s=args.warmup_s,
    )
    if args.check:
        print("dashboard imports OK")
        return 0
    try:
        root = tk.Tk()
    except tk.TclError as error:
        parser.exit(1, f"Cannot open a Tk window: {error}\nUse live.py for a terminal-only display.\n")
    Dashboard(root, args, config)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
