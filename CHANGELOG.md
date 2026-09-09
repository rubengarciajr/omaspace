# Changelog

## 2026-09-08 — Remember resized windows promptly

- Save settled window-size and floating/fullscreen-state changes within a few seconds; keep the longer startup/closure settling period.
- Include fullscreen state in change detection, and restore client fullscreen state even when compositor fullscreen is off.
- Show save times and distinguish Restore latest from the earlier manual checkpoint, which retains its original sizes until another manual save.
- Extend live checks to resize tiled windows in both directions, reopen a floating window at a custom size, and verify the background checkpoint without overwriting the manual save.

Validation: 35 unit tests passed. Live keyboard restore reproduced all four saved window geometries exactly; the isolated daemon saved a fresh resize in 3.2 seconds. No physical reboot performed for this update.

## 2026-09-08 — Display profiles and automatic workspace detection

- Show only workspaces assigned to available displays in both main grids; keep scratchpad and occupied extras in a separate Other open area.
- Detect the iPad virtual display through a connected Sunshine client instead of counting an idle headless output.
- Store independent layouts, manual checkpoints, history, and restore reports for each display combination. Preserve and migrate legacy saves.
- Automatically select profiles as displays change and optionally restore them after a five-second settling period. Login restore has its own toggle.
- Protect profiles when displays change during save/restore, and prevent keyboard navigation to hidden destinations.
- Show the detected profile and saved setups in Settings; save the initial laptop profile.

Validation: 30 unit tests passed, including laptop/external/iPad detection, profile isolation, migration, and hotplug debounce. Live laptop popup checks verified five main workspaces in both screens, hidden-key handling, and four restored fixture geometries. Physical external-monitor/iPad reconnection and reboot remain to be tested.

## 2026-09-07 — Restore saved window placement

- Move extra tiled startup windows to an unused numbered workspace so they no longer prevent reconstruction of the saved layout. Report their destination and record recovery details locally.
- Keep floating extras in place without blocking tiling restoration.
- Reserve exact window-title matches before falling back to other windows of the same application.
- Pause automatic checkpoints when layout restoration is incomplete, protecting the saved arrangement until a successful retry or manual save.
- Update the restore dialog and README to explain the behavior.

Validation: all 15 unit tests passed. Live CLI and keyboard-driven popup checks reopened a missing app, relocated an extra startup window, and restored all four saved window geometries exactly. Physical reboot testing remains outstanding.
