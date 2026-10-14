from __future__ import annotations

import pytest

from backend.uwb.anchors import DEFAULT_ANCHORS, anchors_from_env, load_anchors


def test_load_anchors_accepts_arbitrary_anchor_ids(tmp_path) -> None:
    config = tmp_path / "anchors.yaml"
    config.write_text(
        """\
anchors:
  - anchor_id: A1
    x_m: 0
    y_m: 0
  - anchor_id: A2
    x_m: 8
    y_m: 0
  - anchor_id: A4
    x_m: 0
    y_m: 6
    z_m: 1.5
""",
        encoding="utf-8",
    )

    anchors = load_anchors(config)

    assert [anchor.anchor_id for anchor in anchors] == ["A1", "A2", "A4"]
    assert anchors[2].z_m == pytest.approx(1.5)


def test_load_anchors_rejects_duplicate_ids(tmp_path) -> None:
    config = tmp_path / "anchors.yaml"
    config.write_text(
        """\
anchors:
  - {anchor_id: A4, x_m: 0, y_m: 0}
  - {anchor_id: A4, x_m: 1, y_m: 1}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate anchor_id 'A4'"):
        load_anchors(config)


def test_anchors_from_env_uses_defaults_without_config() -> None:
    assert anchors_from_env({}) == DEFAULT_ANCHORS
