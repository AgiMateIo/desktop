# Changelog

## [0.3.0] - 2026-08-28

### Added
- AgiMate visual identity v1 throughout the interface: the connector mark, the
  warm-neutral palette with its teal accent, and one stylesheet built from the
  identity's tokens (`ui/branding.py`)
- Tray icon says the connection state by form — an empty port against an
  occupied one — and is a template icon in the macOS menu bar
- App icons for all three platforms, generated from the brand tile by
  `python build.py icons` rather than drawn by hand
- Binary tool results are uploaded as files and returned as an `agf_` id
  instead of base64 in the output

### Changed
- The app reports its real version to the backend; it had been hardcoded to
  `1.0.0` since the first release
- The Device tab scrolls, so a long system-information list no longer squeezes
  its rows until the text clips

### Fixed
- Duplicate tool calls: Centrifugo delivers at least once, and a call
  re-delivered on reconnect used to run twice
- The `X-App-Auth-Key` header no longer reaches the logs — `repr()` of an
  aiohttp error embedded the whole request, header included
- Duplicate Centrifugo clients, and modal dialogs that blocked the event loop
- Stale README links and the stated license (Apache-2.0, not MIT)

## [0.2.0] - 2026-07-16

### Added
- New tool plugins: Screenshot (fullscreen / window / region), System Info,
  Window List
- Local MCP server exposing desktop tools via Streamable HTTP
  (`get_pending_triggers` for trigger polling)

### Changed
- Tool/trigger declarations aligned with the app-connector spec: bare
  snake_case names (`tts_speak`, `file_created`) and MCP-style descriptors
  (`title`, `description`, `inputSchema`/`paramsSchema`, `outputSchema`,
  `annotations`)
- "Actions" renamed to "tools" throughout; API endpoints restructured to match
  the backend contract (`/app/registration/link`, `/app/tools/result`,
  `/app/trigger/new`)
- Tool results are correlated by the server-issued tool call id
- Project migrated to uv (`pyproject.toml` + `uv.lock`)

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
