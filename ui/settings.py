"""Settings window for Agimate Desktop."""

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QPushButton,
    QFormLayout,
    QGroupBox,
    QScrollArea,
    QTextEdit,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt, Signal

from urllib.parse import urlparse

from core.constants import (
    DEFAULT_SERVER_URL,
    DEFAULT_RECONNECT_INTERVAL_MS,
    MIN_RECONNECT_INTERVAL_MS,
    MAX_RECONNECT_INTERVAL_MS,
)
from core.api_endpoints import (
    ENDPOINT_DEVICE_LINK,
    HEADER_DEVICE_AUTH,
    CONTENT_TYPE_JSON,
)

if TYPE_CHECKING:
    from core.config_manager import ConfigManager
    from core.plugin_manager import PluginManager
    from core.device_info import DeviceInfo

logger = logging.getLogger(__name__)


class SettingsWindow(QDialog):
    """Settings window with tabs for app and plugin configuration."""

    settings_changed = Signal()

    def __init__(
        self,
        config_manager: "ConfigManager",
        plugin_manager: "PluginManager",
        device_info: "DeviceInfo",
        parent=None
    ):
        super().__init__(parent)
        self.config_manager = config_manager
        self.plugin_manager = plugin_manager
        self.device_info = device_info

        self.setWindowTitle("Agimate Desktop - Settings")
        self.setMinimumSize(600, 450)
        self.resize(650, 500)
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self._background_tasks: set[asyncio.Task] = set()

        self._setup_ui()
        self._load_settings()

    def _create_task(self, coro) -> asyncio.Task:
        """Create a background task with automatic cleanup.

        Prevents tasks from being garbage collected before completion.

        Args:
            coro: Coroutine to run as a task

        Returns:
            The created task
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # General tab
        self.general_tab = self._create_general_tab()
        self.tabs.addTab(self.general_tab, "General")

        # Plugins tab
        self.plugins_tab = self._create_plugins_tab()
        self.tabs.addTab(self.plugins_tab, "Plugins")

        # Device info tab
        self.device_tab = self._create_device_tab()
        self.tabs.addTab(self.device_tab, "Device")

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Server settings group
        server_group = QGroupBox("Server Connection")
        server_layout = QFormLayout(server_group)
        server_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText(DEFAULT_SERVER_URL)
        self.server_url_edit.setMinimumWidth(350)
        server_layout.addRow("Server URL:", self.server_url_edit)

        self.device_key_edit = QLineEdit()
        self.device_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.device_key_edit.setPlaceholderText("Enter device key")
        self.device_key_edit.setMinimumWidth(350)
        server_layout.addRow("Device Key:", self.device_key_edit)

        self.auto_connect_check = QCheckBox("Auto-connect on startup")
        server_layout.addRow("", self.auto_connect_check)

        self.reconnect_spin = QSpinBox()
        self.reconnect_spin.setRange(MIN_RECONNECT_INTERVAL_MS, MAX_RECONNECT_INTERVAL_MS)
        self.reconnect_spin.setSingleStep(1000)
        self.reconnect_spin.setSuffix(" ms")
        server_layout.addRow("Reconnect interval:", self.reconnect_spin)

        # Link device row
        link_layout = QHBoxLayout()

        self.link_btn = QPushButton("Link Device")
        self.link_btn.setFixedWidth(120)
        self.link_btn.clicked.connect(self._on_link_device)
        link_layout.addWidget(self.link_btn)

        self.link_status_label = QLabel("Not linked")
        self.link_status_label.setStyleSheet("color: gray;")
        link_layout.addWidget(self.link_status_label)

        link_layout.addStretch()
        server_layout.addRow("Device:", link_layout)

        layout.addWidget(server_group)

        # Logging group
        log_group = QGroupBox("Logging")
        log_layout = QFormLayout(log_group)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_layout.addRow("Log level:", self.log_level_combo)

        layout.addWidget(log_group)

        layout.addStretch()
        return widget

    def _create_plugins_tab(self) -> QWidget:
        """Create the plugins settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Scroll area for plugins
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self.plugins_layout = QVBoxLayout(scroll_content)

        # Triggers section
        triggers_label = QLabel("<b>Triggers</b>")
        self.plugins_layout.addWidget(triggers_label)

        self.trigger_widgets: dict[str, "PluginConfigWidget"] = {}
        for plugin_id, plugin in self.plugin_manager.triggers.items():
            plugin_widget = PluginConfigWidget(plugin_id, plugin.name, plugin.config_path)
            self.trigger_widgets[plugin_id] = plugin_widget
            self.plugins_layout.addWidget(plugin_widget)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        self.plugins_layout.addWidget(separator)

        # Tools section
        tools_label = QLabel("<b>Tools</b>")
        self.plugins_layout.addWidget(tools_label)

        self.tool_widgets: dict[str, "PluginConfigWidget"] = {}
        for plugin_id, plugin in self.plugin_manager.tools.items():
            plugin_widget = PluginConfigWidget(plugin_id, plugin.name, plugin.config_path)
            self.tool_widgets[plugin_id] = plugin_widget
            self.plugins_layout.addWidget(plugin_widget)

        self.plugins_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return widget

    def _create_device_tab(self) -> QWidget:
        """Create the device info tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Device info group
        info_group = QGroupBox("Device Information")
        info_layout = QFormLayout(info_group)
        info_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        device_id_edit = QLineEdit(self.device_info.device_id)
        device_id_edit.setReadOnly(True)
        device_id_edit.setMinimumWidth(350)
        info_layout.addRow("Device ID:", device_id_edit)

        platform_edit = QLineEdit(self.device_info.get_platform())
        platform_edit.setReadOnly(True)
        info_layout.addRow("Platform:", platform_edit)

        hostname_edit = QLineEdit(self.device_info.get_hostname())
        hostname_edit.setReadOnly(True)
        info_layout.addRow("Hostname:", hostname_edit)

        layout.addWidget(info_group)

        # System info group
        sys_info = self.device_info.get_system_info()
        sys_group = QGroupBox("System Information")
        sys_layout = QFormLayout(sys_group)
        sys_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for key, value in sys_info.items():
            if key not in ("platform", "hostname"):
                edit = QLineEdit(str(value))
                edit.setReadOnly(True)
                edit.setMinimumWidth(350)
                sys_layout.addRow(f"{key.replace('_', ' ').title()}:", edit)

        layout.addWidget(sys_group)

        layout.addStretch()
        return widget

    def _load_settings(self) -> None:
        """Load current settings into the UI."""
        # General settings
        self.server_url_edit.setText(self.config_manager.get("server_url", ""))
        self.device_key_edit.setText(self.config_manager.get("device_key", ""))
        self.auto_connect_check.setChecked(self.config_manager.get("auto_connect", True))
        self.reconnect_spin.setValue(self.config_manager.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL_MS))

        log_level = self.config_manager.get("log_level", "INFO")
        index = self.log_level_combo.findText(log_level)
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)

        # Check link status
        self._update_link_status()

        # Plugin settings are loaded by PluginConfigWidget

    def _validate_server_url(self, url: str) -> tuple[bool, str]:
        """
        Validate server URL format.

        Returns:
            (is_valid, error_message) tuple
        """
        if not url or not url.strip():
            return False, "Server URL cannot be empty"

        try:
            parsed = urlparse(url)

            if not parsed.scheme:
                return False, "Server URL must include http:// or https://"

            if parsed.scheme not in ("http", "https"):
                return False, f"Invalid URL scheme '{parsed.scheme}'. Must be http or https"

            if not parsed.netloc:
                return False, "Server URL must include a hostname"

            return True, ""

        except Exception as e:
            return False, f"Invalid URL format: {e}"

    def _validate_device_key(self, device_key: str) -> tuple[bool, str]:
        """
        Validate device key.

        Returns:
            (is_valid, error_message) tuple
        """
        # Device key can be empty, but if provided should be reasonable length
        stripped = device_key.strip() if device_key else ""
        if stripped and len(stripped) < 10:
            return False, "Device Key must be at least 10 characters if provided"

        return True, ""

    def _save_settings(self) -> None:
        """Save settings from the UI with validation."""
        # Validate server URL
        server_url = self.server_url_edit.text().strip()
        valid, error = self._validate_server_url(server_url)
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            self.tabs.setCurrentIndex(0)  # Switch to General tab
            self.server_url_edit.setFocus()
            return

        # Validate device key
        device_key = self.device_key_edit.text().strip()
        valid, error = self._validate_device_key(device_key)
        if not valid:
            QMessageBox.warning(self, "Validation Error", error)
            self.tabs.setCurrentIndex(0)  # Switch to General tab
            self.device_key_edit.setFocus()
            return

        # Save general settings
        self.config_manager.set("server_url", server_url)
        self.config_manager.set("device_key", device_key)
        self.config_manager.set("auto_connect", self.auto_connect_check.isChecked())
        self.config_manager.set("reconnect_interval", self.reconnect_spin.value())
        self.config_manager.set("log_level", self.log_level_combo.currentText())
        self.config_manager.save()

        # Save plugin settings
        for widget in list(self.trigger_widgets.values()) + list(self.tool_widgets.values()):
            widget.save_config()

        logger.info("Settings saved")
        self.settings_changed.emit()

    def _update_link_status(self) -> None:
        """Update the link status display."""
        is_linked = self.config_manager.get("device_linked", False)
        if is_linked:
            self.link_status_label.setText("Linked ✓")
            self.link_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.link_btn.setText("Unlink Device")
        else:
            self.link_status_label.setText("Not linked")
            self.link_status_label.setStyleSheet("color: gray;")
            self.link_btn.setText("Link Device")

    def _on_link_device(self) -> None:
        """Handle link/unlink device button click."""
        is_linked = self.config_manager.get("device_linked", False)

        if is_linked:
            # Unlink device
            self.config_manager.set("device_linked", False)
            self.config_manager.save()
            self._update_link_status()
            logger.info("Device unlinked")
        else:
            # Link device
            self._do_link_device()

    def _do_link_device(self) -> None:
        """Perform the device linking operation."""
        server_url = self.server_url_edit.text().strip()
        device_key = self.device_key_edit.text().strip()

        if not server_url:
            QMessageBox.warning(self, "Link Device", "Please enter Server URL first.")
            return

        if not device_key:
            QMessageBox.warning(self, "Link Device", "Please enter Device Key first.")
            return

        # Update UI to show linking in progress
        self.link_btn.setEnabled(False)
        self.link_status_label.setText("Linking...")
        self.link_status_label.setStyleSheet("color: orange;")

        # Run the async link operation
        self._create_task(self._link_device_async(server_url, device_key))

    async def _link_device_async(self, server_url: str, device_key: str) -> None:
        """Async operation to link device with server."""
        try:
            url = f"{server_url.rstrip('/')}{ENDPOINT_DEVICE_LINK}"
            payload = {
                "deviceId": self.device_info.device_id,
                "deviceOs": self.device_info.get_platform(),
                "deviceName": self.device_info.get_hostname(),
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": CONTENT_TYPE_JSON,
                        HEADER_DEVICE_AUTH: device_key
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        self.config_manager.set("device_linked", True)
                        self.config_manager.save()
                        self._update_link_status()
                        logger.info("Device linked successfully")
                    else:
                        body = await response.text()
                        error_message = "Link failed"
                        try:
                            error_data = json.loads(body)
                            if "error" in error_data and "message" in error_data["error"]:
                                error_message = error_data["error"]["message"]
                        except json.JSONDecodeError:
                            pass
                        logger.error(f"Link failed: {response.status} - {body}")
                        self.link_status_label.setText(error_message)
                        self.link_status_label.setStyleSheet("color: red;")

        except asyncio.TimeoutError:
            logger.error("Link request timed out")
            self.link_status_label.setText("Timeout")
            self.link_status_label.setStyleSheet("color: red;")

        except aiohttp.ClientError as e:
            logger.error(f"Link request failed: {e}")
            self.link_status_label.setText("Connection error")
            self.link_status_label.setStyleSheet("color: red;")

        except Exception as e:
            logger.error(f"Unexpected error during link: {e}")
            self.link_status_label.setText("Error")
            self.link_status_label.setStyleSheet("color: red;")

        finally:
            self.link_btn.setEnabled(True)


class PluginConfigWidget(QGroupBox):
    """Widget for configuring a single plugin."""

    def __init__(self, plugin_id: str, plugin_name: str, config_path: Path):
        super().__init__(plugin_name)
        self.plugin_id = plugin_id
        self.config_path = config_path
        self._config: dict = {}

        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)

        # Enabled checkbox
        self.enabled_check = QCheckBox("Enabled")
        layout.addWidget(self.enabled_check)

        # Config editor
        self.config_edit = QTextEdit()
        self.config_edit.setMaximumHeight(100)
        self.config_edit.setPlaceholderText("Plugin configuration (JSON)")
        layout.addWidget(self.config_edit)

    def _load_config(self) -> None:
        """Load plugin configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)

                self.enabled_check.setChecked(self._config.get("enabled", True))
                self.config_edit.setPlainText(json.dumps(self._config, indent=2, ensure_ascii=False))
            except Exception as e:
                logger.error(f"Failed to load plugin config {self.config_path}: {e}")

    def save_config(self) -> None:
        """Save plugin configuration."""
        try:
            # Parse the edited JSON
            config_text = self.config_edit.toPlainText()
            if config_text.strip():
                self._config = json.loads(config_text)

            # Update enabled state
            self._config["enabled"] = self.enabled_check.isChecked()

            # Save to file
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved plugin config: {self.plugin_id}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in plugin config {self.plugin_id}: {e}")
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                f"Plugin '{self.plugin_id}' has invalid JSON configuration: {e}"
            )
        except Exception as e:
            logger.error(f"Failed to save plugin config {self.plugin_id}: {e}")
