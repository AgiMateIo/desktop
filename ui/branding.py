"""AgiMate identity for the Qt interface — colour, type, radii and the mark.

Everything here comes from identica v1 (`design/tokens/*.json` and the mark
files in `assets/brand/`); nothing is redrawn or re-picked. Two tiers, and the
boundary matters: `Palette` is named paint, `Theme` is roles. Interface code
uses roles only — a widget that reaches for `TEAL_500` has lost the ability to
be re-themed.

The mark SVGs are copied verbatim from the identity repository, media query and
all. Qt's SVG renderer does not apply a `<style>` block, so `resolve_svg()`
flattens the classes into presentation attributes for one theme before handing
the bytes to QSvgRenderer. Keeping the files verbatim means re-copying them
after an identity change is the whole update.
"""

from __future__ import annotations

import logging
import platform
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

logger = logging.getLogger(__name__)


class Palette:
    """Primitives: named paint, no roles. Only `Theme` may reference these."""

    # The brand hue, 188 degrees.
    TEAL_300 = "#3cc8de"
    TEAL_400 = "#1fa4b8"
    TEAL_500 = "#228391"
    TEAL_600 = "#1c6975"
    TEAL_700 = "#154e58"

    # Mocha Mousse — the one warm ink the interface is allowed.
    MOCHA_500 = "#a47764"
    MOCHA_600 = "#8a6250"

    # Neutrals, warm rather than grey.
    WARM_950 = "#0f0e0d"
    WARM_900 = "#1a1715"
    WARM_850 = "#231f1c"
    WARM_800 = "#2e2a27"
    WARM_300 = "#d8d3cc"
    WARM_200 = "#f0eee9"
    WARM_100 = "#f8f7f5"

    # Cool text greys: body copy stays neutral against the warm ground.
    SLATE_50 = "#f8fafc"
    SLATE_400 = "#94a3b8"
    SLATE_500 = "#64748b"
    SLATE_800 = "#1e293b"

    # State, not brand. Identical in both themes on purpose.
    GREEN = "#22c55e"
    AMBER = "#f59e0b"
    RED = "#ef4444"

    WHITE = "#ffffff"


@dataclass(frozen=True)
class Theme:
    """Semantic roles. Dark is the product's default."""

    name: str
    background: str
    surface: str
    surface_secondary: str
    border: str
    foreground: str
    muted: str
    accent: str
    accent_hover: str
    accent_foreground: str
    success: str
    warning: str
    error: str
    warm: str

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


DARK = Theme(
    name="dark",
    background=Palette.WARM_950,
    surface=Palette.WARM_900,
    surface_secondary=Palette.WARM_850,
    border=Palette.WARM_800,
    foreground=Palette.SLATE_50,
    muted=Palette.SLATE_400,
    accent=Palette.TEAL_500,
    accent_hover=Palette.TEAL_400,
    accent_foreground=Palette.WHITE,
    success=Palette.GREEN,
    warning=Palette.AMBER,
    error=Palette.RED,
    warm=Palette.MOCHA_500,
)

LIGHT = Theme(
    name="light",
    background=Palette.WARM_100,
    surface=Palette.WHITE,
    surface_secondary=Palette.WARM_200,
    border=Palette.WARM_300,
    foreground=Palette.SLATE_800,
    muted=Palette.SLATE_500,
    accent=Palette.TEAL_600,
    accent_hover=Palette.TEAL_500,
    accent_foreground=Palette.WHITE,
    success=Palette.GREEN,
    warning=Palette.AMBER,
    error=Palette.RED,
    warm=Palette.MOCHA_600,
)


class Radius:
    """Theme-independent scale, named by role.

    The whole scale is stated even where this app has no use for a step yet:
    a component that needs one should find it here rather than invent it.
    """

    CONTROL = 8  # buttons, inputs, rows — the default
    CARD = 12  # cards and modals
    PANEL = 16  # large panels
    PILL = 9999  # chips, avatars, badges


class Type:
    """The interface lives in a small scale: 14 px body, 12 px metadata."""

    BODY_PX = 14
    SMALL_PX = 12
    HEADING_PX = 16

    WEIGHT_REGULAR = 400
    WEIGHT_MEDIUM = 500  # the workhorse: labels and buttons
    WEIGHT_SEMIBOLD = 600  # headings


# Filled by install_fonts(); until then the platform decides.
_sans_family = ""
_mono_family = ""


def brand_dir() -> Path:
    """Directory holding the identity's SVG files, copied verbatim."""
    from core.paths import get_app_dir

    return get_app_dir() / "assets" / "brand"


def ui_asset(name: str) -> str:
    """Path to an interface asset, as a Qt stylesheet `url()` value.

    Forward slashes and quotes: Qt parses a stylesheet url() itself, and an
    unquoted Windows path or one with a space in it silently resolves to
    nothing — leaving, for a checkbox, an indicator with no tick in it.
    """
    from core.paths import get_app_dir

    path = (get_app_dir() / "assets" / "ui" / name).as_posix()
    return f'url("{path}")'


def current_theme(app: QGuiApplication | None = None) -> Theme:
    """The theme the system is asking for.

    Dark is the product's default and the fallback: a Qt build too old to
    report a colour scheme gets the theme the identity is designed in.
    """
    try:
        scheme = (app or QGuiApplication.instance()).styleHints().colorScheme()
    except AttributeError:  # Qt < 6.5
        return DARK
    return LIGHT if scheme == Qt.ColorScheme.Light else DARK


# ---------------------------------------------------------------- the mark

_STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL)
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_RULE_RE = re.compile(r"\.([\w-]+)\s*\{([^}]*)\}")
_CLASS_ATTR_RE = re.compile(r'\s+class="([\w-]+)"')


def _split_media(css: str) -> tuple[str, str]:
    """Split CSS into (base rules, rules inside the light media query).

    Brace matching rather than a regex: the media block is last in every
    identity file today, but a regex that assumes so breaks silently the day
    one of them gains a second block.
    """
    start = css.find("@media")
    if start == -1:
        return css, ""

    open_brace = css.find("{", start)
    if open_brace == -1:
        return css, ""

    depth = 0
    for i in range(open_brace, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[:start] + css[i + 1:], css[open_brace + 1:i]

    return css[:start], css[open_brace + 1:]


def _rules(css: str) -> dict[str, dict[str, str]]:
    """Parse `.class { prop: value }` into {class: {prop: value}}."""
    parsed: dict[str, dict[str, str]] = {}
    for class_name, body in _RULE_RE.findall(css):
        props = parsed.setdefault(class_name, {})
        for declaration in body.split(";"):
            if ":" not in declaration:
                continue
            prop, _, value = declaration.partition(":")
            props[prop.strip()] = value.strip()
    return parsed


def resolve_svg(name: str, theme: Theme, ink: str | None = None) -> bytes:
    """Read an identity SVG and flatten its `<style>` block for one theme.

    Qt renders SVG Tiny: a `<style>` block is ignored and every class-styled
    shape falls back to black. So the classes become presentation attributes
    here instead.

    Args:
        name: file stem in `assets/brand/`, e.g. "connector-flat".
        theme: which side of the media query to resolve.
        ink: replaces every resolved `fill`, for the macOS template icon,
            where the whole mark must be one flat colour.
    """
    source = (brand_dir() / f"{name}.svg").read_text(encoding="utf-8")

    css = "".join(_STYLE_RE.findall(source))
    css = _COMMENT_RE.sub("", css)
    base, light = _split_media(css)

    styles = _rules(base)
    if not theme.is_dark:
        for class_name, props in _rules(light).items():
            styles.setdefault(class_name, {}).update(props)

    def substitute(match: re.Match[str]) -> str:
        props = styles.get(match.group(1))
        if not props:
            return ""
        rendered = {p: (ink if ink and p == "fill" else v) for p, v in props.items()}
        return "".join(f' {prop}="{value}"' for prop, value in rendered.items())

    resolved = _CLASS_ATTR_RE.sub(substitute, source)
    return _STYLE_RE.sub("", resolved).encode("utf-8")


def render_svg(svg: bytes, size: int) -> QPixmap:
    """Rasterise resolved SVG bytes into a square pixmap."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg)).render(painter, QRectF(0, 0, size, size))
    painter.end()

    return QPixmap.fromImage(image)


# Sizes a tray strip asks for, from a 16 px Windows notification area to a
# retina macOS menu bar (22 pt at 2x).
TRAY_SIZES = (16, 18, 20, 22, 24, 32, 44, 64)

# Below this the connected mark's 10.3% stripe is under 2 px and ring and
# module fuse into a solid rhombus — so the small sizes show the empty port
# and the tooltip carries the state.
LINKED_MIN_PX = 24


def tray_icon(connected: bool, theme: Theme | None = None) -> QIcon:
    """The tray mark: an empty port, or a port with the module seated in it.

    State is said by form, never by colour — the difference has to survive a
    colour-blind eye and a 16 px strip, and the macOS menu bar allows one ink
    in the first place. There the icon is a black template and the system
    tints it for the strip it lands on; elsewhere it is the teal the theme
    asks for.
    """
    theme = theme or current_theme()
    template = platform.system() == "Darwin"
    ink = "#000000" if template else None

    empty = resolve_svg("connector-flat", theme, ink=ink)
    linked = resolve_svg("connector-flat-linked", theme, ink=ink) if connected else empty

    icon = QIcon()
    for size in TRAY_SIZES:
        svg = linked if size >= LINKED_MIN_PX else empty
        icon.addPixmap(render_svg(svg, size))

    icon.setIsMask(template)
    return icon


APP_ICON_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def app_tile(size: int, theme: Theme | None = None, rounded: bool = False) -> QPixmap:
    """The app tile at one size — the port on its warm plate.

    The tile never shows the connected state: a launcher icon is cached by the
    OS, and an icon that changes reads as a glitch.

    Args:
        rounded: clip to the platform's icon corner. The identity draws a full
            square; macOS expects the rounded rect, and the tile's corners are
            bare plate, so nothing of the mark is lost.
    """
    pixmap = render_svg(resolve_svg("connector-tile", theme or DARK), size)
    if not rounded:
        return pixmap

    masked = QPixmap(size, size)
    masked.fill(Qt.GlobalColor.transparent)

    painter = QPainter(masked)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), size * 0.2237, size * 0.2237)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()

    return masked


def app_icon(theme: Theme | None = None) -> QIcon:
    """Window and taskbar icon, built from the tile."""
    icon = QIcon()
    for size in (16, 32, 64, 128, 256):
        icon.addPixmap(app_tile(size, theme))
    return icon


def mark_pixmap(size: int, theme: Theme | None = None) -> QPixmap:
    """The standalone faceted mark, for in-app headers."""
    return render_svg(resolve_svg("connector-mark", theme or current_theme()), size)


def write_ico(path: Path, theme: Theme | None = None) -> None:
    """Write a multi-size Windows .ico with PNG-compressed entries.

    Qt writes a single-size ICO, and Windows picks an icon per surface — the
    taskbar wants 32, the tray 16, Explorer's large view 256. Entries are
    stored as PNG, which every Windows since Vista reads.
    """
    entries: list[tuple[int, bytes]] = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        buffer = QByteArray()
        image = app_tile(size, theme).toImage()

        device = QBuffer(buffer)
        device.open(QBuffer.OpenModeFlag.WriteOnly)
        image.save(device, "PNG")
        device.close()
        entries.append((size, bytes(buffer.data())))

    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = len(header) + 16 * len(entries)

    directory = b""
    for size, png in entries:
        # 0 in the ICO directory means 256.
        directory += struct.pack(
            "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset
        )
        offset += len(png)

    path.write_bytes(header + directory + b"".join(png for _, png in entries))


# ---------------------------------------------------------------- type

FONT_SANS = "IBM Plex Sans"
FONT_MONO = "IBM Plex Mono"


def install_fonts() -> tuple[str, str]:
    """Resolve the two brand families, loading bundled files if there are any.

    IBM Plex is the identity's one family — sans for everything, mono for
    machine values. Files dropped in `assets/brand/fonts/` are registered with
    Qt; failing that an installed copy is used; failing that the platform's own
    UI font, which is the one substitution the identity tolerates.
    """
    global _sans_family, _mono_family

    fonts_dir = brand_dir() / "fonts"
    if fonts_dir.is_dir():
        for font_file in sorted(fonts_dir.glob("*.[to]tf")):
            if QFontDatabase.addApplicationFont(str(font_file)) == -1:
                logger.warning(f"Could not load bundled font: {font_file.name}")

    available = set(QFontDatabase.families())
    _sans_family = FONT_SANS if FONT_SANS in available else ""
    _mono_family = FONT_MONO if FONT_MONO in available else ""

    if not _sans_family:
        logger.info(f"{FONT_SANS} not available, using the platform UI font")

    return _sans_family, _mono_family


def _family_stack(mono: bool = False) -> str:
    """A CSS font-family stack for the stylesheet, brand family first.

    Named faces only — Qt resolves a CSS generic like `sans-serif` against a
    family literally called "Sans Serif", warns when it finds none, and then
    falls back anyway. The last entry is the platform's own UI font, which is
    the one substitution the identity tolerates.
    """
    if mono:
        brand, fallbacks = _mono_family, ['"SF Mono"', '"Menlo"', '"Consolas"']
    else:
        brand, fallbacks = _sans_family, ['"SF Pro Text"', '"Segoe UI"', '"Helvetica Neue"']

    families = ([f'"{brand}"'] if brand else []) + fallbacks
    return ", ".join(families)


def base_font() -> QFont:
    """The application font: 14 px, the size most working interfaces run on."""
    font = QFont()
    if _sans_family:
        font.setFamily(_sans_family)
    font.setPixelSize(Type.BODY_PX)
    font.setWeight(QFont.Weight.Normal)
    return font


# ---------------------------------------------------------------- interface

def palette(theme: Theme) -> QPalette:
    """A QPalette in the brand roles.

    The stylesheet does not reach everything — message box text, disabled
    states, the text cursor and selection all read the palette — so the roles
    are stated twice, once here and once in the sheet.
    """
    qp = QPalette()
    window, base = QColor(theme.background), QColor(theme.surface)
    text, muted = QColor(theme.foreground), QColor(theme.muted)
    accent = QColor(theme.accent)

    qp.setColor(QPalette.ColorRole.Window, window)
    qp.setColor(QPalette.ColorRole.WindowText, text)
    qp.setColor(QPalette.ColorRole.Base, base)
    qp.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.surface_secondary))
    qp.setColor(QPalette.ColorRole.Text, text)
    qp.setColor(QPalette.ColorRole.Button, QColor(theme.surface_secondary))
    qp.setColor(QPalette.ColorRole.ButtonText, text)
    qp.setColor(QPalette.ColorRole.ToolTipBase, base)
    qp.setColor(QPalette.ColorRole.ToolTipText, text)
    qp.setColor(QPalette.ColorRole.PlaceholderText, muted)
    qp.setColor(QPalette.ColorRole.Highlight, accent)
    qp.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.accent_foreground))
    qp.setColor(QPalette.ColorRole.Link, accent)

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        qp.setColor(QPalette.ColorGroup.Disabled, role, muted)

    return qp


def stylesheet(theme: Theme) -> str:
    """The application stylesheet.

    Rectangles with an 8 px corner: the identity's diagonal belongs to the
    mark, and the interface is built on the soft rectangle. What ties them is
    the softness, not the angle.

    QMenu is deliberately absent — styling it would push Qt off the native
    macOS menu the tray needs.
    """
    accent_pressed = Palette.TEAL_600 if theme.is_dark else Palette.TEAL_700
    # With no brand family present the rule is left out entirely, so the
    # application font set by base_font() — the platform's own — governs.
    # Naming families that do not exist only sends Qt looking for them.
    sans_rule = f"font-family: {_family_stack()};" if _sans_family else ""
    return f"""
    QWidget {{
        background-color: {theme.background};
        color: {theme.foreground};
        {sans_rule}
        font-size: {Type.BODY_PX}px;
    }}

    QDialog, QScrollArea, QAbstractScrollArea {{
        background-color: {theme.background};
    }}

    QLabel {{
        background: transparent;
    }}
    QLabel[role="caption"] {{
        color: {theme.muted};
        font-size: {Type.SMALL_PX}px;
    }}
    QLabel[role="warm"] {{
        color: {theme.warm};
    }}

    /* ---- panels ---- */
    QGroupBox {{
        background-color: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: {Radius.CARD}px;
        margin-top: 22px;
        padding: 16px 14px 14px;
        font-weight: {Type.WEIGHT_SEMIBOLD};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 2px;
        padding: 0 2px 6px 0;
        color: {theme.muted};
        font-size: {Type.SMALL_PX}px;
        font-weight: {Type.WEIGHT_MEDIUM};
    }}

    QFrame[frameShape="4"], QFrame[frameShape="5"] {{
        background-color: {theme.border};
        border: none;
        max-height: 1px;
    }}

    /* ---- tabs ---- */
    QTabWidget::pane {{
        border: 1px solid {theme.border};
        border-radius: {Radius.CARD}px;
        background-color: {theme.surface};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {theme.muted};
        padding: 7px 14px;
        border: 1px solid transparent;
        border-top-left-radius: {Radius.CONTROL}px;
        border-top-right-radius: {Radius.CONTROL}px;
        font-weight: {Type.WEIGHT_MEDIUM};
    }}
    QTabBar::tab:!selected {{
        /* Carries the pane's top border across the strip: without it the line
           starts abruptly where the last tab ends. */
        border-bottom-color: {theme.border};
    }}
    QTabBar::tab:hover {{
        color: {theme.foreground};
    }}
    QTabBar::tab:selected {{
        background-color: {theme.surface};
        color: {theme.foreground};
        border-color: {theme.border};
        border-bottom-color: {theme.surface};
    }}

    /* ---- controls ---- */
    QPushButton {{
        background-color: {theme.surface_secondary};
        color: {theme.foreground};
        border: 1px solid {theme.border};
        border-radius: {Radius.CONTROL}px;
        padding: 7px 16px;
        font-weight: {Type.WEIGHT_MEDIUM};
    }}
    QPushButton:hover {{
        border-color: {theme.accent};
    }}
    QPushButton:pressed {{
        background-color: {theme.border};
    }}
    QPushButton:disabled {{
        color: {theme.muted};
        border-color: {theme.border};
    }}
    QPushButton[accent="true"] {{
        background-color: {theme.accent};
        color: {theme.accent_foreground};
        border-color: {theme.accent};
    }}
    QPushButton[accent="true"]:hover {{
        background-color: {theme.accent_hover};
        border-color: {theme.accent_hover};
    }}
    QPushButton[accent="true"]:pressed {{
        background-color: {accent_pressed};
        border-color: {accent_pressed};
    }}
    QPushButton[accent="true"]:disabled {{
        background-color: {theme.surface_secondary};
        color: {theme.muted};
        border-color: {theme.border};
    }}
    QPushButton[trigger="true"] {{
        background-color: {theme.surface};
        border-radius: {Radius.CARD}px;
        padding: 12px 14px;
    }}
    QPushButton[trigger="true"]:hover {{
        background-color: {theme.surface_secondary};
        border-color: {theme.accent};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
        background-color: {theme.surface_secondary};
        color: {theme.foreground};
        border: 1px solid {theme.border};
        border-radius: {Radius.CONTROL}px;
        padding: 6px 9px;
        selection-background-color: {theme.accent};
        selection-color: {theme.accent_foreground};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QSpinBox:focus, QComboBox:focus {{
        border-color: {theme.accent};
    }}
    QLineEdit:read-only {{
        color: {theme.muted};
    }}
    QLineEdit[mono="true"], QTextEdit[mono="true"], QPlainTextEdit[mono="true"] {{
        font-family: {_family_stack(mono=True)};
        font-size: {Type.SMALL_PX}px;
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {theme.surface};
        border: 1px solid {theme.border};
        selection-background-color: {theme.accent};
        selection-color: {theme.accent_foreground};
        outline: none;
    }}

    QCheckBox {{
        spacing: 8px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid {theme.border};
        border-radius: 4px;
        background-color: {theme.surface_secondary};
    }}
    QCheckBox::indicator:hover {{
        border-color: {theme.accent};
    }}
    QCheckBox::indicator:checked {{
        background-color: {theme.accent};
        border-color: {theme.accent};
        image: {ui_asset("checkmark.svg")};
    }}
    QCheckBox::indicator:disabled {{
        background-color: {theme.surface};
        border-color: {theme.border};
    }}

    /* ---- scrollbars ---- */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {theme.border};
        border-radius: 5px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {theme.muted};
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {theme.border};
        border-radius: 5px;
        min-width: 28px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
        width: 0;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent;
    }}
    """


def apply(app: QGuiApplication) -> Theme:
    """Dress the whole application: fonts, palette, stylesheet, window icon.

    Returns the theme that was applied.
    """
    install_fonts()
    theme = current_theme(app)

    app.setFont(base_font())
    app.setPalette(palette(theme))
    app.setStyleSheet(stylesheet(theme))
    app.setWindowIcon(app_icon(theme))

    logger.info(f"Brand applied: {theme.name} theme, sans={_sans_family or 'system'}")
    return theme


def accent(button) -> None:
    """Mark a button as the accented one — actions belong to the accent."""
    button.setProperty("accent", True)


def caption(label) -> None:
    """Mark a label as metadata: muted, one step down in size."""
    label.setProperty("role", "caption")


def mono(edit) -> None:
    """Mark a field as holding a machine value — ids, keys, tokens, sizes."""
    edit.setProperty("mono", True)


def status_color(theme: Theme, status: str) -> str:
    """Signal colour for a state word. Signals are state, not brand."""
    return {
        "success": theme.success,
        "warning": theme.warning,
        "error": theme.error,
        "muted": theme.muted,
    }.get(status, theme.muted)
