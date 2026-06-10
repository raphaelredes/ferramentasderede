import { app, BrowserWindow, ipcMain, shell, dialog, session } from 'electron'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
import { spawn, ChildProcess } from 'node:child_process'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// The built directory structure
process.env.APP_ROOT = path.join(__dirname, '..')

// 🚧 Use ['ENV_NAME'] avoid vite:define plugin - Vite@2.x
export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron')
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist')

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, 'public') : RENDERER_DIST

let win: BrowserWindow | null
let pythonProcess: ChildProcess | null = null

// Função para logar em arquivo
function logToFile(message: string) {
  const logPath = path.join(app.getPath('temp'), 'network_tools_debug.log');
  const timestamp = new Date().toISOString();
  fs.appendFileSync(logPath, `[${timestamp}] ${message}\n`);
}

logToFile('=== APP STARTED (Main Process) ===');

// Função para iniciar o backend Python
function startPythonBackend() {
  let pythonExecutable = 'python'
  let scriptArgs: string[] = []
  let cwd = process.env.APP_ROOT

  logToFile(`app.isPackaged: ${app.isPackaged}`);
  const potentialServerPath = path.join(process.resourcesPath, 'server', 'server.exe');

  if (fs.existsSync(potentialServerPath)) {
    // Se o executável existe nos resources, estamos em produção (ou teste de build)
    pythonExecutable = potentialServerPath
    scriptArgs = []
    cwd = path.join(process.resourcesPath, 'server')
    logToFile(`Modo Produção detectado (server.exe encontrado).`);
    logToFile(`Server Path: ${pythonExecutable}`);
    logToFile(`CWD: ${cwd}`);
  } else {
    // Em dev, rodar o script python
    const pythonDir = path.join(process.env.APP_ROOT, '..', 'python')
    const scriptPath = path.join(pythonDir, 'api', 'server.py')

    pythonExecutable = 'python'
    scriptArgs = ['-u', scriptPath] // -u for unbuffered output
    cwd = pythonDir
    console.log(`Iniciando backend Python (Dev): ${pythonExecutable} ${scriptPath}`)
    console.log(`CWD: ${cwd}`)
    logToFile(`Modo Dev detectado (server.exe não encontrado).`);
  }

  try {
    logToFile(`Executando spawn: ${pythonExecutable} com args: ${JSON.stringify(scriptArgs)} em ${cwd}`);
    pythonProcess = spawn(pythonExecutable, scriptArgs, {
      cwd: cwd,
      stdio: ['ignore', 'pipe', 'pipe']
    })

    pythonProcess.stdout?.on('data', (data) => {
      const msg = data.toString();
      console.log(`[Python API]: ${msg}`)
      logToFile(`[Python API]: ${msg}`);
    })

    pythonProcess.stderr?.on('data', (data) => {
      const msg = data.toString();
      console.error(`[Python API Error]: ${msg}`)
      logToFile(`[Python API Error]: ${msg}`);
    })

    pythonProcess.on('close', (code, signal) => {
      const msg = `Backend Python encerrado. Código: ${code}, Sinal: ${signal}`;
      console.log(msg)
      logToFile(msg);
    })

    pythonProcess.on('error', (err) => {
      const msg = `Falha ao iniciar backend Python: ${err}`;
      console.error(msg)
      logToFile(msg);
    })
  } catch (e) {
    logToFile(`Erro crítico ao tentar iniciar processo: ${e}`);
  }
}

// Função para encerrar o backend Python
function killPythonBackend() {
  if (pythonProcess) {
    console.log('Encerrando backend Python...')
    logToFile('Encerrando backend Python...');
    if (!pythonProcess.killed) {
      pythonProcess.kill()
    }
    pythonProcess = null
  }
}

function isAllowedRendererUrl(url: string): boolean {
  // Dev: vite server. Prod: only file:// pointing inside RENDERER_DIST.
  if (VITE_DEV_SERVER_URL && url.startsWith(VITE_DEV_SERVER_URL)) return true
  if (url.startsWith('file://')) {
    try {
      const filePath = path.resolve(fileURLToPath(url))
      const rendererRoot = path.resolve(RENDERER_DIST)
      // path.resolve normalizes `..` — only accept paths that live inside the
      // bundled renderer directory. Without this, `file:///C:/Windows/System32/...`
      // would slip past a simple `startsWith('file://')` check.
      return filePath === rendererRoot || filePath.startsWith(rendererRoot + path.sep)
    } catch {
      return false
    }
  }
  return false
}

function createWindow() {
  logToFile('createWindow called');
  // Window title carries the version (app.getVersion reads electron/package.json,
  // the single source). Matches the portable's title (main_webview.py) so an
  // operator can tell which build is running regardless of how it was launched.
  const windowTitle = `Ferramentas de Rede v${app.getVersion()}`
  win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1200,
    minHeight: 800,
    title: windowTitle,
    backgroundColor: '#09090b', // Dark background to match loader (prevents white flash)
    icon: path.join(process.env.VITE_PUBLIC, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      // Sandbox the renderer process so a compromised page can't spawn child
      // processes, read arbitrary files or use Node APIs. The preload still
      // runs in a privileged context and exposes only validated bridges.
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  })

  win.removeMenu()

  // The renderer's <title> tag ("Ferramentas de Rede") would override the
  // versioned title above once the page loads. Pin our title and re-apply it
  // whenever the page tries to change it.
  win.on('page-title-updated', (event) => {
    event.preventDefault()
    win?.setTitle(windowTitle)
  })

  // Defense-in-depth navigation guards:
  // 1. Reject window.open / target=_blank — the UI doesn't need it. External URLs
  //    go through the explicit `openExternal` IPC which validates the URL.
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  // 2. Block in-renderer navigation away from the bundled UI (dev: vite, prod:
  //    file://). Prevents a crafted link or compromised content from steering
  //    the window to an attacker-controlled origin. Path-normalize file:// URLs
  //    so they can only reference paths inside RENDERER_DIST.
  win.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedRendererUrl(url)) {
      event.preventDefault()
      logToFile(`Blocked navigation to ${url}`)
    }
  })
  // 3. Same guard for redirects — a 30x from a stray fetch shouldn't reach an
  //    attacker origin.
  win.webContents.on('will-redirect', (event, url) => {
    if (!isAllowedRendererUrl(url)) {
      event.preventDefault()
      logToFile(`Blocked redirect to ${url}`)
    }
  })

  // Test active push message to Renderer-process.
  win.webContents.on('did-finish-load', () => {
    logToFile('win.webContents did-finish-load');
    win?.webContents.send('main-process-message', (new Date).toLocaleString())
  })

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL)
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'index.html'))
  }

  // Monitorar foco da janela para controle de notificações
  win.on('focus', () => {
    win?.webContents.send('window-focus-change', true)
  })

  win.on('blur', () => {
    win?.webContents.send('window-focus-change', false)
  })

  win.once('ready-to-show', () => {
    logToFile('win ready-to-show');
    win?.show();
  });
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    killPythonBackend() // Garantir que o Python morra junto
    app.quit()
    win = null
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

app.on('before-quit', () => {
  killPythonBackend()
})

// Validation helpers — refuse any input the user could weaponize before
// passing it to spawn / shell.openExternal / shell.showItemInFolder.
function isSafeHost(value: unknown): value is string {
  if (typeof value !== 'string' || value.length === 0 || value.length > 253) return false
  // IPv4 (strict octets)
  if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(value)) {
    return value.split('.').every(o => {
      const n = Number(o)
      return Number.isInteger(n) && n >= 0 && n <= 255
    })
  }
  // Hostname: alphanumerics, dot, hyphen, underscore. Leading hyphen/underscore
  // is rejected so an attacker can't masquerade as an argv flag for downstream
  // tools (e.g. `msra.exe -SomeFlag`).
  return /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(value)
}

function isSafeTeamViewerId(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9 ]{1,32}$/.test(value)
}

function isSafeExternalUrl(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 2048) return false
  try {
    const u = new URL(value)
    // mailto: dropped — the app doesn't surface any mailto link; allowing it
    // gave a small mail-client launch primitive with attacker-controlled body.
    return ['http:', 'https:'].includes(u.protocol)
  } catch {
    return false
  }
}

function isSafeShowItemPath(value: unknown): value is string {
  if (typeof value !== 'string' || value.length === 0 || value.length > 1024) return false
  // Reject NUL, path-traversal, UNC shares, and the \\?\ device path prefix.
  // shell.showItemInFolder is normally harmless, but UNC/device paths are a
  // quick way to coerce Explorer into rendering attacker-controlled content
  // (or trigger NTLM relay via SMB).
  if (value.includes('\0') || value.includes('..')) return false
  if (value.startsWith('\\\\') || value.startsWith('//')) return false
  // Reject NTFS Alternate Data Streams in the leaf name.
  const leaf = value.split(/[\\/]/).pop() || ''
  if (leaf.includes(':') && !/^[A-Za-z]:$/.test(leaf)) return false
  return true
}

// Absolute path to the system powershell.exe — avoids any PATH-based hijack.
const PS_EXECUTABLE = path.join(
  process.env.SystemRoot || 'C:\\Windows',
  'System32',
  'WindowsPowerShell',
  'v1.0',
  'powershell.exe'
)

// Enforce single-instance: a second launch focuses the existing window instead
// of racing for port 8000 and orphaning the previous backend.
const gotSingleInstanceLock = app.requestSingleInstanceLock()
if (!gotSingleInstanceLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })
}

function registerIpcHandlers() {
  ipcMain.handle('launch-rdp', async (_event: unknown, ip: unknown) => {
    if (!isSafeHost(ip)) throw new Error('Invalid host')
    spawn('mstsc', ['/v:' + ip])
    return true
  })

  ipcMain.handle('launch-msra', async (_event: unknown, ip: unknown, askCredentials?: unknown) => {
    if (!isSafeHost(ip)) throw new Error('Invalid host')

    // Resolve msra.exe absolute path. Plain `spawn('msra', ...)` relies on the
    // process PATH including %WINDIR%\system32, which is usually true, but if
    // the Electron child env is sanitized we get ENOENT. Using the absolute
    // path is safer and lets us pin the system version (avoids any user-shadowed
    // msra.cmd / .ps1 hijack via PATH).
    const msraPath = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'msra.exe')

    if (askCredentials) {
      // Both `target` AND `msraPath` are passed via env vars (cleared on entry)
      // so no user-controlled or env-controlled value is interpolated into the
      // script body. Errors get appended (not overwritten) to a debug log so
      // we can see what happened across multiple attempts.
      const script = `
        $ErrorActionPreference = 'Stop'
        $target = $env:NT_MSRA_TARGET
        $msraBin = $env:NT_MSRA_BIN
        Remove-Item Env:\\NT_MSRA_TARGET -ErrorAction SilentlyContinue
        Remove-Item Env:\\NT_MSRA_BIN -ErrorAction SilentlyContinue
        $logPath = Join-Path $env:TEMP 'msra_debug.log'
        "[" + (Get-Date -Format o) + "] launch-msra (other user) target=$target" | Out-File -FilePath $logPath -Append -Encoding utf8
        $cred = Get-Credential -Message "Credenciais para conectar em $target"
        if ($cred) {
          try {
            Start-Process -FilePath $msraBin -ArgumentList @('/offerRA', $target) -Credential $cred -LoadUserProfile -WorkingDirectory 'C:\\' -ErrorAction Stop
            "[" + (Get-Date -Format o) + "] Start-Process OK" | Out-File -FilePath $logPath -Append -Encoding utf8
          } catch {
            "[" + (Get-Date -Format o) + "] Start-Process FAILED: $($_.Exception.Message)" | Out-File -FilePath $logPath -Append -Encoding utf8
          }
        } else {
          "[" + (Get-Date -Format o) + "] Get-Credential cancelled by user" | Out-File -FilePath $logPath -Append -Encoding utf8
        }
      `
      // NOTE: -NonInteractive is deliberately omitted here. The whole point of
      // this branch is the Get-Credential prompt below, which throws a
      // PromptingException in non-interactive mode (PS 5.1). Other PS spawns
      // can use -NonInteractive freely; this one can't.
      const child = spawn(
        PS_EXECUTABLE,
        ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
        {
          env: { ...process.env, NT_MSRA_TARGET: ip as string, NT_MSRA_BIN: msraPath },
          windowsHide: false,
        }
      )
      child.on('error', (err) => logToFile(`launch-msra (askCreds) spawn error: ${err.message}`))
      child.on('exit', (code) => logToFile(`launch-msra (askCreds) ps exited with code ${code}`))
    } else {
      // Direct mode: `msra.exe /offerRA <ip>` immediately opens the MSRA window
      // already targeting <ip>. Pinning the absolute path avoids any PATH
      // shim hijack.
      const child = spawn(msraPath, ['/offerRA', ip], { windowsHide: false })
      child.on('error', (err) => logToFile(`launch-msra spawn error: ${err.message}`))
      child.on('exit', (code) => logToFile(`launch-msra exited with code ${code}`))
    }
    return true
  })

  ipcMain.handle('open-external', async (_event: unknown, url: unknown) => {
    if (!isSafeExternalUrl(url)) throw new Error('Invalid URL')
    await shell.openExternal(url)
    return true
  })

  ipcMain.handle('show-item-in-folder', async (_event: unknown, p: unknown) => {
    if (!isSafeShowItemPath(p)) throw new Error('Invalid path')
    shell.showItemInFolder(p)
    return true
  })

  ipcMain.handle('launch-teamviewer', async (_event: unknown, id?: unknown) => {
    if (id !== undefined && !isSafeTeamViewerId(id)) throw new Error('Invalid TeamViewer id')
    const paths = [
      'C:\\Program Files\\TeamViewer\\TeamViewer.exe',
      'C:\\Program Files (x86)\\TeamViewer\\TeamViewer.exe'
    ]

    for (const p of paths) {
      try {
        if (fs.existsSync(p)) {
          const args = id ? ['-i', id as string] : []
          spawn(p, args)
          return true
        }
      } catch (e) {
        console.error(`Error checking path ${p}:`, e)
      }
    }
    return false
  })

  ipcMain.handle('get-local-domain', async () => {
    return process.env.USERDNSDOMAIN || process.env.USERDOMAIN || ''
  })

  ipcMain.handle('save-file-as', async (_event: unknown, filename: unknown, content: unknown) => {
    if (typeof filename !== 'string' || typeof content !== 'string') {
      throw new Error('Invalid arguments')
    }
    if (filename.includes('\0') || filename.includes('/') || filename.includes('\\') || filename.includes('..')) {
      throw new Error('Invalid filename')
    }
    // Reject Windows reserved device names and trailing dot/space tricks.
    const stem = filename.replace(/\.[^.]+$/, '').toUpperCase()
    const reserved = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/
    if (reserved.test(stem)) throw new Error('Invalid filename')
    if (/[. ]$/.test(filename)) throw new Error('Invalid filename')

    const { filePath } = await dialog.showSaveDialog({
      defaultPath: filename,
      filters: [
        { name: 'CSV Files', extensions: ['csv'] },
        { name: 'All Files', extensions: ['*'] }
      ]
    })

    if (filePath) {
      await fs.promises.writeFile(filePath, content, 'utf-8')
      return filePath
    }
    return null
  })
}

app.whenReady().then(() => {
  logToFile('app.whenReady fired');

  // CSP is enforced by the `<meta http-equiv="Content-Security-Policy">` tag
  // in electron/index.html. We do NOT inject a duplicate via webRequest:
  // when two CSPs are present the browser combines them by taking the most
  // restrictive value of EACH directive — and the meta tag legitimately
  // needs `'unsafe-inline' 'unsafe-eval'` in script-src for Vite's
  // module-preload helper and recharts internals. Injecting `script-src
  // 'self'` here (no unsafe-*) intersected with the meta to block every
  // module load → the splash screen hung forever because the React bundle
  // couldn't execute.
  //
  // If you want to tighten CSP further, edit the meta tag in index.html;
  // don't add a header here.

  // Deny camera/mic/notifications/geolocation/etc. by default. Future UI
  // changes can request specifics explicitly.
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false))

  startPythonBackend()
  createWindow()
  registerIpcHandlers()
})
