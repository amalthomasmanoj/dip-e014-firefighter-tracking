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
import urllib.error
import urllib.parse
import urllib.request

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
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                if candidate == preferred:
                    continue
                raise
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


class HostController:
    """Own the packaged backend processes and expose safe controls to the WebView."""

    def __init__(self) -> None:
        self.mode = "simulation"
        self.port = _available_tcp_port()
        self.backend: subprocess.Popen[str] | None = None
        self.adapter: subprocess.Popen[str] | None = None
        self.tunnel: subprocess.Popen[str] | None = None
        self.public_url: str | None = None
        self._log_handles: list[object] = []
        self._lock = threading.RLock()
        self._tunnel_ready = threading.Event()

    def get_status(self) -> dict[str, object]:
        with self._lock:
            running = self.backend is not None and self.backend.poll() is None
            source_label = "simulation" if self.mode == "simulation" else "real sensors"
            status = f"Running {source_label}" if running else "Stopped"
            if running and self.public_url:
                status += " + publicly shared"
            return {
                "mode": self.mode,
                "running": running,
                "status": status,
                "local_url": f"http://{_lan_address()}:{self.port}",
                "public_url": self.public_url,
            }

    def start(self, mode: str = "simulation") -> dict[str, object]:
        if mode not in {"simulation", "udp"}:
            raise ValueError("Data source must be simulation or udp")
        with self._lock:
            if self.backend is not None and self.backend.poll() is None and self.mode == mode:
                return self.get_status()
            self._stop_locked()
            self.mode = mode
        ui_dist = _bundled_ui_dist()
        if not ui_dist.is_dir():
            raise RuntimeError("Bundled UI files are missing. Rebuild the Mac app.")
        if mode == "udp" and self._udp_port_busy(9000):
            raise RuntimeError(
                "UDP port 9000 is already in use. Stop the existing tracking backend and try again."
            )
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backend_log = (_log_dir() / f"backend-{timestamp}.log").open("a", encoding="utf-8")
        self._log_handles.append(backend_log)
        self.backend = subprocess.Popen(
            _child_command("--backend-child", mode, str(self.port), str(ui_dist)),
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if mode == "udp":
            adapter_log = (_log_dir() / f"adapter-{timestamp}.log").open("a", encoding="utf-8")
            self._log_handles.append(adapter_log)
            raw_path = _log_dir() / f"raw-dwm3000-{timestamp}.jsonl"
            self.adapter = subprocess.Popen(
                _child_command("--adapter-child", str(raw_path)),
                stdout=adapter_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        self._wait_for_backend(mode)
        return self.get_status()

    def switch_mode(self, mode: str) -> dict[str, object]:
        return self.start(mode)

    @staticmethod
    def _udp_port_busy(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            try:
                probe.bind(("0.0.0.0", port))
            except OSError:
                return True
        return False

    def _wait_for_backend(self, expected_mode: str) -> None:
        for _attempt in range(80):
            if self.backend is None or self.backend.poll() is not None:
                self._stop_locked()
                raise RuntimeError("The tracking backend stopped during startup. Open Logs for details.")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/health", timeout=0.4
                ) as response:
                    health = json.load(response)
                if health.get("source") == expected_mode:
                    return
            except (OSError, urllib.error.URLError, ValueError):
                pass
            time.sleep(0.15)
        self._stop_locked()
        raise RuntimeError("The tracking backend timed out during startup. Open Logs for details.")

    def share_publicly(self) -> dict[str, object]:
        with self._lock:
            if self.backend is None or self.backend.poll() is not None:
                raise RuntimeError("The tracking backend is not running")
            if self.public_url:
                return self.get_status()
            if self.tunnel is None or self.tunnel.poll() is not None:
                self._tunnel_ready.clear()
                cloudflared = _ensure_cloudflared()
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
                threading.Thread(
                    target=self._read_tunnel_output,
                    args=(self.tunnel,),
                    daemon=True,
                ).start()
        if not self._tunnel_ready.wait(timeout=30):
            with self._lock:
                self._terminate(self.tunnel)
                self.tunnel = None
            raise RuntimeError("Cloudflare did not provide a public URL within 30 seconds")
        with self._lock:
            if not self.public_url:
                self.tunnel = None
                raise RuntimeError("Cloudflare tunnel stopped before creating a public URL")
            public_url = self.public_url
        if not self._public_dns_available(public_url):
            with self._lock:
                self._terminate(self.tunnel)
                self.tunnel = None
                self.public_url = None
            raise RuntimeError("The public URL was created but did not appear in public DNS")
        return self.get_status()

    @staticmethod
    def _public_dns_available(public_url: str) -> bool:
        tls_context = ssl.create_default_context(cafile=certifi.where())
        hostname = urllib.parse.urlparse(public_url).hostname
        if not hostname:
            return False
        query = urllib.parse.urlencode({"name": hostname, "type": "A"})
        request = urllib.request.Request(
            f"https://cloudflare-dns.com/dns-query?{query}",
            headers={"Accept": "application/dns-json"},
        )
        for _attempt in range(40):
            try:
                with urllib.request.urlopen(
                    request,
                    context=tls_context,
                    timeout=2,
                ) as response:
                    dns_response = json.load(response)
                if dns_response.get("Status") == 0 and dns_response.get("Answer"):
                    return True
            except (OSError, urllib.error.URLError, ValueError):
                time.sleep(0.5)
        return False

    def _read_tunnel_output(self, process: subprocess.Popen[str]) -> None:
        log_path = _log_dir() / f"tunnel-{time.strftime('%Y%m%d-%H%M%S')}.log"
        candidate_url: str | None = None
        try:
            with log_path.open("a", encoding="utf-8") as output:
                assert process.stdout is not None
                for line in process.stdout:
                    output.write(line)
                    output.flush()
                    match = QUICK_TUNNEL_PATTERN.search(line)
                    if match:
                        candidate_url = match.group(0)
                    if candidate_url and "Registered tunnel connection" in line:
                        with self._lock:
                            self.public_url = candidate_url
                        self._tunnel_ready.set()
            process.wait()
        finally:
            self._tunnel_ready.set()

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

    def _stop_locked(self) -> None:
        self._terminate(self.tunnel)
        self._terminate(self.adapter)
        self._terminate(self.backend)
        self.tunnel = None
        self.adapter = None
        self.backend = None
        self.public_url = None
        self._tunnel_ready.set()
        for handle in self._log_handles:
            handle.close()
        self._log_handles.clear()

    def stop(self) -> dict[str, object]:
        with self._lock:
            self._stop_locked()
            return self.get_status()


def _run_embedded_app() -> None:
    import webview

    controller = HostController()
    try:
        controller.start("simulation")
        webview.create_window(
            APP_NAME,
            url=f"http://127.0.0.1:{controller.port}/?desktop=1",
            js_api=controller,
            width=1440,
            height=920,
            min_size=(960, 640),
            background_color="#f4f6f8",
        )
        webview.start(gui="cocoa", debug=False)
    finally:
        controller.stop()


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
    _run_embedded_app()


if __name__ == "__main__":
    main()
