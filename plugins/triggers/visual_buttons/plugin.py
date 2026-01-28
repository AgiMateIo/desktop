"""Visual Buttons trigger plugin implementation."""

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QInputDialog,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from core.plugin_base import TriggerPlugin

logger = logging.getLogger(__name__)


class InputDialog(QDialog):
    """Simple input dialog for button parameters."""

    def __init__(self, title: str, input_label: str, input_type: str = "text", parent=None):
        super().__init__(parent)
        self.input_type = input_type
        self.result_value: str = ""

        self.setWindowTitle(title)
        self.setMinimumWidth(350)
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._setup_ui(input_label)

    def _setup_ui(self, input_label: str) -> None:
        layout = QVBoxLayout(self)

        # Input field
        form_layout = QFormLayout()

        if self.input_type == "textarea":
            self.input_widget = QTextEdit()
            self.input_widget.setMaximumHeight(100)
        else:
            self.input_widget = QLineEdit()

        form_layout.addRow(input_label + ":", self.input_widget)
        layout.addLayout(form_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def _on_ok(self) -> None:
        if isinstance(self.input_widget, QTextEdit):
            self.result_value = self.input_widget.toPlainText()
        else:
            self.result_value = self.input_widget.text()
        self.accept()

    def get_value(self) -> str:
        return self.result_value


class VisualButtonsWindow(QDialog):
    """Window for Visual Buttons plugin."""

    def __init__(self, plugin: "VisualButtonsTrigger", parent=None):
        super().__init__(parent)
        self.plugin = plugin

        self.setWindowTitle("Visual Buttons")
        self.setMinimumSize(400, 300)
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()

        # Buttons tab
        buttons_tab = self._create_buttons_tab()
        tabs.addTab(buttons_tab, "Buttons")

        # Config tab
        config_tab = self._create_config_tab()
        tabs.addTab(config_tab, "Config")

        layout.addWidget(tabs)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_buttons_tab(self) -> QWidget:
        """Create the buttons tab with grid layout."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Scroll area for buttons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        grid.setSpacing(10)

        buttons = self.plugin.get_config("buttons", [])
        columns = self.plugin.get_config("grid_columns", 3)

        # Ensure columns is an integer (defensive programming)
        try:
            columns = int(columns)
            if columns <= 0:
                columns = 3
        except (ValueError, TypeError):
            logger.warning(f"Invalid grid_columns value: {columns}, using default 3")
            columns = 3

        for i, btn_config in enumerate(buttons):
            row = i // columns
            col = i % columns

            btn = QPushButton(btn_config.get("button_name", f"Button {i+1}"))
            btn.setMinimumHeight(50)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(
                lambda checked=False, cfg=btn_config: self._on_button_click(cfg)
            )
            grid.addWidget(btn, row, col)

        # Add stretch to push buttons to top
        grid.setRowStretch(len(buttons) // columns + 1, 1)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return widget

    def _create_config_tab(self) -> QWidget:
        """Create the config tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Config editor
        config_group = QGroupBox("Configuration (JSON)")
        config_layout = QVBoxLayout(config_group)

        self.config_edit = QTextEdit()
        self.config_edit.setPlainText(
            json.dumps(self.plugin._config, indent=2, ensure_ascii=False)
        )
        config_layout.addWidget(self.config_edit)

        # Save button
        save_btn = QPushButton("Save Config")
        save_btn.clicked.connect(self._save_config)
        config_layout.addWidget(save_btn)

        layout.addWidget(config_group)
        return widget

    def _on_button_click(self, btn_config: dict[str, Any]) -> None:
        """Handle button click."""
        btn_name = btn_config.get("button_name", "")
        trigger_name = btn_config.get("trigger_name", f"device.button.{btn_name}")
        btn_type = btn_config.get("type", "direct")
        params = btn_config.get("params", {})

        logger.info(f"Button clicked: {btn_name}, type: {btn_type}")

        if btn_type == "dialog":
            # Show dialog for input
            dialog_params = btn_config.get("dialog_params", {})
            input_label = dialog_params.get("input_label", "Input")
            input_type = dialog_params.get("input_type", "text")

            dialog = InputDialog(btn_name, input_label, input_type, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                input_value = dialog.get_value()
                if input_value:
                    data = {**params, "input": input_value, "button_name": btn_name}
                    self.plugin.emit_event(trigger_name, data)
                    logger.info(f"Trigger emitted: {trigger_name}")
        else:
            # Direct trigger
            data = {**params, "button_name": btn_name}
            self.plugin.emit_event(trigger_name, data)
            logger.info(f"Trigger emitted: {trigger_name}")

    def _save_config(self) -> None:
        """Save the config from the editor."""
        try:
            config_text = self.config_edit.toPlainText()
            new_config = json.loads(config_text)
            self.plugin._config = new_config
            self.plugin.save_config()
            QMessageBox.information(self, "Config", "Configuration saved!")
            logger.info("Config saved")
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Error", f"Invalid JSON: {e}")


class VisualButtonsTrigger(TriggerPlugin):
    """Trigger plugin for visual buttons."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)

    @property
    def name(self) -> str:
        return "Visual Buttons"

    def validate_config(self) -> tuple[bool, str]:
        """Validate plugin configuration."""
        # Validate grid_columns
        grid_columns = self._config.get("grid_columns", 3)
        if not isinstance(grid_columns, int):
            return False, f"grid_columns must be an integer, got {type(grid_columns).__name__}"
        if grid_columns <= 0:
            return False, f"grid_columns must be positive, got {grid_columns}"

        # Validate buttons list
        buttons = self._config.get("buttons", [])
        if not isinstance(buttons, list):
            return False, f"buttons must be a list, got {type(buttons).__name__}"

        # Validate each button config
        for i, button in enumerate(buttons):
            if not isinstance(button, dict):
                return False, f"Button {i} must be a dict, got {type(button).__name__}"

            # Check required fields
            if "button_name" not in button:
                return False, f"Button {i} missing required field 'button_name'"
            if "trigger_name" not in button:
                return False, f"Button {i} missing required field 'trigger_name'"
            if "type" not in button:
                return False, f"Button {i} missing required field 'type'"

            # Validate type
            if button["type"] not in ("direct", "dialog"):
                return False, f"Button {i} has invalid type '{button['type']}', must be 'direct' or 'dialog'"

        return True, ""

    def has_window(self) -> bool:
        """This plugin has a UI window."""
        return True

    def create_window(self, parent=None) -> QDialog:
        """Create the plugin window."""
        return VisualButtonsWindow(self, parent)

    async def initialize(self) -> None:
        """Initialize the plugin."""
        logger.info(f"VisualButtonsTrigger initialized with {len(self.get_config('buttons', []))} buttons")

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        logger.info("VisualButtonsTrigger shutdown")

    async def start(self) -> None:
        """Start the trigger."""
        self._running = True
        logger.info("VisualButtonsTrigger started")

    async def stop(self) -> None:
        """Stop the trigger."""
        self._running = False
        logger.info("VisualButtonsTrigger stopped")
