import { app, BrowserWindow } from 'electron'
// import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { spawn, ChildProcess } from 'node:child_process'

// const require = createRequire(import.meta.url)
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
  const fs = require('fs');
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
  const fs = require('fs');

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

function createWindow() {
  logToFile('createWindow called');
  win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1200,
    minHeight: 800,
    title: 'Ferramentas de Rede',
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
    },
  })

  win.removeMenu()

  // Defense-in-depth navigation guards:
  // 1. Reject window.open / target=_blank — the UI doesn't need it. External URLs
  //    go through the explicit `openExternal` IPC which validates the URL.
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  // 2. Block in-renderer navigation away from the bundled UI (dev: vite, prod:
  //    file://). Prevents a crafted link or compromised content from steering
  //    the window to an attacker-controlled origin.
  win.webContents.on('will-navigate', (event, url) => {
    const allowedPrefixes = [VITE_DEV_SERVER_URL, 'file://'].filter(Boolean) as string[]
    if (!allowedPrefixes.some(p => url.startsWith(p))) {
      event.preventDefault()
      logToFile(`Blocked navigation to ${url}`)
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
  // Hostname: alphanumerics, dot, hyphen, underscore. No spaces, no quotes, no shell metas.
  return /^[A-Za-z0-9._-]+$/.test(value)
}

function isSafeTeamViewerId(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9 ]{1,32}$/.test(value)
}

function isSafeExternalUrl(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 2048) return false
  try {
    const u = new URL(value)
    return ['http:', 'https:', 'mailto:'].includes(u.protocol)
  } catch {
    return false
  }
}

function isSafeShowItemPath(value: unknown): value is string {
  if (typeof value !== 'string' || value.length === 0 || value.length > 1024) return false
  // Reject NUL and any path-traversal attempt. Caller passes absolute paths only.
  if (value.includes('\0') || value.includes('..')) return false
  return true
}

app.whenReady().then(() => {
  logToFile('app.whenReady fired');
  startPythonBackend()
  createWindow()

  // IPC Handlers para ferramentas nativas
  const { ipcMain } = require('electron')

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
      // Pass the target via env var (not interpolated into the script body) AND
      // build PowerShell arguments as an *array literal* so `/offerRA` stays a
      // separate argv element regardless of any quoting weirdness with hyphens
      // or underscores in the hostname. Errors get appended (not overwritten)
      // to a debug log so we can see what happened across multiple attempts.
      const script = `
        $ErrorActionPreference = 'Stop'
        $target = $env:NT_MSRA_TARGET
        Remove-Item Env:\\NT_MSRA_TARGET -ErrorAction SilentlyContinue
        $logPath = Join-Path $env:TEMP 'msra_debug.log'
        "[" + (Get-Date -Format o) + "] launch-msra (other user) target=$target" | Out-File -FilePath $logPath -Append -Encoding utf8
        $cred = Get-Credential -Message "Credenciais para conectar em $target"
        if ($cred) {
          try {
            Start-Process -FilePath "${msraPath.replace(/\\/g, '\\\\')}" -ArgumentList @('/offerRA', $target) -Credential $cred -LoadUserProfile -WorkingDirectory 'C:\\' -ErrorAction Stop
            "[" + (Get-Date -Format o) + "] Start-Process OK" | Out-File -FilePath $logPath -Append -Encoding utf8
          } catch {
            "[" + (Get-Date -Format o) + "] Start-Process FAILED: $($_.Exception.Message)" | Out-File -FilePath $logPath -Append -Encoding utf8
          }
        } else {
          "[" + (Get-Date -Format o) + "] Get-Credential cancelled by user" | Out-File -FilePath $logPath -Append -Encoding utf8
        }
      `
      const child = spawn('powershell', ['-NoProfile', '-Command', script], {
        env: { ...process.env, NT_MSRA_TARGET: ip as string },
        windowsHide: false,
      })
      child.on('error', (err) => logToFile(`launch-msra (askCreds) spawn error: ${err.message}`))
      child.on('exit', (code) => logToFile(`launch-msra (askCreds) ps exited with code ${code}`))
    } else {
      // Direct mode: `msra.exe /offerRA <ip>` immediately opens the MSRA window
      // already targeting <ip>. If the user reported that the window opens but
      // does NOT auto-connect, the most likely cause was msra resolving via
      // PATH and getting a hijack/shim — pinning the absolute path fixes it.
      const child = spawn(msraPath, ['/offerRA', ip as string], { windowsHide: false })
      child.on('error', (err) => logToFile(`launch-msra spawn error: ${err.message}`))
      child.on('exit', (code) => logToFile(`launch-msra exited with code ${code}`))
    }
    return true
  })

  ipcMain.handle('open-external', async (_event: unknown, url: unknown) => {
    if (!isSafeExternalUrl(url)) throw new Error('Invalid URL')
    const { shell } = require('electron')
    await shell.openExternal(url)
    return true
  })

  ipcMain.handle('show-item-in-folder', async (_event: unknown, p: unknown) => {
    if (!isSafeShowItemPath(p)) throw new Error('Invalid path')
    const { shell } = require('electron')
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
        const fs = require('fs')
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
    if (filename.includes('\0') || filename.includes('/') || filename.includes('\\')) {
      throw new Error('Invalid filename')
    }
    const { dialog } = require('electron')
    const fs = require('fs')

    const { filePath } = await dialog.showSaveDialog({
      defaultPath: filename,
      filters: [
        { name: 'CSV Files', extensions: ['csv'] },
        { name: 'All Files', extensions: ['*'] }
      ]
    })

    if (filePath) {
      fs.writeFileSync(filePath, content, 'utf-8')
      return filePath
    }
    return null
  })
})
