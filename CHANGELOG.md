# Changelog

## [0.1.1] - 2026-02-12

### Fixed
- Centrifugo WebSocket connection: use correct host (`centrifugo.{domain}`) and always use `wss://` for production domains
- Support server-provided `wsUrl` from token endpoint

## [0.1.0] - 2026-02-10

### Added
- Cross-platform system tray agent with plugin architecture
- Plugin system: triggers (File Watcher, Visual Buttons) and actions (Notifications, TTS)
- Centrifugo WebSocket connection for real-time server actions
- HTTP trigger sending with retry and exponential backoff
- Device linking and registration
- Settings UI (General, Plugins, Device tabs)
- DI container and EventBus architecture
- macOS DMG and Linux AppImage builds
- Apache 2.0 license
