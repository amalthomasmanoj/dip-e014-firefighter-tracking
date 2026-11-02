from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.error
import urllib.request
import webbrowser

import certifi


APP_NAME = "E014 Firefighter Tracking"
QUICK_TUNNEL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _app_support_dir() -> Path:
    path = Path.home() / "Library" / "Application Support" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _log_dir() -> Path:
    path = Path.home() / "Library" / "Logs" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _bundled_ui_dist() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[1]))
    bundled = bundle_root / "ui_dist"
    if bundled.is_dir():
        return bundled
    return Path(__file__).parents[1] / "ui" / "web" / "dist"


def _child_command(*arguments: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, str(Path(__file__).resolve()), *arguments]


def _available_tcp_port(preferred: int = 8000) -> int:
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", candidate))
            if candidate == 0:
                return int(probe.getsockname()[1])
            return candidate
    raise RuntimeError("Unable to allocate a local server port")


def _lan_address() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def _run_backend_child(source: str, port: int, ui_dist: Path) -> None:
    os.environ["E014_SOURCE"] = source
    os.environ["E014_UI_DIST"] = str(ui_dist)
    import uvicorn

    from backend.api.app import create_app
    from backend.config.source import SourceMode

    uvicorn.run(
        create_app(source_mode=SourceMode(source)),
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


def _run_adapter_child(raw_jsonl: Path) -> None:
    from tools.uwb.dwm3000_udp_adapter import run_adapter

    run_adapter(
        listen_host="0.0.0.0",
        listen_port=7007,
        target_host="127.0.0.1",
        target_port=9000,
        raw_jsonl=raw_jsonl,
    )


def _cloudflared_archive_name() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "cloudflared-darwin-arm64.tgz"
    if machine in {"x86_64", "amd64"}:
        return "cloudflared-darwin-amd64.tgz"
    raise RuntimeError(f"Unsupported Mac architecture: {machine}")


def _ensure_cloudflared() -> Path:
    installed = shutil.which("cloudflared")
    if installed:
        return Path(installed)
    destination = _app_support_dir() / "cloudflared"
    if destination.is_file():
        return destination
    archive_name = _cloudflared_archive_name()
    archive_path = _app_support_dir() / archive_name
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{archive_name}"
    archive_path.unlink(missing_ok=True)
    tls_context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, context=tls_context) as response:
        with archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)
    with tarfile.open(archive_path, "r:gz") as archive:
        member = next((item for item in archive.getmembers() if Path(item.name).name == "cloudflared"), None)
        if member is None:
            raise RuntimeError("The Cloudflare download did not contain cloudflared")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RuntimeError("Unable to extract cloudflared")
        with destination.open("wb") as output:
            shutil.copyfileobj(extracted, output)
    archive_path.unlink(missing_ok=True)
    destination.chmod(0o755)
    return destination


class TrackingApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("620x430")
        self.root.minsize(560, 400)
        self.mode = tk.StringVar(value="simulation")
        self.status = tk.StringVar(value="Stopped")
        self.local_url = tk.StringVar(value="—")
        self.public_url = tk.StringVar(value="—")
        self.backend: subprocess.Popen[str] | None = None
        self.adapter: subprocess.Popen[str] | None = None
        self.tunnel: subprocess.Popen[str] | None = None
        self.port: int | None = None
        self._log_handles: list[object] = []
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=24)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text=APP_NAME, font=("Helvetica", 20, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text="Run the local tracking host and open the dashboard without Terminal.",
        ).pack(anchor="w", pady=(4, 20))

        mode_frame = ttk.LabelFrame(container, text="Data source", padding=12)
        mode_frame.pack(fill="x")
        ttk.Radiobutton(
            mode_frame,
            text="Simulation",
            variable=self.mode,
            value="simulation",
        ).pack(side="left", padx=(0, 20))
        ttk.Radiobutton(
            mode_frame,
            text="Real sensors (DWM3000 + waist IMU)",
            variable=self.mode,
            value="udp",
        ).pack(side="left")

        status_frame = ttk.Frame(container, padding=(0, 18))
        status_frame.pack(fill="x")
        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.status, font=("Helvetica", 13, "bold")).grid(
            row=0, column=1, sticky="w", padx=8
        )
        ttk.Label(status_frame, text="Local / Android Wi-Fi URL:").grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Label(status_frame, textvariable=self.local_url).grid(
            row=1, column=1, sticky="w", padx=8, pady=(12, 0)
        )
        ttk.Label(status_frame, text="Public URL:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self.public_url).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )
        status_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(container)
        button_frame.pack(fill="x")
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.open_button = ttk.Button(
            button_frame, text="Open Dashboard", command=self.open_dashboard, state="disabled"
        )
        self.open_button.pack(side="left")
        self.share_button = ttk.Button(
            button_frame, text="Share Publicly", command=self.share_publicly, state="disabled"
        )
        self.share_button.pack(side="left", padx=8)

        link_frame = ttk.Frame(container)
        link_frame.pack(fill="x", pady=(12, 0))
        ttk.Button(link_frame, text="Copy Local URL", command=lambda: self.copy(self.local_url.get())).pack(
            side="left"
        )
        ttk.Button(link_frame, text="Copy Public URL", command=lambda: self.copy(self.public_url.get())).pack(
            side="left", padx=8
        )
        ttk.Button(link_frame, text="Open Logs", command=self.open_logs).pack(side="right")

        ttk.Separator(container).pack(fill="x", pady=18)
        ttk.Label(
            container,
            text=(
                "Public sharing uses a temporary free Cloudflare URL. Anyone with the URL can view "
                "telemetry, so stop sharing after the demo."
            ),
            foreground="#6b4d00",
            wraplength=560,
        ).pack(anchor="w")

    def start(self) -> None:
        if self.backend is not None:
            return
        ui_dist = _bundled_ui_dist()
        if not ui_dist.is_dir():
            messagebox.showerror(APP_NAME, "Bundled UI files are missing. Rebuild the Mac app.")
            return
        if self.mode.get() == "udp" and self._udp_port_busy(9000):
            messagebox.showerror(
                APP_NAME,
                "UDP port 9000 is already in use. Stop the existing tracking backend and try again.",
            )
            return
        self.port = _available_tcp_port()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backend_log = (_log_dir() / f"backend-{timestamp}.log").open("a", encoding="utf-8")
        self._log_handles.append(backend_log)
        self.backend = subprocess.Popen(
            _child_command("--backend-child", self.mode.get(), str(self.port), str(ui_dist)),
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if self.mode.get() == "udp":
            adapter_log = (_log_dir() / f"adapter-{timestamp}.log").open("a", encoding="utf-8")
            self._log_handles.append(adapter_log)
            raw_path = _log_dir() / f"raw-dwm3000-{timestamp}.jsonl"
            self.adapter = subprocess.Popen(
                _child_command("--adapter-child", str(raw_path)),
                stdout=adapter_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        self.status.set("Starting…")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.root.after(150, lambda: self._wait_for_backend(0))

    @staticmethod
    def _udp_port_busy(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            try:
                probe.bind(("0.0.0.0", port))
            except OSError:
                return True
        return False

    def _wait_for_backend(self, attempt: int) -> None:
        if self.backend is None:
            return
        if self.backend.poll() is not None:
            self.status.set("Failed — open logs for details")
            self.stop()
            return
        assert self.port is not None
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=0.4) as response:
                health = json.load(response)
            expected = self.mode.get()
            if health.get("source") != expected:
                raise RuntimeError("Unexpected data source")
        except (OSError, urllib.error.URLError, ValueError, RuntimeError):
            if attempt < 80:
                self.root.after(150, lambda: self._wait_for_backend(attempt + 1))
            else:
                self.status.set("Startup timed out — open logs for details")
            return
        self.status.set("Running simulation" if self.mode.get() == "simulation" else "Running real sensors")
        self.local_url.set(f"http://{_lan_address()}:{self.port}")
        self.open_button.configure(state="normal")
        self.share_button.configure(state="normal")
        self.open_dashboard()

    def open_dashboard(self) -> None:
        if self.port is not None:
            webbrowser.open(f"http://127.0.0.1:{self.port}")

    def share_publicly(self) -> None:
        if self.port is None or self.backend is None or self.tunnel is not None:
            return
        if not messagebox.askyesno(
            "Public telemetry link",
            "Anyone with this temporary link can view the dashboard. Start public sharing?",
        ):
            return
        self.status.set("Preparing secure public tunnel…")
        self.share_button.configure(state="disabled")
        threading.Thread(target=self._start_tunnel_worker, daemon=True).start()

    def _start_tunnel_worker(self) -> None:
        try:
            cloudflared = _ensure_cloudflared()
            assert self.port is not None
            self.tunnel = subprocess.Popen(
                [
                    str(cloudflared),
                    "tunnel",
                    "--no-autoupdate",
                    "--url",
                    f"http://127.0.0.1:{self.port}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            log_path = _log_dir() / f"tunnel-{time.strftime('%Y%m%d-%H%M%S')}.log"
            with log_path.open("a", encoding="utf-8") as output:
                assert self.tunnel.stdout is not None
                for line in self.tunnel.stdout:
                    output.write(line)
                    output.flush()
                    match = QUICK_TUNNEL_PATTERN.search(line)
                    if match:
                        url = match.group(0)
                        self.root.after(0, lambda value=url: self._tunnel_ready(value))
            code = self.tunnel.wait()
            if code != 0:
                self.root.after(0, lambda: self._tunnel_failed("Cloudflare tunnel stopped unexpectedly."))
        except Exception as exc:
            self.root.after(0, lambda error=str(exc): self._tunnel_failed(error))

    def _tunnel_ready(self, url: str) -> None:
        self.public_url.set(url)
        self.status.set("Running + publicly shared")
        self.copy(url)
        messagebox.showinfo(APP_NAME, "Public URL copied. Paste it into Android or any browser.")

    def _tunnel_failed(self, error: str) -> None:
        self.public_url.set("—")
        self.tunnel = None
        self.status.set("Running — public sharing failed")
        self.share_button.configure(state="normal")
        messagebox.showerror(APP_NAME, f"Could not start public sharing:\n{error}")

    def copy(self, value: str) -> None:
        if value == "—":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update()

    def open_logs(self) -> None:
        subprocess.run(["open", str(_log_dir())], check=False)

    @staticmethod
    def _terminate(process: subprocess.Popen[str] | None) -> None:
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def stop(self) -> None:
        self._terminate(self.tunnel)
        self._terminate(self.adapter)
        self._terminate(self.backend)
        self.tunnel = None
        self.adapter = None
        self.backend = None
        self.port = None
        for handle in self._log_handles:
            handle.close()
        self._log_handles.clear()
        self.status.set("Stopped")
        self.local_url.set("—")
        self.public_url.set("—")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.share_button.configure(state="disabled")

    def close(self) -> None:
        self.stop()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(add_help=not getattr(sys, "frozen", False))
    parser.add_argument("--backend-child", nargs=3, metavar=("SOURCE", "PORT", "UI_DIST"))
    parser.add_argument("--adapter-child", metavar="RAW_JSONL")
    args = parser.parse_args()
    if args.backend_child:
        source, port, ui_dist = args.backend_child
        _run_backend_child(source, int(port), Path(ui_dist))
        return
    if args.adapter_child:
        _run_adapter_child(Path(args.adapter_child))
        return
    root = tk.Tk()
    TrackingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
