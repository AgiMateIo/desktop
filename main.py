#!/usr/bin/env python3
"""Main entry point for Agimate Desktop.

Uses dependency injection architecture with EventBus for decoupled communication.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path before imports
if not getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(__file__).parent
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from core.di_container import ContainerBuilder
from core.application import Application

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    # Create Qt application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Create async event loop
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Build DI container
    logger.info("Building DI container...")
    container = ContainerBuilder.build_container(app, loop)

    # Create application with dependencies
    logger.info("Creating application...")
    application = Application(
        config_manager=container.get("config_manager"),
        device_info=container.get("device_info"),
        plugin_manager=container.get("plugin_manager"),
        server_client=container.get("server_client"),
        tray_manager=container.get("tray_manager"),
        event_bus=container.get("event_bus"),
        app=app,
        loop=loop
    )

    # Run application
    with loop:
        try:
            loop.run_until_complete(application.run())
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            loop.run_until_complete(application._shutdown())


if __name__ == "__main__":
    main()
