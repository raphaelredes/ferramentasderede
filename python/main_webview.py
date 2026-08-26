import sys
import os
import threading
import webview
import uvicorn
import psutil
import time
import atexit
import signal
import winreg
import ctypes

try:
    import pyi_splash
except (ImportError, ModuleNotFoundError):
    pyi_splash = None





# --- Fresh-Windows runtime pre-flight ---------------------------------------
# pywebview 6.1 has ONLY the WebView2/EdgeChromium backend on Windows (there is
# no MSHTML fallback). If the Microsoft Edge WebView2 Runtime is absent — which
# happens on freshly-imaged / unpatched / LTSC / air-gapped Windows 10 (every
# Windows 11 ships it in-box) — then webview.start() raises deep inside pythonnet
# and the process dies with NO window and NO message. The bundle ships only the
# WebView2 *loader* (WebView2Loader.dll), not the runtime itself, so it cannot
# render on its own. We therefore (1) optionally wire a bundled fixed-version
# runtime for offline builds, (2) verify a usable runtime exists, and (3) if not,
# show an actionable dialog instead of hanging silently.

# Evergreen WebView2 client GUID (verified on-machine; do NOT confuse with the
# ...E38 GUID that floats around online — that one is wrong).
_WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def _wire_bundled_webview2():
    """Point WebView2 at a bundled fixed-version runtime, if one is shipped.

    Looks in _MEIPASS/webview2_runtime (onefile), next to the exe, and next to
    this source file (dev). Sets WEBVIEW2_BROWSER_EXECUTABLE_FOLDER so pywebview
    uses it — the guarantee of a true offline first boot. Returns True if wired.
    No-op (returns False) when no bundled runtime is present, so the default
    ~34 MB build simply falls back to the system runtime. An operator override
    of the env var is always respected."""
    if os.environ.get("WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"):
        return True
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "webview2_runtime"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "webview2_runtime"))
    else:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "webview2_runtime"))
    for folder in candidates:
        if os.path.isfile(os.path.join(folder, "msedgewebview2.exe")):
            os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = folder
            print(f"Using bundled WebView2 runtime: {folder}")
            return True
    return False


def _system_webview2_version():
    """Return the installed Evergreen WebView2 version string, or None.

    Checks the per-machine 64-bit view (WOW6432Node holds the 32-bit-registered
    client on 64-bit Windows), the plain per-machine view, and the per-user hive.
    Any non-empty, non-zero 'pv' means a runtime is present."""
    roots = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\EdgeUpdate\Clients"),
    )
    for hive, base in roots:
        try:
            with winreg.OpenKey(hive, base + "\\" + _WEBVIEW2_GUID) as key:
                pv, _ = winreg.QueryValueEx(key, "pv")
                if pv and pv != "0.0.0.0":
                    return pv
        except OSError:
            continue
    return None


def _message_box(text, title, flags=0x10):
    """Best-effort native dialog (MB_ICONERROR default). Never raises — we may be
    a console-less GUI process, so print() is the only other channel."""
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    except Exception as e:
        print(f"MessageBox failed: {e}")


def _bundled_bootstrapper_path():
    """Return the path to the embedded WebView2 Evergreen Bootstrapper, or None.

    We ship the ~1.6 MB official Microsoft bootstrapper in bin/ (packaged by the
    spec's ('bin/*','bin') rule), so a fresh PC with internet can install the
    runtime WITHOUT the app first having to download the installer itself — the
    installer is already inside the .exe. It still pulls the actual runtime from
    Microsoft at run time (that ~180 MB is what we deliberately do NOT bundle)."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "bin", "MicrosoftEdgeWebview2Setup.exe")
    return path if os.path.isfile(path) else None


def _install_webview2():
    """Install the Evergreen runtime, preferring the embedded bootstrapper.

    Runs the bundled MicrosoftEdgeWebview2Setup.exe (falling back to downloading
    it from Microsoft's permanent fwlink if, for any reason, it isn't bundled).
    Returns True only if a runtime is present afterwards. Requires internet: the
    bootstrapper downloads the runtime payload from Microsoft."""
    import subprocess
    setup = _bundled_bootstrapper_path()
    try:
        if setup is None:
            # Fallback: the installer wasn't bundled — fetch it on the fly.
            import urllib.request
            import tempfile
            setup = os.path.join(tempfile.gettempdir(), "MicrosoftEdgeWebview2Setup.exe")
            print("Bundled bootstrapper missing; downloading from Microsoft...")
            urllib.request.urlretrieve("https://go.microsoft.com/fwlink/p/?LinkId=2124703", setup)
        else:
            print(f"Running bundled WebView2 bootstrapper: {setup}")
        # //silent //install → unattended per-machine install (bootstrapper accepts
        # both / and // forms; //silent avoids its own UI). check=False: we verify
        # success by re-reading the registry, not by exit code.
        subprocess.run([setup, "/silent", "/install"], check=False)
        return _system_webview2_version() is not None
    except Exception as e:
        print(f"WebView2 install failed: {e}")
        return False


def preflight_webview2():
    """Guarantee a WebView2 runtime is reachable before webview.start().

    Order: bundled fixed-version → installed system Evergreen → offer to install
    via the embedded bootstrapper (needs internet) → guided fallback. Returns
    True if the app may proceed, False if it must exit. This converts the
    fresh-Windows silent-death into an actionable path to a working app."""
    if _wire_bundled_webview2():
        return True

    version = _system_webview2_version()
    if version:
        print(f"System WebView2 runtime found: {version}")
        return True

    print("WebView2 runtime not found.")
    # MB_YESNO | MB_ICONWARNING = 0x34
    resp = 0
    try:
        resp = ctypes.windll.user32.MessageBoxW(
            None,
            "Para exibir a interface, o Ferramentas de Rede precisa do componente\n"
            "Microsoft Edge WebView2 Runtime, que nao esta instalado neste computador.\n\n"
            "Deseja instalar agora? O instalador ja vem incluido no aplicativo;\n"
            "so e necessaria conexao com a internet para concluir (poucos minutos).",
            "Instalar componente necessario",
            0x34,
        )
    except Exception as e:
        print(f"MessageBox failed: {e}")

    if resp == 6:  # IDYES → run the embedded bootstrapper (falls back to download)
        if _install_webview2():
            print("WebView2 runtime installed successfully.")
            return True
        _message_box(
            "Nao foi possivel instalar o WebView2 automaticamente.\n"
            "Verifique a conexao com a internet e tente novamente, ou instale\n"
            "manualmente a partir de:\n"
            "https://developer.microsoft.com/microsoft-edge/webview2/",
            "WebView2 Runtime",
        )
        return False

    # User declined or the dialog itself failed: guide and exit rather than hang.
    _message_box(
        "O aplicativo nao pode iniciar sem o WebView2 Runtime.\n"
        "Instale-o a partir de:\n"
        "https://developer.microsoft.com/microsoft-edge/webview2/",
        "WebView2 Runtime ausente",
    )
    return False


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
    from api.server import app
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

        # Deterministic MIME map for the web assets we serve. SimpleHTTPRequestHandler
        # derives Content-Type from the `mimetypes` module, which on Windows seeds
        # itself from the registry (HKCR\.js "Content Type"). On locked-down /
        # freshly-imaged corporate PCs that key is frequently set to "text/plain"
        # (AV, JS-hardening GPOs, or another app that claimed the .js extension).
        # When our bundled ES module (`<script type="module">`) is served as
        # text/plain, WebView2 refuses to execute it (strict module MIME checking),
        # React never mounts, and the app hangs forever on the static splash. We
        # therefore pin the correct types ourselves instead of trusting the host.
        _STATIC_MIME = {
            ".js": "text/javascript",
            ".mjs": "text/javascript",
            ".css": "text/css",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json",
            ".map": "application/json",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
        }

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=os.path.dirname(gui_path), **kwargs)

            def guess_type(self, path):
                """Pin web-asset MIME types independent of the host registry.

                See _STATIC_MIME above for why the stdlib default is unsafe here.
                Falls back to the base implementation for anything not pinned."""
                _, ext = os.path.splitext(path)
                pinned = _STATIC_MIME.get(ext.lower())
                if pinned:
                    return pinned
                return super().guess_type(path)

            # Quiet the request log
            def log_message(self, format, *args):
                pass

        class _ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        static_ready = threading.Event()

        def start_static_server():
            with _ReusableTCPServer(("127.0.0.1", webview_port), Handler) as httpd:
                global static_port
                static_port = httpd.server_address[1]
                static_ready.set()
                httpd.serve_forever()

        static_thread = threading.Thread(target=start_static_server, daemon=True)
        static_thread.start()

        # Signal instantly when port is assigned (0ms wait instead of polling loop)
        static_ready.wait(timeout=5.0)

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
        global pyi_splash
        if pyi_splash:
            try:
                pyi_splash.close()
                pyi_splash = None
            except Exception:
                pass
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

    # Fresh-Windows guarantee: ensure a WebView2 runtime is reachable (bundled
    # or system) BEFORE we try to render. On a machine without it, this exits
    # with clear guidance instead of the previous silent crash / eternal splash.
    if not preflight_webview2():
        sys.exit(1)



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
    # Last line of defense: even with the pre-flight, a corrupt/partial runtime
    # can still make WebView2 init throw. Surface it instead of dying silently.
    try:
        webview.start(func=initialize_shim, args=window, debug=_debug)
    except Exception as e:
        print(f"FATAL: WebView2 initialization failed: {e}")
        _message_box(
            "Falha ao inicializar a interface (WebView2):\n\n"
            f"{e}\n\n"
            "Verifique se o Microsoft Edge WebView2 Runtime esta instalado e "
            "atualizado, ou reinicie o computador.",
            "Erro de inicializacao",
        )
        sys.exit(1)

if __name__ == '__main__':
    main()
