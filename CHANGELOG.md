# Changelog

## [1.3.0] - 2026-03-23

### Added
- Headless-friendly `RecordingService` for unified start/stop/pause/status flow.
- Domain event bus (`core/event_bus.py`) for recording lifecycle events.
- Real-time event manager (`api/websocket.py`) ready for WebSocket/SSE transport.
- API endpoints for recent events and event stats:
  - `GET /api/events/recent`
  - `GET /api/events/stats`
- Observability endpoints:
  - `GET /api/observability/metrics`
  - `GET /api/observability/baseline`
- New unit tests for recording service and event layer.

### Changed
- Screen capture backend migrated to `windows-capture` (removed `mss` usage).
- API server lifecycle improved with managed waitress shutdown.
- API error payload standardized to a unified contract:
  `success=false`, `error={code,message,details}`, `trace_id`.
- Atomic persistence for config and scheduler task files.
- Health endpoint `GET /health` extended with `version`, `uptime_seconds`
  and real-time transport stats (`websocket`).
- Updated app version metadata to `1.3.0`.

### Reliability
- Strengthened API rate limiting coverage on write endpoints.
- Expanded integration and unit test coverage for API/server/recorder/scheduler paths.
- Stabilized Windows test teardown for temporary directories in CI.

### Automation
- CI expanded to Python matrix (`3.10`, `3.11`) on Windows.
- Added non-blocking security audit job (`pip-audit`) in CI.
- Added tag-based release workflow (`v*`) with build artifacts and `SHA256SUMS`.
