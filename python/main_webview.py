import sys
import os
import threading
import webview
import uvicorn
import psutil
import time
import atexit
import signal
from api.server import app

def kill_port_process(port):
    """Kills process listening on the specified port if it looks like our server."""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                try:
                    process = psutil.Process(conn.pid)
                    proc_name = process.name().lower()
                    # Only kill if it's python or our built exe
                    if 'python' in proc_name or 'server' in proc_name or 'ferramentas' in proc_name:
                        print(f"Stopping existing server process {proc_name} (PID: {conn.pid}) on port {port}...")
                        process.terminate()
                        process.wait(timeout=3)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                except psutil.TimeoutExpired:
                    try:
                        process.kill()
                    except Exception as e:
                        print(f"Warning: failed to kill process on port: {e}")
    except Exception as e:
        print(f"Warning: Could not check port {port}: {e}")

def kill_child_processes(parent_pid, sig=signal.SIGTERM):
    """Recursively kills child processes."""
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return
    
    children = parent.children(recursive=True)
    for process in children:
        try:
            print(f"Terminating child process: {process.name()} (PID: {process.pid})")
            process.send_signal(sig)
        except psutil.NoSuchProcess:
            pass
            
    _, alive = psutil.wait_procs(children, timeout=3)
    for p in alive:
        try:
            print(f"Killing child process: {p.name()} (PID: {p.pid})")
            p.kill()
        except psutil.NoSuchProcess:
            pass

def cleanup():
    """Cleanup function to be called on exit."""
    print("Performing cleanup...")
    kill_child_processes(os.getpid())

def start_server():
    """Starts the FastAPI server in a separate thread.

    Respect NT_API_HOST / NT_API_PORT so the portable .exe matches the
    documented override surface (CLAUDE.md, TESTES.html). Default stays
    on loopback. The webview's static port is independent — see
    NT_WEBVIEW_PORT below."""
    host = os.environ.get("NT_API_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("NT_API_PORT", "8000"))
    except ValueError:
        port = 8000
    uvicorn.run(app, host=host, port=port, log_level="error")

def main():
    # Register cleanup on exit
    atexit.register(cleanup)

    # Ensure the API port is free (respects NT_API_PORT override).
    try:
        api_port = int(os.environ.get("NT_API_PORT", "8000"))
    except ValueError:
        api_port = 8000
    kill_port_process(api_port)
    
    # Start the backend server
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Determine the path to the frontend assets
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = sys._MEIPASS
        gui_path = os.path.join(base_path, 'gui', 'index.html')
    else:
        # Running from source (dev mode)
        # Assuming we are in python/ directory, and frontend is in electron/dist
        base_path = os.path.dirname(os.path.abspath(__file__))
        gui_path = os.path.join(base_path, '..', 'electron', 'dist', 'index.html')

    # Verify if the GUI file exists
    if not os.path.exists(gui_path):
        # Fallback to localhost if static files are not found (e.g. dev server)
        url = "http://localhost:5173"
    else:
        # Serve static files via a simple HTTP server in a thread.
        # We pin a fixed loopback port (default 5174) so the backend's CORS
        # whitelist can include it. If the user runs multiple instances and
        # the port is taken, the SO_REUSEADDR + kill_port_process handshake
        # below makes the new instance reclaim it.
        import http.server
        import socketserver

        webview_port = int(os.environ.get("NT_WEBVIEW_PORT", "5174") or "5174")
        kill_port_process(webview_port)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=os.path.dirname(gui_path), **kwargs)

            # Quiet the request log
            def log_message(self, format, *args):
                pass

        class _ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        def start_static_server():
            with _ReusableTCPServer(("127.0.0.1", webview_port), Handler) as httpd:
                global static_port
                static_port = httpd.server_address[1]
                httpd.serve_forever()

        static_thread = threading.Thread(target=start_static_server, daemon=True)
        static_thread.start()

        # Wait for port to be assigned
        import time
        while 'static_port' not in globals():
            time.sleep(0.1)

        url = f"http://127.0.0.1:{static_port}/index.html"

    # API to expose to frontend
    class Api:
        def open_url(self, url):
            import webbrowser
            webbrowser.open(url)
            
        def getLocalDomain(self):
            import socket
            try:
                # Get fully qualified domain name
                fqdn = socket.getfqdn()
                # Split to get domain part
                parts = fqdn.split('.')
                if len(parts) > 1:
                    return '.'.join(parts[1:])
                return ""
            except Exception:
                return ""

        def _is_safe_host(self, value):
            """Mesma validação conservadora do backend (_is_safe_remote_target)."""
            import re
            if not value or not isinstance(value, str) or len(value) > 253:
                return False
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value):
                try:
                    return all(0 <= int(o) <= 255 for o in value.split("."))
                except ValueError:
                    return False
            return bool(re.fullmatch(r"[A-Za-z0-9._-]+", value))

        def launchRdp(self, ip):
            import subprocess
            if not self._is_safe_host(ip):
                print(f"launchRdp: invalid host rejected")
                return False
            try:
                subprocess.Popen(['mstsc', '/v:' + ip])
                return True
            except Exception as e:
                print(f"Error launching RDP: {e}")
                return False

        def launchMsra(self, ip, askCredentials=False):
            import subprocess
            import os
            # Validate IP/hostname BEFORE building any command — caller-controlled
            # input must never reach a PowerShell f-string. The IP is passed via
            # env var ($env:NT_MSRA_TARGET) so it stays out of `Get-Process` /
            # event-viewer command-line snapshots.
            if not self._is_safe_host(ip):
                print(f"launchMsra: invalid host rejected")
                return False
            try:
                if askCredentials:
                    cmd = (
                        "$ip = $env:NT_MSRA_TARGET; "
                        "Remove-Item Env:\\NT_MSRA_TARGET -ErrorAction SilentlyContinue; "
                        "$cred = Get-Credential; "
                        "if ($cred -and $ip) { "
                        "  Start-Process \"$env:windir\\system32\\msra.exe\" "
                        "  -ArgumentList \"/offerRA $ip\" "
                        "  -Credential $cred -LoadUserProfile -WorkingDirectory 'C:\\' "
                        "}"
                    )
                    env = os.environ.copy()
                    env["NT_MSRA_TARGET"] = ip
                    subprocess.Popen(['powershell', '-NoProfile', '-Command', cmd], env=env)
                else:
                    subprocess.Popen(['msra', '/offerRA', ip])
                return True
            except Exception as e:
                print(f"Error launching MSRA: {e}")
                return False

        def launchTeamViewer(self, id):
            import subprocess
            paths = [
                r'C:\Program Files\TeamViewer\TeamViewer.exe',
                r'C:\Program Files (x86)\TeamViewer\TeamViewer.exe'
            ]
            for p in paths:
                if os.path.exists(p):
                    try:
                        args = ['-i', id] if id else []
                        subprocess.Popen([p] + args)
                        return True
                    except Exception as e:
                        print(f"Error launching TeamViewer: {e}")
            return False

        def openExternal(self, url):
            import webbrowser
            webbrowser.open(url)
            return True

        def showItemInFolder(self, path):
            import subprocess
            import os
            # Mirror the Electron isSafeShowItemPath guard: reject NUL,
            # traversal, UNC shares and \\?\ device paths before handing the
            # value to explorer. Belt-and-suspenders — the renderer is trusted
            # and behind CSP, but the two entry points should validate alike.
            if (not isinstance(path, str) or not path or len(path) > 1024
                    or '\0' in path or '..' in path
                    or path.startswith('\\\\') or path.startswith('//')):
                print("showItemInFolder: rejected unsafe path")
                return False
            try:
                path = os.path.normpath(path)
                subprocess.Popen(['explorer', '/select,', path])
                return True
            except Exception as e:
                print(f"Error showing item in folder: {e}")
                return False

        def saveFileAs(self, filename, content):
            import webview
            import re as _re
            # Mirror the Electron handler's filename guard
            # (electron/main.ts:save-file-as). The OS save dialog is the user's
            # last line of defense, but we shouldn't be feeding it a default
            # name containing path separators, null bytes, traversal, Windows
            # reserved device names, or trailing dot/space. Content must be a
            # plain string — the renderer should never send anything else.
            if not isinstance(filename, str) or not isinstance(content, str):
                return None
            if (not filename
                    or '\0' in filename
                    or '/' in filename
                    or '\\' in filename
                    or '..' in filename):
                return None
            stem = _re.sub(r"\.[^.]+$", "", filename).upper()
            if _re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", stem):
                return None
            if _re.search(r"[. ]$", filename):
                return None
            try:
                active_window = webview.windows[0]
                result = active_window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    save_filename=filename,
                    file_types=('CSV Files (*.csv)', 'All files (*.*)')
                )

                if result:
                    path = result if isinstance(result, str) else result[0]
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return path
                return None
            except Exception as e:
                print(f"Error saving file: {e}")
                return None

    # Inject JS Shim to map window.electron to pywebview api
    def initialize_shim(window):
        shim_js = """
        window.electron = {
            getLocalDomain: () => window.pywebview.api.getLocalDomain(),
            launchRdp: (ip) => window.pywebview.api.launchRdp(ip),
            launchMsra: (ip, askCredentials) => window.pywebview.api.launchMsra(ip, askCredentials),
            launchTeamViewer: (id) => window.pywebview.api.launchTeamViewer(id),
            openExternal: (url) => window.pywebview.api.openExternal(url),
            showItemInFolder: (path) => window.pywebview.api.showItemInFolder(path),
            saveFileAs: (filename, content) => window.pywebview.api.saveFileAs(filename, content)
        };
        console.log("Electron Shim Initialized");
        """
        window.evaluate_js(shim_js)

    # Window title carries the app version so an operator can tell which
    # build they're running at a glance (we ship the portable as a single
    # versioned .exe, but copies on the Desktop drift). APP_VERSION is the
    # single source resolved from electron/package.json (settings.py).
    try:
        from src.config.settings import APP_VERSION as _APP_VERSION
        _window_title = f'Ferramentas de Rede v{_APP_VERSION}'
    except Exception:
        _window_title = 'Ferramentas de Rede'

    # Create the window
    window = webview.create_window(
        _window_title,
        url=url,
        width=1280,
        height=800,
        resizable=True,
        min_size=(1024, 768),
        js_api=Api()
    )
    
    # Register the shim injection.
    # `debug` is opt-in via NT_WEBVIEW_DEBUG=1. When enabled, pywebview exposes
    # the WebView2 DevTools (right-click → Inspecionar), which is the only way
    # to capture network requests / console logs from inside the portable .exe.
    # Off by default so production users don't see a "Inspecionar" item.
    _debug = os.environ.get("NT_WEBVIEW_DEBUG", "").strip() in ("1", "true", "yes")
    webview.start(func=initialize_shim, args=window, debug=_debug)

if __name__ == '__main__':
    main()
