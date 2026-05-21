#!/usr/bin/env bash
# activate_unity.sh — bring a running Unity Editor window to the front by title substring.
#
# Usage:
#   activate_unity.sh <project-name-substring>    Activate first Unity window matching the substring.
#   activate_unity.sh --pid <pid>                  Activate the Unity process with that PID.
#   activate_unity.sh --list                       List every Unity Editor window with its PID.
#
# Matching is case-insensitive (AppleScript's default `contains` ignores case).
# macOS only. Requires Accessibility permission for whichever process invokes this
# script (Claude Code, Terminal, iTerm, …). If permission is missing osascript exits
# with `-25211` — direct the user to System Settings → Privacy & Security → Accessibility.
#
# Note: `every process whose name is "Unity"` matches headless helpers too
# (AssetImportWorker, batchmode workers). Those processes have no windows, so they're
# naturally filtered out by the per-PID lookup pattern below.

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <project-name-substring> | --pid <pid> | --list" >&2
  exit 2
fi

if [ "$1" = "--list" ]; then
  exec osascript <<'APPLESCRIPT'
tell application "System Events"
    set pidList to unix id of (every process whose name is "Unity")
end tell
if (count of pidList) is 0 then return "NO_UNITY"
set out to ""
repeat with pidRef in pidList
    set targetPid to pidRef as integer
    tell application "System Events"
        tell (first process whose unix id is targetPid)
            repeat with w in windows
                set out to out & "pid=" & (targetPid as text) & "  " & (name of w) & linefeed
            end repeat
        end tell
    end tell
end repeat
if out is "" then return "NO_WINDOWS"
return out
APPLESCRIPT
fi

if [ "$1" = "--pid" ]; then
  if [ "$#" -lt 2 ]; then
    echo "Usage: $0 --pid <pid>" >&2
    exit 2
  fi
  PID="$2"
  osascript - "$PID" <<'APPLESCRIPT'
on run argv
    set targetPid to (item 1 of argv) as integer
    tell application "System Events"
        set procs to every process whose unix id is targetPid
        if (count of procs) is 0 then return "NO_SUCH_PID"
        tell (first process whose unix id is targetPid)
            if (name of it) is not "Unity" then return "NOT_UNITY: " & (name of it)
            set wcount to count of windows
            set frontmost to true
            if wcount is 0 then return "ACTIVATED_PROC: pid=" & targetPid & " (no windows reported)"
            set targetWin to window 1
            try
                perform action "AXRaise" of targetWin
            end try
            return "ACTIVATED: pid=" & targetPid & "  " & (name of targetWin)
        end tell
    end tell
end run
APPLESCRIPT
  exit 0
fi

QUERY="$1"

osascript - "$QUERY" <<'APPLESCRIPT'
on run argv
    set q to item 1 of argv

    tell application "System Events"
        set pidList to unix id of (every process whose name is "Unity")
    end tell
    if (count of pidList) is 0 then return "NO_UNITY"

    -- Collect matches as {pid, windowName} pairs. We re-look-up the process when
    -- it's time to raise it; the System Events references from this discovery
    -- pass aren't reliable to hold onto (they re-resolve lazily).
    set matchList to {}
    repeat with pidRef in pidList
        set targetPid to pidRef as integer
        tell application "System Events"
            tell (first process whose unix id is targetPid)
                repeat with w in windows
                    set wname to name of w
                    if wname contains q then
                        set end of matchList to {targetPid, wname}
                    end if
                end repeat
            end tell
        end tell
    end repeat

    set matchCount to count of matchList
    if matchCount is 0 then return "NO_MATCH"

    set firstMatch to item 1 of matchList
    set winPid to item 1 of firstMatch
    set winName to item 2 of firstMatch

    -- Raise the matched window in a fresh tell-block.
    tell application "System Events"
        tell (first process whose unix id is winPid)
            set frontmost to true
            try
                -- Find the window by name and raise it.
                set targetWin to (first window whose name is winName)
                perform action "AXRaise" of targetWin
            end try
        end tell
    end tell

    if matchCount is 1 then
        return "ACTIVATED: pid=" & winPid & "  " & winName
    else
        set msg to "ACTIVATED: pid=" & winPid & "  " & winName & " (and " & (matchCount - 1) & " other matches)"
        repeat with i from 2 to matchCount
            set other to item i of matchList
            set msg to msg & linefeed & "  also matches: pid=" & (item 1 of other) & "  " & (item 2 of other)
        end repeat
        return msg
    end if
end run
APPLESCRIPT
