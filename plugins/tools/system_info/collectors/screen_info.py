"""Screen information collector using PySide6 QScreen."""

from typing import Any


def collect_screen_info(qt_available: bool) -> list[dict[str, Any]]:
    """Collect display information from all connected screens.

    Args:
        qt_available: Whether QApplication is running and screens are accessible.

    Returns:
        List of screen info dicts. Empty list if Qt is not available.
    """
    if not qt_available:
        return []

    from PySide6.QtWidgets import QApplication

    screens = []
    primary = QApplication.primaryScreen()

    for i, screen in enumerate(QApplication.screens()):
        geo = screen.geometry()
        avail = screen.availableGeometry()
        phys = screen.physicalSize()
        screens.append({
            "index": i,
            "name": screen.name(),
            "manufacturer": screen.manufacturer(),
            "model": screen.model(),
            "geometry": {
                "x": geo.x(),
                "y": geo.y(),
                "width": geo.width(),
                "height": geo.height(),
            },
            "availableGeometry": {
                "x": avail.x(),
                "y": avail.y(),
                "width": avail.width(),
                "height": avail.height(),
            },
            "physicalSizeMm": {
                "width": phys.width(),
                "height": phys.height(),
            },
            "logicalDotsPerInch": screen.logicalDotsPerInch(),
            "physicalDotsPerInch": screen.physicalDotsPerInch(),
            "devicePixelRatio": screen.devicePixelRatio(),
            "refreshRate": screen.refreshRate(),
            "orientation": getattr(screen.orientation(), "name", None),
            "isPrimary": screen == primary,
        })
    return screens
