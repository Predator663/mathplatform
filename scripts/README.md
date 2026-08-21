# MathPlatform - background start/stop scripts (Windows)

Runs the Django backend and the Vite frontend in the background (no
terminal windows), so you can just open Chrome to `http://localhost:5173`
instead of manually running two dev servers every day.

## One-time setup

Nothing to install - the scripts create the backend `venv` and run
`npm install` themselves on first launch.

## Everyday manual use

Double-click **`start.bat`** (project root). It:
- Starts the backend and frontend hidden in the background, if not already running
- Waits until both respond
- Opens Chrome to `http://localhost:5173`
- Is safe to double-click again - it detects servers already running and won't start a second copy

Double-click **`stop.bat`** to shut both down.
Double-click **`status.bat`** to check what's currently running.
Double-click **`restart.bat`** to cycle both (stop, then start, then open Chrome) - handy after pulling
new backend code or changing `.env`, since the running servers won't pick that up on their own.

All four render as a green-on-black "hacker" console (banner, boot-sequence checkmarks, an
animated spinner while waiting on the servers, a brief matrix-rain intro) rather than plain
text output. Set `MATHPLATFORM_NO_ANIMATION=1` as an environment variable first if you want the
same information instantly, with no animation delay (e.g. running one of these from another
script).

## Fully automatic - start at Windows login

To never think about this again:

1. Open PowerShell in `scripts/` and run:
   ```
   .\install_autostart.ps1
   ```
2. That's it. From your next login onward, MathPlatform starts silently
   in the background automatically - no window, no double-click. Give it
   ~20-30 seconds after logging in, then open Chrome to
   `http://localhost:5173`.

To undo: run `.\uninstall_autostart.ps1`.

By default the auto-started copy does **not** pop Chrome open on its own
(so it doesn't launch a browser tab every time you log in, even on days
you're not using it) - it just makes sure the servers are ready and
waiting for whenever you do open Chrome. If you'd rather it also open
Chrome automatically at login, edit `start_hidden.vbs` and add
`" -OpenChrome"` to the end of the `cmd = ...` line.

## Files

| File                      | Purpose                                                    |
|----------------------------|-------------------------------------------------------------|
| `start.ps1`                | Starts backend + frontend (idempotent), waits, optionally opens Chrome |
| `stop.ps1`                 | Stops both, with a fallback sweep of ports 8000/5173 for orphaned processes |
| `status.ps1`               | Quick check of what's running                               |
| `restart.ps1`              | Runs `stop.ps1` then `start.ps1`                              |
| `hacker_theme.ps1`         | Shared console theme (banner, spinner, matrix intro) used by all four above |
| `start_hidden.vbs`         | Runs `start.ps1` with zero visible window (used for autostart) |
| `install_autostart.ps1`    | Adds a shortcut to the Windows Startup folder                |
| `uninstall_autostart.ps1`  | Removes it                                                    |
| `run/*.pid`                | PIDs of the processes this script started (auto-generated)   |
| `logs/*.log`               | stdout/stderr from each server, for troubleshooting          |

## Notes

- Backend runs with `--noreload`. Django's autoreloader spawns a hidden
  child watcher process; if the main script only tracks the parent PID,
  `stop.ps1` could leave that child running as an orphan. A single
  predictable process is what you want for something running unattended
  in the background. If you're actively editing backend code and want
  live-reload, just run `backend/setup_backend.sh` (or `.bat`) manually
  in a terminal instead, like before.
- If port 8000 or 5173 is already in use by *something else* (not
  something this script started), it leaves that process alone rather
  than guessing and killing it - check `status.bat` if the app doesn't
  come up.
- Logs land in `scripts/logs/` - check them first if a server doesn't
  respond within the wait timeout.
