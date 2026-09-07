# Changelog

## 2026-09-07 — Restore saved window placement

- Move extra tiled startup windows to an unused numbered workspace so they no longer prevent reconstruction of the saved layout. Report their destination and record recovery details locally.
- Keep floating extras in place without blocking tiling restoration.
- Reserve exact window-title matches before falling back to other windows of the same application.
- Pause automatic checkpoints when layout restoration is incomplete, protecting the saved arrangement until a successful retry or manual save.
- Update the restore dialog and README to explain the behavior.

Validation: all 15 unit tests passed. Live CLI and keyboard-driven popup checks reopened a missing app, relocated an extra startup window, and restored all four saved window geometries exactly. Physical reboot testing remains outstanding.
