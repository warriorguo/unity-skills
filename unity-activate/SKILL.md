---
name: unity-activate
description: Bring a running Unity Editor window to the front by matching the project name in its window title (case-insensitive substring). Use this skill whenever the user wants to switch focus to a specific already-open Unity project — phrases like "激活 X 的 Unity"、"切到 X 项目的 Unity 窗口"、"focus the Unity for Y"、"open the X Unity window"、"jump to the Unity editing X", or any time the user wants to bring a particular Unity Editor window to the foreground among multiple running Unity instances. macOS only. Triggers even when the user doesn't say the word "window" — "open my OZX Unity" or "切到 RoomTemplate" while Unity is running should fire this skill.
---

# unity-activate

Focus a running Unity Editor window whose title contains a given substring. Useful when several Unity projects are open and the user wants to jump to a specific one without alt-tabbing through them.

## How Unity exposes itself on macOS

Each open Unity project runs as its own process named `Unity` (Unity Hub is a separate process named `Unity Hub` and is ignored here). The main editor window's title contains the project name, for example:

```
RoomTemplate - SampleScene - PC, Mac & Linux Standalone - Unity 2022.3.21f1
```

So matching the project name against window titles is enough to identify the right Unity instance.

## Usage

Run the bundled script with the project name (or any substring of it):

```bash
bash <skill-dir>/scripts/activate_unity.sh "<project-name>"
```

The script's working directory doesn't matter — invoke it by absolute path.

Examples:

- `activate_unity.sh "RoomTemplate"` — raises the Unity window whose title contains `RoomTemplate`.
- `activate_unity.sh "ozx"` — matches any project window containing `ozx` (case-insensitive). If several windows match, the first is raised and the others are listed with their PIDs so the user can target a specific one.

To inspect what's available without activating anything:

```bash
bash <skill-dir>/scripts/activate_unity.sh --list
```

Each `--list` line is `pid=<N>  <window title>`. Note that Unity's batchmode helper processes (`AssetImportWorker`, etc.) also report as `Unity` to the OS but own no windows, so they don't appear here.

To activate a specific Unity process directly by PID (useful when two projects have identical titles):

```bash
bash <skill-dir>/scripts/activate_unity.sh --pid <PID>
```

## Interpreting output

The script writes exactly one of these to stdout:

| Output | Meaning | What to tell the user |
|---|---|---|
| `ACTIVATED: pid=<N>  <title>` | Single window matched and was raised. | Confirm briefly which window was raised. |
| `ACTIVATED: pid=<N>  <title> (and N other matches)` + `also matches: pid=… …` lines | First match raised, but the substring was ambiguous. | Tell the user which one was raised AND list the others — they may have wanted a different one. Offer to re-run with `--pid <N>` if they want a specific instance, or a more specific substring. |
| `ACTIVATED_PROC: pid=<N> (no windows reported)` | `--pid` mode: process was found and frontmost set, but no windows enumerated (Unity may still be loading). | Probably fine; suggest retry if the window doesn't come forward. |
| `NO_MATCH` | Unity is running but no window title contains the substring. | Suggest the user re-check the project name, or `--list` to see what's open. Possibly the project isn't open in Unity yet — in that case point them to Unity Hub (this skill does not launch new projects). |
| `NO_UNITY` | No Unity Editor process is running at all (Unity Hub alone doesn't count). | Tell the user to open the project from Unity Hub first. |
| `NO_SUCH_PID` | `--pid` mode: no process exists with that PID. | Suggest `--list` to see current PIDs. |
| `NOT_UNITY: <name>` | `--pid` mode: PID exists but it's not a Unity process. | Tell the user the PID they passed isn't Unity. |
| `NO_WINDOWS` | `--list` mode only: Unity is running but reports no windows (rare; usually means it's still launching). | Suggest retrying in a few seconds. |

## When matching is ambiguous

If the user's substring matches more than one window (e.g., they said "Unity" or "OZX" and several projects qualify), the script raises the first match and lists the alternates with their PIDs. Show the alternates to the user — don't silently pick. They can re-invoke with a more specific substring, or with `--pid <N>` to target a specific instance directly (useful when two open projects share an identical title, e.g. multiple worktrees of the same repo).

## Accessibility permission (one-time setup)

This script drives the OS via AppleScript and needs the macOS **Accessibility** permission for whichever process invokes it (Claude Code, Terminal.app, iTerm, etc.). If you see this error:

```
execution error: System Events got an error: osascript is not allowed assistive access. (-25211)
```

…stop and walk the user through the fix instead of retrying:

1. Open **System Settings → Privacy & Security → Accessibility**
2. Click the **+** button and add the app that's running the script (most often "Claude Code", or the terminal emulator like Terminal/iTerm/Warp/Ghostty).
3. Toggle it on. Restart the app if it was already open.
4. Re-run the skill.

This is a one-time grant — subsequent runs work without prompting.

## What this skill does NOT do

- **Does not launch Unity** for projects that aren't open. Unity Hub is the right tool for that, or `open -a "Unity Hub"`.
- **Does not activate Unity License.** It only switches focus among already-running editors.
- **Does not work on Windows or Linux** — it's AppleScript/macOS-only.

If the user asks for any of these, say so clearly and stop — don't try to fudge the script into doing something it doesn't.
