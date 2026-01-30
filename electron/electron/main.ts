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
    },
  })

  win.removeMenu()

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

app.whenReady().then(() => {
  logToFile('app.whenReady fired');
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

  ipcMain.handle('show-item-in-folder', async (_: any, path: string) => {
    const { shell } = require('electron')
    shell.showItemInFolder(path)
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

  ipcMain.handle('save-file-as', async (_: any, filename: string, content: string) => {
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
