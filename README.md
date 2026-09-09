# OmaSpace

Organize your desktop. Remember your setup.

A keyboard-controlled workspace overview for Omarchy and Hyprland. Press **Super + Up** to see every workspace over a blurred desktop, inspect window previews, move windows, exchange window positions, or move a whole workspace while keeping its layout intact.

Built with Quickshell and the Python standard library. This is an early release, tested with Hyprland **0.56.2**, Quickshell **0.3.1**, and Python **3.14**. It includes an Omarchy shell service to keep workspace indicators synchronized.

## Get started

Requires an Omarchy desktop with the Lua-based Hyprland configuration and the installed Omarchy shell. Run inside your Hyprland session:

```sh
git clone https://github.com/rubengarciajr/omaspace.git
cd omaspace
python scripts/install.py
```

Press **Super + Up**, choose a workspace, press **M**, choose its destination, then press **Enter**. An occupied destination swaps places with the source. Press **comma (,)** for window management and session settings.

The installer replaces Super+Up's default “Focus on above window” shortcut and enables session memory with restore at login. Backups are kept in `.backups/`. See the restore limitations below; a physical reboot has not yet been tested.

## Your desktop

The overview detects available displays and reads their live workspace assignments. On the laptop alone, its main grid shows **1–5**. Connecting the external monitor adds its configured **6–10** workspaces (the **0** key is 10). An active iPad stream adds the workspaces assigned to that output. Empty workspaces belonging to unavailable displays are hidden in both the switcher and Settings. Scratchpad and occupied extra workspaces stay accessible under **Other open**, so windows are never lost from the overview. Display resolution and scale follow your existing configuration.

Appearance uses the installed Omarchy shell's shared `Color` and `Style` components directly:

- Borders read Hyprland's live `general:border_size`, including selected cards; corners read `decoration:rounding`. Zero values are respected.
- Font family follows the system monospace alias managed by `omarchy font set`, with Omarchy's `OMARCHY_MENU_FONT` override honored.
- Text sizes use Omarchy's caption/body/heading tokens. The global text-size setting and `[font]` overrides in `~/.config/omarchy/shell.toml` apply here too. Layout spacing scales through Omarchy's shared spacing system.
- Colors and theme style overrides come from the current Omarchy theme, with the shell's normal machine-level overrides applied.

These values refresh on opening and every two seconds while idle and visible; the shared user style file also reloads when edited. OmaSpace does not maintain separate border, radius, or font-size defaults. Previews use native Wayland screencopy and refresh every 1.5 seconds while visible; they are not saved to disk.

## Two screens

**Super+Up opens the compact switcher.** It has workspace previews, Switch, and Move. Available displays have separate rows; scratchpad and occupied extra workspaces stay available as small buttons.

| Switcher key | Action |
| --- | --- |
| Arrows / 1–9, 0 | Select a workspace |
| Enter | Switch to it |
| M (or W) | Pick up the selected workspace |
| Destination number → Enter | Move there; swap if occupied |
| Ctrl+Z | Undo the last move |
| Comma (,) | Open Settings |
| Escape | Cancel a move or close |

**Settings** opens the larger panel for individual-window management, session save/restore, and startup preferences. Escape returns to the compact switcher.

After a whole-workspace move, the selected card follows the destination. Older layout queries are discarded, and a fresh query follows the completed action. The installed `omaspace.workspace-sync` background service refreshes Omarchy's workspace and monitor cache when Hyprland changes workspace IDs, keeping the bar's active indicator aligned with the actual workspace. Existing user clones of the standard workspace widget use Hyprland's native window count to avoid stale occupancy after swaps; packaged widgets are never modified.

## Settings panel keyboard

| Key | Action |
| --- | --- |
| Super + Up | Open / close OmaSpace |
| Arrow keys or H J K L | Select a workspace or window |
| 1–9, 0 | Select workspace 1–10; in Windows view select window 1–10 |
| Tab | Switch Workspaces / Windows |
| Space | Inspect the selected workspace's windows |
| Enter | Focus selected window / workspace and close overview |
| M | Move selected window; choose destination, then Enter |
| W | Move whole workspace; choose destination, then Enter |
| X | Swap selected window's position with another tiled window |
| Ctrl + Z | Undo the last move / swap in this app instance |
| S | Save the current display profile and pin its manual checkpoint |
| R | Restore the current display profile; P in this dialog restores its manual checkpoint |
| A | Toggle automatic restore at login |
| Escape | Cancel dialog, return to workspace view, then close |

Mouse selection, double-click activation, and all visible buttons work too. The destination grid follows available displays and occupied extra workspaces. Number keys cannot select hidden destinations; use arrows for numbers above 10.

**Example — move workspace 1 to 6:** Super+Up → 1 → M → 6 → Enter. If 6 is occupied, the two workspaces exchange places. Each whole layout moves to the destination display. Nothing is merged or closed. The dialog states this before applying; Ctrl+Z reverses the exchange.

**Example — move a window from workspace 6 to 1:** Super+Up → comma → 6 → Tab → select window → M → 1 → Enter.

Super+Up previously ran Omarchy's “Focus on above window” binding; OmaSpace explicitly unbinds that before registering its shortcut.

## Remembering a session

**Each display combination has its own profile.** Laptop, laptop + external monitor, laptop + iPad, and all three displays keep independent layouts, manual checkpoints, histories, and restore reports. The detected profile appears in the switcher and Settings. Press **S / Save profile** to remember the current setup, or **R / Restore** to restore it. Profiles are keyed by sorted output names, so changes to numeric monitor IDs, enumeration order, resolution, or scale do not select a different profile.

The installer saves the current setup if it has no profile yet. A user systemd service saves window size, floating, and fullscreen changes after they have stayed stable for two seconds (typically within 2–4 seconds including polling). App launches, closures, and workspace moves keep a 15-second settling period. It retains 20 historical snapshots per profile and never replaces a save with an empty desktop. **S** saves immediately and preserves a separate manual checkpoint for the current profile. **Restore latest / R** uses the latest saved positions and sizes; **P** deliberately restores the older manual checkpoint. Settings shows the latest save time and the restore dialog dates both versions.

Connecting or disconnecting a display selects its matching profile. After the connection has settled for five seconds, **Auto-switch: on** restores that profile if one exists. Turn this off in Settings to select profiles while keeping windows where they are. New setups begin with the current arrangement and get their own checkpoints. A save or restore interrupted by a display change cannot overwrite another profile. Laptop saves include windows on available displays; windows left on an unavailable virtual display remain accessible in Other open.

At login, the service waits 25 seconds for normal autostarts and monitor mapping, then restores only the matching profile. **Login [A]** controls login restore independently of Auto-switch. Existing legacy saves and manual checkpoints are copied into profiles for their recorded display combinations, with the original files retained.

The virtual **iPad** output is considered available only while Sunshine reports a connected client in its current service invocation. An idle headless output alone does not add workspaces. Detection supports `app-dev.lizardbyte.app.Sunshine.service` and `sunshine.service` in the user session. For a different virtual-display setup, configure `~/.config/omaspace/displays.json`, for example `{"virtual": {"iPad": "sunshine"}}`. Virtual entries can use `sunshine`, `on` (count whenever Hyprland exposes it), or `off` (exclude it). Physical outputs are detected directly through Hyprland.

Restore matches existing windows first, launches missing applications through their installed desktop entries, waits for new windows, places them on their workspaces, reconstructs compatible **dwindle** split trees and proportions, and restores floating geometry and fullscreen state. Windows created by a previous app launch are reused as well. Extra tiled windows on restored workspaces move to an unused numbered workspace, which is reported in the result; floating extras stay in place. Exact title matches are reserved before matching other windows of the same app. If a restore is incomplete (including layout warnings), checkpoints pause so the original session remains available; manually saving accepts the current desktop and resumes checkpoints.

Boundaries:

- Applications manage their own browser tabs, documents, login state, and unsaved contents. OmaSpace does not recreate terminal commands, tmux jobs, or process memory; terminals reopen fresh shells.
- Exact native tiling recovery supports binary dwindle layouts. Other tiling engines and overlapping/tabbed layouts keep compositor tiling and report the limitation. App minimum sizes may constrain geometry.
- Scratchpads are visible and individual windows can be moved from them. Omarchy's preloader owns scratchpad startup, so OmaSpace does not relaunch scratchpad windows.
- Pinned windows must be unpinned before moving; swapping positions requires tiled windows.
- A different display combination selects a separate profile. It does not restore the layout saved for missing displays. Workspace assignments still follow your existing Omarchy monitor rules.
- Relaunch requires a matching installed desktop entry. Failed/missing launchers are reported. Multi-window singleton applications may choose to open fewer windows than requested.
- Tested restore using real temporary windows, including reopening a closed application and matching saved geometry. A physical reboot has **not** been performed.

For custom apps, add explicit argument arrays keyed by window class to `~/.config/omaspace/launchers.json`, for example:

```json
{
  "my-app": ["/absolute/path/to/my-app", "--new-window"]
}
```

Only add commands you intend to launch. Commands from terminal process histories are never inferred or replayed.

## Install and operate

Run from this directory:

```sh
python scripts/install.py
```

The installer checks for the required Lua dispatcher and installed Omarchy shell style components, installs a user-owned Hyprland module, desktop launcher, and session service, and validates `hyprctl reload` / `configerrors`. It does not modify packaged Omarchy files. Package dependencies are `quickshell`, `python`, `glib2`, and `fontconfig` plus a compatible Hyprland and Omarchy shell at `/usr/share/omarchy/shell`.

```sh
omaspace open
omaspace close
omaspace save
omaspace restore
omaspace restore-pinned
omaspace move-window 0xADDRESS 6
omaspace move-workspace 1 6
omaspace settings autoRestore false
omaspace settings autoProfileRestore false
systemctl --user status omaspace-session.service
journalctl --user -u omaspace-session.service
```

The installer links `~/.local/bin/omaspace` to this checkout. New XDG config/state directories link to `.local/config` and `.local/state` here; existing OmaOrder data is reused when present. Profiles live in `~/.local/state/omaspace/profiles/<profile-id>/`, each with `session.json`, `pinned-session.json`, and `history/`. State files are mode 0600 inside mode 0700 directories. They contain private window titles and application paths, and are gitignored. Live configuration backups are in `.backups/`, also gitignored. Keep this checkout in place while the app is installed.

Uninstall integration while retaining snapshots and source:

```sh
python scripts/uninstall.py
```

## Checks

```sh
python -m unittest discover -s tests -v
python scripts/live-check.py --ui
python scripts/check-return-move.py
python scripts/check-return-move.py --occupied
```

The integration check requires **empty workspaces 4 and 7** with an external display, or **4 and 5** on the laptop alone, creates uniquely identified temporary Foot windows, checks moves and swaps (across monitors when available), reopens a missing window, compares resized tiled and floating geometry, and verifies prompt background resize saving in an isolated profile. It closes only its own fixtures and restores the original view. Stop the session service before running it and start it afterward so fixtures do not enter checkpoints.

Implementation references: [Hyprland Lua dispatchers](https://wiki.hypr.land/Configuring/Basics/Dispatchers/), [Dwindle layout](https://wiki.hypr.land/Configuring/Layouts/Dwindle-Layout/), [Quickshell screencopy](https://master.quickshell.org/docs/types/Quickshell.Wayland/ScreencopyView). The installed Lua API and Hyprland v0.56.2 source were also checked for version-specific behavior.

The return-move regression uses temporary workspaces 94/95, automatically pauses/resumes session memory, and verifies three moves out and back across popup reopenings without relocating existing windows. It checks both the popup and the installed Omarchy sync service against native focused workspace, monitor workspace IDs and window counts. `--occupied` fills both workspaces to test swaps. The installer enables the sync service and backs up the shell configuration and any adjusted user workspace widget; uninstall reverses those adjustments.
