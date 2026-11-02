from pathlib import Path

from starlette.routing import Mount

from backend.api.app import create_app
from backend.config.source import SourceMode


def test_serves_built_ui_without_shadowing_api(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>packaged UI</h1>", encoding="utf-8")
    monkeypatch.setenv("E014_UI_DIST", str(tmp_path))

    app = create_app(source_mode=SourceMode.SIMULATION)
    health_index = next(index for index, route in enumerate(app.routes) if route.path == "/health")
    ui_index, ui_route = next(
        (index, route)
        for index, route in enumerate(app.routes)
        if isinstance(route, Mount) and route.name == "ui"
    )

    assert health_index < ui_index
    assert Path(ui_route.app.directory) == tmp_path
