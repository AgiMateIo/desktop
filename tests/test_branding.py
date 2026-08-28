"""Tests for the brand identity layer.

The SVG resolver is the part worth guarding: when it silently stops matching,
nothing raises — Qt just falls back to black, and the tray goes from the
connector mark to a black blob that still looks deliberate.
"""

import os
import struct
import sys

import pytest


@pytest.fixture(scope="module")
def qt_app():
    """A Qt application, without which no pixmap can be built.

    Offscreen unless the environment has already chosen a platform, so the
    suite runs the same on a headless machine as on a desktop.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def branding(qt_app):
    from ui import branding as module

    return module


class TestResolveSvg:
    """Flattening the identity's `<style>` block into attributes."""

    def test_dark_theme_uses_the_dark_ink(self, branding):
        svg = branding.resolve_svg("connector-flat", branding.DARK).decode()

        assert 'fill="#228391"' in svg  # teal-500
        assert "#1c6975" not in svg

    def test_light_theme_uses_the_light_strip_ink(self, branding):
        svg = branding.resolve_svg("connector-flat", branding.LIGHT).decode()

        assert 'fill="#1c6975"' in svg  # teal-600
        assert "#228391" not in svg

    def test_style_block_and_classes_are_gone(self, branding):
        # Anything left behind is a shape Qt would paint black.
        for name in ("connector-flat", "connector-flat-linked", "connector-tile"):
            for theme in (branding.DARK, branding.LIGHT):
                svg = branding.resolve_svg(name, theme).decode()
                assert "<style" not in svg
                assert 'class="' not in svg

    def test_ink_overrides_every_fill(self, branding):
        # The macOS template icon is one flat colour, whatever the theme says.
        svg = branding.resolve_svg(
            "connector-flat-linked", branding.DARK, ink="#000000"
        ).decode()

        assert svg.count('fill="#000000"') == 2  # ring and module
        assert "#228391" not in svg

    def test_gradient_stops_resolve_per_theme(self, branding):
        dark = branding.resolve_svg("connector-tile", branding.DARK).decode()
        light = branding.resolve_svg("connector-tile", branding.LIGHT).decode()

        assert 'stop-color="#231f1c"' in dark  # warm-850 plate
        assert 'stop-color="#f0eee9"' in light  # warm-200 plate
        # The light theme drops the mark a whole step: teal-400 washes out.
        assert 'stop-color="#154e58"' in light  # teal-700

    def test_stop_opacity_survives_resolution(self, branding):
        # The bloom is capped at 0.22 as a contrast floor, not as taste.
        svg = branding.resolve_svg("connector-tile", branding.DARK).decode()

        assert 'stop-opacity="0.22"' in svg


class TestSplitMedia:
    """The light-theme block is found by brace matching, not by position."""

    def test_media_block_is_not_assumed_to_be_last(self, branding):
        css = (
            ".a { fill: #111111; }"
            "@media (prefers-color-scheme: light) { .a { fill: #222222; } }"
            ".b { fill: #333333; }"
        )

        base, light = branding._split_media(css)

        assert "#111111" in base and "#333333" in base
        assert "#222222" not in base
        assert "#222222" in light

    def test_css_without_a_media_block_is_all_base(self, branding):
        base, light = branding._split_media(".a { fill: #111111; }")

        assert "#111111" in base
        assert light == ""


class TestTrayIcon:
    """State said by form: an empty port against an occupied one."""

    def test_icon_is_drawn(self, branding):
        assert not branding.tray_icon(connected=False).isNull()

    def test_connected_differs_from_disconnected_at_readable_sizes(self, branding):
        from PySide6.QtCore import QSize

        size = QSize(branding.LINKED_MIN_PX, branding.LINKED_MIN_PX)
        connected = branding.tray_icon(True).pixmap(size).toImage()
        disconnected = branding.tray_icon(False).pixmap(size).toImage()

        assert connected != disconnected

    def test_below_the_minimum_both_states_show_the_empty_port(self, branding):
        # The stripe is 10.3% of the mark: at 16 px ring and module fuse into a
        # solid rhombus, so the small sizes stay neutral and the tooltip says
        # the state instead.
        from PySide6.QtCore import QSize

        size = QSize(16, 16)
        connected = branding.tray_icon(True).pixmap(size).toImage()
        disconnected = branding.tray_icon(False).pixmap(size).toImage()

        assert connected == disconnected

    def test_macos_gets_a_template_icon(self, branding, monkeypatch):
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        assert branding.tray_icon(False).isMask() is True

    def test_other_platforms_get_the_teal_mark(self, branding, monkeypatch):
        monkeypatch.setattr("platform.system", lambda: "Windows")
        assert branding.tray_icon(False).isMask() is False


class TestAppTile:
    """The launcher icon: always the empty port, never the state."""

    def test_square_tile_fills_its_corners(self, branding):
        image = branding.app_tile(128, branding.DARK).toImage()

        assert image.pixelColor(2, 2).alpha() == 255
        assert image.pixelColor(125, 125).alpha() == 255

    def test_rounded_tile_clears_its_corners(self, branding):
        image = branding.app_tile(128, branding.DARK, rounded=True).toImage()

        assert image.pixelColor(1, 1).alpha() == 0
        assert image.pixelColor(64, 64).alpha() == 255

    def test_ico_carries_every_size_windows_asks_for(self, branding, tmp_path):
        path = tmp_path / "icon.ico"
        branding.write_ico(path, branding.DARK)

        data = path.read_bytes()
        reserved, image_type, count = struct.unpack("<HHH", data[:6])

        assert (reserved, image_type) == (0, 1)
        assert count == 7

        for i in range(count):
            entry = data[6 + 16 * i: 22 + 16 * i]
            _, _, _, _, _, _, length, offset = struct.unpack("<BBBBHHII", entry)
            assert data[offset:offset + 8] == b"\x89PNG\r\n\x1a\n"
            assert length > 0


def _rule_block(sheet: str, selector: str) -> str:
    """The declarations of the first rule whose selector starts with this."""
    start = sheet.index(selector)
    return sheet[start:sheet.index("}", start)]


class TestStylesheet:
    """Roles reach the sheet; primitives do not reach the widgets."""

    def test_sheet_carries_the_theme_roles(self, branding):
        sheet = branding.stylesheet(branding.DARK)

        assert branding.DARK.accent in sheet
        assert branding.DARK.background in sheet
        assert branding.DARK.border in sheet

    def test_themes_produce_different_sheets(self, branding):
        assert branding.stylesheet(branding.DARK) != branding.stylesheet(branding.LIGHT)

    def test_checked_box_gets_a_tick(self, branding):
        # Styling the indicator takes drawing away from the widget style, so
        # the tick has to be supplied or the box reads as a filled square.
        assert "checkmark.svg" in branding.stylesheet(branding.DARK)

    def test_menus_are_left_native(self, branding):
        # Styling QMenu pushes Qt off the native macOS menu the tray needs.
        assert "QMenu" not in branding.stylesheet(branding.DARK)

    def test_the_pane_is_a_rule_and_not_a_box(self, branding):
        # A bordered, rounded pane boxes cards that are already boxed, and at
        # the border colour's contrast only its corners show — they read as
        # stray marks. Only the line under the tab strip survives.
        pane = _rule_block(branding.stylesheet(branding.DARK), "QTabWidget::pane")

        assert "border: none;" in pane
        assert "border-top:" in pane
        assert "border-radius" not in pane

    def test_group_box_title_clears_the_card_border(self, branding):
        # Qt clears the title's rect out of the frame it draws, so a title
        # that dips into the border punches a gap the width of the heading.
        box = _rule_block(branding.stylesheet(branding.DARK), "QGroupBox")
        margin = int(box.split("margin-top:")[1].split("px")[0].strip())

        assert margin > branding.Type.SMALL_PX * 2

    def test_fields_refuse_to_shrink_until_their_text_clips(self, branding):
        fields = _rule_block(branding.stylesheet(branding.DARK), "QLineEdit, QTextEdit")

        assert "min-height:" in fields

    def test_scroll_areas_have_no_frame(self, branding):
        assert "border: none;" in _rule_block(
            branding.stylesheet(branding.DARK), "QScrollArea {"
        )


class TestStatusColour:
    """Signals are state, not brand — the same in both themes."""

    @pytest.mark.parametrize("theme_name", ["DARK", "LIGHT"])
    def test_signals_match_across_themes(self, branding, theme_name):
        theme = getattr(branding, theme_name)

        assert branding.status_color(theme, "success") == branding.Palette.GREEN
        assert branding.status_color(theme, "warning") == branding.Palette.AMBER
        assert branding.status_color(theme, "error") == branding.Palette.RED

    def test_unknown_status_falls_back_to_muted(self, branding):
        assert branding.status_color(branding.DARK, "nonsense") == branding.DARK.muted
