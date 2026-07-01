# app/network/iperf.py
#
# Bandwidth testing via the bundled iperf2 binary. Mirrors the structure of
# ping.py: a streaming generator that yields output line-by-line as the
# subprocess produces it, with robust process cleanup on consumer disconnect.
#
# WHY iperf2 (and not iperf3): iperf3 has no native Win32 build — it only makes
# POSIX calls and ALWAYS needs cygwin1.dll at runtime (which is GPL and ~3 MB).
# iperf2 ships a native MinGW-static build that runs as a single self-contained
# .exe importing only Windows DLLs. License is BSD-style (NLANR/DAST,
# University of Illinois) — clean to bundle in the closed-source portable.
#
# The binary lives in python/bin/iperf2.exe and is packaged into the PyInstaller
# bundle via build_webview.spec (added_files: ('bin/*', 'bin')). At runtime we
# resolve it through sys.frozen/_MEIPASS, the same pattern remote_commands.py
# uses for the .ps1 scripts.

import os
import sys
import subprocess
import logging
from pathlib import Path

# Strong-signal multi-VLAN parity with ping: `-B <ip>` binds iperf2 to a
# specific source/listen IP, exactly like `-S` does for ping.exe. This is what
# makes the bandwidth test go out (client) or listen (server) on the right NIC
# on a machine sitting in multiple VLANs.

# Hard cap on a single client test duration. iperf2's own default is 10s; we
# allow up to this for a longer averaging window but never unbounded — an
# unbounded `-t` from a malformed request would pin a NIC indefinitely.
MAX_CLIENT_DURATION = 60

# Default port matches what operators expect from the iperf ecosystem.
DEFAULT_IPERF_PORT = 5201


def _iperf_binary():
    """Resolve the absolute path to the bundled iperf2 executable.

    Order:
      1. PyInstaller bundle: `_MEIPASS/bin/iperf2.exe`
      2. Dev source tree:    `python/bin/iperf2.exe`
      3. PATH fallback:      whatever `iperf2`/`iperf` resolves to (best-effort;
         lets a developer point at a system install if the bundled one is
         missing).

    Returns the path string, or None if nothing usable is found. Callers must
    handle None and surface a friendly "iperf não encontrado" rather than
    crashing.
    """
    exe_name = "iperf2.exe" if os.name == "nt" else "iperf2"

    candidates = []
    if getattr(sys, "frozen", False):
        # Running as the compiled portable. _MEIPASS is the unpack dir.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "bin" / exe_name)
    else:
        # Running from source: this file is python/src/network/iperf.py, so the
        # repo's python/ dir is three parents up.
        python_dir = Path(__file__).resolve().parent.parent.parent
        candidates.append(python_dir / "bin" / exe_name)

    for cand in candidates:
        try:
            if cand.is_file():
                return str(cand)
        except OSError as e:
            logging.debug(f"iperf binary candidate check failed for {cand}: {e}")

    # PATH fallback — try a couple of common names.
    from shutil import which
    for name in ("iperf2", "iperf"):
        found = which(name)
        if found:
            return found

    return None


def get_iperf_info():
    """Return availability + version of the iperf binary for the Settings/Tools
    UI. Never raises — a missing or non-runnable binary returns available=False
    so the frontend can disable the bandwidth tab with a clear message."""
    binary = _iperf_binary()
    if not binary:
        return {"available": False, "version": None, "path": None}

    version = None
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=5,
        )
        # iperf2 prints the version banner to stderr on some builds, stdout on
        # others — check both.
        banner = (result.stdout or "").strip() or (result.stderr or "").strip()
        if banner:
            version = banner.splitlines()[0].strip()
    except Exception as e:
        # Binary present but didn't run (missing DLL, AV quarantine, etc.).
        # Report unavailable so the UI degrades gracefully instead of letting a
        # later server/client launch fail mid-stream.
        logging.warning(f"iperf --version failed for {binary}: {e}")
        return {"available": False, "version": None, "path": binary}

    return {"available": True, "version": version, "path": binary}


def _build_creationflags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _stream_process(command):
    """Spawn `command` and yield (line, process) tuples as output arrives.

    First yield is ("", process) so the caller can register the process for
    cancellation BEFORE any output (mirrors continuous_ping's contract). On
    consumer close (GeneratorExit), terminate→kill the child so a long-running
    `iperf2 -s` server doesn't orphan when the client disconnects.
    """
    # iperf2's native Windows build emits cp850-ish console text; utf-8 with
    # errors='replace' is the safe choice across both OSes and never raises on a
    # stray byte.
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_build_creationflags(),
    )

    yield "", process
    try:
        for line in iter(process.stdout.readline, ""):
            yield line, process
    finally:
        # Same teardown discipline as continuous_ping: an iperf2 server never
        # exits on its own, so we must actively terminate it when the consumer
        # (StreamingResponse) goes away, or we leak one iperf2.exe per run.
        try:
            process.stdout.close()
        except Exception as e:
            logging.debug(f"iperf teardown: stdout.close failed: {e}")
        try:
            process.terminate()
        except Exception as e:
            logging.debug(f"iperf teardown: terminate failed: {e}")
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=2)
            except Exception as e:
                logging.debug(f"iperf teardown: kill failed: {e}")


def run_server(port=DEFAULT_IPERF_PORT, source_ip=None):
    """Run iperf2 in server mode, yielding (line, process) as clients connect
    and transfer. The app IS the destination — operators on other VLANs run
    `iperf2 -c <this_machine_ip> -p <port>` against it.

    `source_ip` binds the listen socket to a specific NIC (multi-VLAN), via -B.
    The server runs until the consumer closes the generator (Stop button →
    StreamingResponse disconnect → process terminated in _stream_process).
    """
    binary = _iperf_binary()
    if not binary:
        yield ("iperf não encontrado. O binário de teste de banda não está "
               "disponível nesta instalação.\n"), None
        return

    # -s server, -p port, -f m = report in Mbits/sec, -i 1 = 1s interval updates
    command = [binary, "-s", "-p", str(port), "-f", "m", "-i", "1"]
    if source_ip:
        command += ["-B", source_ip]

    yield from _stream_process(command)


def run_client(target, port=DEFAULT_IPERF_PORT, source_ip=None,
               duration=10, reverse=False, udp=False):
    """Run iperf2 in client mode against `target`, yielding (line, process).

    Tests bandwidth from this machine TO an existing iperf server on the
    network (the inverse of run_server).

    - `source_ip` (-B): egress NIC for multi-VLAN.
    - `duration` (-t): test length in seconds, clamped to [1, MAX_CLIENT_DURATION].
    - `reverse` (--reverse): server sends, client receives (download direction).
    - `udp` (-u): UDP test instead of TCP.
    """
    binary = _iperf_binary()
    if not binary:
        yield ("iperf não encontrado. O binário de teste de banda não está "
               "disponível nesta instalação.\n"), None
        return

    try:
        dur = int(duration)
    except (TypeError, ValueError):
        dur = 10
    dur = max(1, min(dur, MAX_CLIENT_DURATION))

    command = [binary, "-c", target, "-p", str(port), "-f", "m", "-i", "1",
               "-t", str(dur)]
    if source_ip:
        command += ["-B", source_ip]
    if reverse:
        # iperf2's reverse flag is the long form ONLY: `--reverse`. The short
        # `-R` is a DIFFERENT, dangerous option here — it means `--remove`
        # (uninstall the win32 service). Never use -R for reverse.
        command.append("--reverse")
    if udp:
        command.append("-u")

    yield from _stream_process(command)
