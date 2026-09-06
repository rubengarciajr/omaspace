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

The overview reads live monitors, clients, workspaces, and persistent workspace rules. Its initial layout was built for laptop workspaces **1–5** and external-monitor workspaces **6–10** (the **0** key is 10), with additional workspaces and the scratchpad available too. Configured empty workspaces remain visible, including those assigned to disconnected displays. Display resolution, scale, and workspace assignments are read from your existing setup.

Appearance uses the installed Omarchy shell's shared `Color` and `Style` components directly:

- Borders read Hyprland's live `general:border_size`, including selected cards; corners read `decoration:rounding`. Zero values are respected.
- Font family follows the system monospace alias managed by `omarchy font set`, with Omarchy's `OMARCHY_MENU_FONT` override honored.
- Text sizes use Omarchy's caption/body/heading tokens. The global text-size setting and `[font]` overrides in `~/.config/omarchy/shell.toml` apply here too. Layout spacing scales through Omarchy's shared spacing system.
- Colors and theme style overrides come from the current Omarchy theme, with the shell's normal machine-level overrides applied.

These values refresh on opening and every two seconds while idle and visible; the shared user style file also reloads when edited. OmaSpace does not maintain separate border, radius, or font-size defaults. Previews use native Wayland screencopy and refresh every 1.5 seconds while visible; they are not saved to disk.

## Two screens

**Super+Up opens the compact switcher.** It has workspace previews, Switch, and Move. Displays have separate rows; extra workspaces stay available as small buttons.

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
| S | Save session and pin a manual checkpoint |
| R | Review and restore the latest saved session; P in this dialog restores the manual checkpoint |
| A | Toggle automatic restore at login |
| Escape | Cancel dialog, return to workspace view, then close |

Mouse selection, double-click activation, and all visible buttons work too. The destination grid includes workspace 11 and any other numbered workspace; use arrows to reach numbers above 10.

**Example — move workspace 1 to 6:** Super+Up → 1 → M → 6 → Enter. If 6 is occupied, the two workspaces exchange places. Each whole layout moves to the destination display. Nothing is merged or closed. The dialog states this before applying; Ctrl+Z reverses the exchange.

**Example — move a window from workspace 6 to 1:** Super+Up → comma → 6 → Tab → select window → M → 1 → Enter.

Super+Up previously ran Omarchy's “Focus on above window” binding; OmaSpace explicitly unbinds that before registering its shortcut.

## Remembering a session

The installer saves the current desktop. A user systemd service records a new checkpoint after the desktop arrangement has stayed stable for 15 seconds. It retains 20 historical snapshots and never replaces a saved session with an empty desktop. **S** also preserves a separate manual checkpoint, accessible from the restore dialog.

At the next Hyprland login, `omaspace-start` supplies the compositor environment and starts the session service. It waits 25 seconds for normal Omarchy autostarts and monitor mapping, then restores once per compositor session. Turn this off with **Login [A]: restore on/off** in the sidebar.

Restore matches existing windows first, launches missing applications through their installed desktop entries, waits for new windows, places them on their workspaces, reconstructs compatible **dwindle** split trees and proportions, and restores floating geometry and fullscreen state. Windows created by a previous app launch are reused as well. Workspaces containing additional windows are not rebuilt. If a restore is incomplete, checkpoints pause so the original session remains available; manually saving accepts the current desktop and resumes checkpoints.

Boundaries:

- Applications manage their own browser tabs, documents, login state, and unsaved contents. OmaSpace does not recreate terminal commands, tmux jobs, or process memory; terminals reopen fresh shells.
- Exact native tiling recovery supports binary dwindle layouts. Other tiling engines and overlapping/tabbed layouts keep compositor tiling and report the limitation. App minimum sizes may constrain geometry.
- Scratchpads are visible and individual windows can be moved from them. Omarchy's preloader owns scratchpad startup, so OmaSpace does not relaunch scratchpad windows.
- Pinned windows must be unpinned before moving; swapping positions requires tiled windows.
- A missing monitor falls back to the available layout. Reconnecting displays follows your existing Omarchy monitor rules.
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
systemctl --user status omaspace-session.service
journalctl --user -u omaspace-session.service
```

The installer links `~/.local/bin/omaspace` to this checkout. New XDG config/state directories link to `.local/config` and `.local/state` here; existing OmaOrder data is reused when present. State files are mode 0600 inside mode 0700 directories. They contain private window titles and application paths, and are gitignored. Live configuration backups are in `.backups/`, also gitignored. Keep this checkout in place while the app is installed.

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

The integration check requires **empty workspaces 4 and 7**, creates uniquely identified temporary Foot windows, checks moves and swaps across monitors, reopens a missing window, and compares restored geometry. It closes only its own fixtures and restores the original view. Stop the session service before running it and start it afterward so fixtures do not enter checkpoints.

Implementation references: [Hyprland Lua dispatchers](https://wiki.hypr.land/Configuring/Basics/Dispatchers/), [Dwindle layout](https://wiki.hypr.land/Configuring/Layouts/Dwindle-Layout/), [Quickshell screencopy](https://master.quickshell.org/docs/types/Quickshell.Wayland/ScreencopyView). The installed Lua API and Hyprland v0.56.2 source were also checked for version-specific behavior.

The return-move regression uses temporary workspaces 94/95, automatically pauses/resumes session memory, and verifies three moves out and back across popup reopenings without relocating existing windows. It checks both the popup and the installed Omarchy sync service against native focused workspace, monitor workspace IDs and window counts. `--occupied` fills both workspaces to test swaps. The installer enables the sync service and backs up the shell configuration and any adjusted user workspace widget; uninstall reverses those adjustments.
