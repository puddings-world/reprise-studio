import pytest
from PIL import Image

from videogen import cover


def test_find_font_matches_family_prefix_ignoring_case_and_spaces(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "NotoSerifTC-VF.ttf").write_bytes(b"")
    (tmp_path / "Arial.ttf").write_bytes(b"")
    assert cover.find_font("Noto Serif TC", [tmp_path]).name == "NotoSerifTC-VF.ttf"
    assert cover.find_font("missing", [tmp_path]) is None


def test_find_font_accepts_an_explicit_path(tmp_path):
    f = tmp_path / "x.otf"; f.write_bytes(b"")
    assert cover.find_font(str(f), []) == f


def test_project_cover_settings_override_defaults():
    s = cover.settings({"cover": {"title": "阿拉斯加海灣", "side": "right"}})
    assert s["title"] == "阿拉斯加海灣" and s["side"] == "right" and s["size"] == [1664, 928]


SYSTEM_FONT = cover.find_font("NotoSerifTC") or cover.find_font("Arial") or cover.find_font("DejaVuSans")


@pytest.mark.skipif(SYSTEM_FONT is None, reason="no usable system font")
@pytest.mark.parametrize("side", ["left", "right"])
def test_title_is_drawn_on_the_requested_side(side):
    art = Image.new("RGB", (832, 464), (120, 140, 160))
    img = cover.compose_title(art, "阿拉斯加海灣", "Cover by 布丁", SYSTEM_FONT, side, out_size=(640, 360))
    assert img.size == (640, 360)
    gray = img.convert("L")
    import numpy as np
    left = int(np.asarray(gray.crop((0, 0, 320, 360))).sum())
    right = int(np.asarray(gray.crop((320, 0, 640, 360))).sum())
    # the scrim darkens the title side more than the bright title text lightens it
    assert (left < right) if side == "left" else (right < left)
