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
                    except:
                        pass
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
    """Starts the FastAPI server in a separate thread."""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

def main():
    # Register cleanup on exit
    atexit.register(cleanup)

    # Ensure port 8000 is free
    kill_port_process(8000)
    
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

        def launchRdp(self, ip):
            import subprocess
            try:
                subprocess.Popen(['mstsc', '/v:' + ip])
                return True
            except Exception as e:
                print(f"Error launching RDP: {e}")
                return False

        def launchMsra(self, ip, askCredentials=False):
            import subprocess
            try:
                if askCredentials:
                    # PowerShell command to prompt for credentials and launch MSRA
                    cmd = f"""
                    $cred = Get-Credential
                    if ($cred) {{
                        Start-Process "$env:windir\\system32\\msra.exe" -ArgumentList "/offerRA {ip}" -Credential $cred -LoadUserProfile -WorkingDirectory "C:\\"
                    }}
                    """
                    subprocess.Popen(['powershell', '-Command', cmd])
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
            try:
                # Windows explorer /select,path
                path = os.path.normpath(path)
                subprocess.Popen(['explorer', '/select,', path])
                return True
            except Exception as e:
                print(f"Error showing item in folder: {e}")
                return False

        def saveFileAs(self, filename, content):
            import webview
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

    # Create the window
    window = webview.create_window(
        'Ferramentas de Rede',
        url=url,
        width=1280,
        height=800,
        resizable=True,
        min_size=(1024, 768),
        js_api=Api()
    )
    
    # Register the shim injection
    webview.start(func=initialize_shim, args=window, debug=False)

if __name__ == '__main__':
    main()
