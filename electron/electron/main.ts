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

// Função para iniciar o backend Python
function startPythonBackend() {
  let pythonExecutable = 'python'
  let scriptArgs: string[] = []
  let cwd = process.env.APP_ROOT

  if (app.isPackaged) {
    // Em produção, o executável está em resources/server/server.exe
    const serverPath = path.join(process.resourcesPath, 'server', 'server.exe')
    pythonExecutable = serverPath
    scriptArgs = []
    cwd = path.join(process.resourcesPath, 'server')
    console.log(`Iniciando backend Python (Prod): ${serverPath}`)
  } else {
    // Em dev, rodar o script python
    const pythonDir = path.join(process.env.APP_ROOT, '..', 'python')
    const scriptPath = path.join(pythonDir, 'api', 'server.py')

    pythonExecutable = 'python'
    scriptArgs = ['-u', scriptPath] // -u for unbuffered output
    cwd = pythonDir
    console.log(`Iniciando backend Python (Dev): ${pythonExecutable} ${scriptPath}`)
    console.log(`CWD: ${cwd}`)
  }

  pythonProcess = spawn(pythonExecutable, scriptArgs, {
    cwd: cwd,
    stdio: ['ignore', 'pipe', 'pipe']
  })

  pythonProcess.stdout?.on('data', (data) => {
    console.log(`[Python API]: ${data}`)
  })

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`[Python API Error]: ${data}`)
  })

  pythonProcess.on('close', (code, signal) => {
    console.log(`Backend Python encerrado. Código: ${code}, Sinal: ${signal}`)
  })

  pythonProcess.on('error', (err) => {
    console.error(`Falha ao iniciar backend Python: ${err}`)
  })
}

// Função para encerrar o backend Python
function killPythonBackend() {
  if (pythonProcess) {
    console.log('Encerrando backend Python...')
    if (!pythonProcess.killed) {
      pythonProcess.kill()
    }
    pythonProcess = null
  }
}

function createWindow() {
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
    },
  })

  win.removeMenu()

  // Test active push message to Renderer-process.
  win.webContents.on('did-finish-load', () => {
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

app.whenReady().then(() => {
  startPythonBackend()
  createWindow()

  // IPC Handlers para ferramentas nativas
  const { ipcMain } = require('electron')

  ipcMain.handle('launch-rdp', async (_: any, ip: string) => {
    spawn('mstsc', ['/v:' + ip])
    return true
  })

  ipcMain.handle('launch-msra', async (_: any, ip: string, askCredentials?: boolean) => {
    if (askCredentials) {
      // Use PowerShell to prompt for credentials and launch MSRA
      // Using a more robust command structure
      const command = `
        $cred = Get-Credential
        if ($cred) {
            try {
                Start-Process "$env:windir\\system32\\msra.exe" -ArgumentList "/offerRA ${ip}" -Credential $cred -LoadUserProfile -WorkingDirectory "C:\\" -ErrorAction Stop
            } catch {
                $err = $_.Exception.Message
                Set-Content -Path "$env:TEMP\\msra_debug.txt" -Value "Error launching MSRA: $err"
            }
        }
      `
      spawn('powershell', ['-Command', command])
    } else {
      spawn('msra', ['/offerRA', ip])
    }
    return true
  })

  ipcMain.handle('open-external', async (_: any, url: string) => {
    const { shell } = require('electron')
    await shell.openExternal(url)
    return true
  })

  ipcMain.handle('launch-teamviewer', async (_: any, id?: string) => {
    const paths = [
      'C:\\Program Files\\TeamViewer\\TeamViewer.exe',
      'C:\\Program Files (x86)\\TeamViewer\\TeamViewer.exe'
    ]

    for (const p of paths) {
      try {
        const fs = require('fs')
        if (fs.existsSync(p)) {
          const args = id ? ['-i', id] : []
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
})
