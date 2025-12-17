"use strict";
Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
const electron = require("electron");
const node_url = require("node:url");
const path = require("node:path");
const node_child_process = require("node:child_process");
var _documentCurrentScript = typeof document !== "undefined" ? document.currentScript : null;
const __dirname$1 = path.dirname(node_url.fileURLToPath(typeof document === "undefined" ? require("url").pathToFileURL(__filename).href : _documentCurrentScript && _documentCurrentScript.tagName.toUpperCase() === "SCRIPT" && _documentCurrentScript.src || new URL("main.js", document.baseURI).href));
process.env.APP_ROOT = path.join(__dirname$1, "..");
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
const MAIN_DIST = path.join(process.env.APP_ROOT, "dist-electron");
const RENDERER_DIST = path.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, "public") : RENDERER_DIST;
let win;
let pythonProcess = null;
function startPythonBackend() {
  var _a, _b;
  let pythonExecutable = "python";
  let scriptArgs = [];
  let cwd = process.env.APP_ROOT;
  if (electron.app.isPackaged) {
    const serverPath = path.join(process.resourcesPath, "server", "server.exe");
    pythonExecutable = serverPath;
    scriptArgs = [];
    cwd = path.join(process.resourcesPath, "server");
    console.log(`Iniciando backend Python (Prod): ${serverPath}`);
  } else {
    const pythonDir = path.join(process.env.APP_ROOT, "..", "python");
    const scriptPath = path.join(pythonDir, "api", "server.py");
    pythonExecutable = "python";
    scriptArgs = ["-u", scriptPath];
    cwd = pythonDir;
    console.log(`Iniciando backend Python (Dev): ${pythonExecutable} ${scriptPath}`);
    console.log(`CWD: ${cwd}`);
  }
  pythonProcess = node_child_process.spawn(pythonExecutable, scriptArgs, {
    cwd,
    stdio: ["ignore", "pipe", "pipe"]
  });
  (_a = pythonProcess.stdout) == null ? void 0 : _a.on("data", (data) => {
    console.log(`[Python API]: ${data}`);
  });
  (_b = pythonProcess.stderr) == null ? void 0 : _b.on("data", (data) => {
    console.error(`[Python API Error]: ${data}`);
  });
  pythonProcess.on("close", (code, signal) => {
    console.log(`Backend Python encerrado. Código: ${code}, Sinal: ${signal}`);
  });
  pythonProcess.on("error", (err) => {
    console.error(`Falha ao iniciar backend Python: ${err}`);
  });
}
function killPythonBackend() {
  if (pythonProcess) {
    console.log("Encerrando backend Python...");
    if (!pythonProcess.killed) {
      pythonProcess.kill();
    }
    pythonProcess = null;
  }
}
function createWindow() {
  win = new electron.BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1200,
    minHeight: 800,
    title: "Ferramentas de Rede",
    backgroundColor: "#09090b",
    // Dark background to match loader (prevents white flash)
    icon: path.join(process.env.VITE_PUBLIC, "icon.png"),
    webPreferences: {
      preload: path.join(__dirname$1, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  win.removeMenu();
  win.webContents.on("did-finish-load", () => {
    win == null ? void 0 : win.webContents.send("main-process-message", (/* @__PURE__ */ new Date()).toLocaleString());
  });
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(RENDERER_DIST, "index.html"));
  }
  win.on("focus", () => {
    win == null ? void 0 : win.webContents.send("window-focus-change", true);
  });
  win.on("blur", () => {
    win == null ? void 0 : win.webContents.send("window-focus-change", false);
  });
}
electron.app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    killPythonBackend();
    electron.app.quit();
    win = null;
  }
});
electron.app.on("activate", () => {
  if (electron.BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
electron.app.on("before-quit", () => {
  killPythonBackend();
});
electron.app.whenReady().then(() => {
  startPythonBackend();
  createWindow();
  const { ipcMain } = require("electron");
  ipcMain.handle("launch-rdp", async (_, ip) => {
    node_child_process.spawn("mstsc", ["/v:" + ip]);
    return true;
  });
  ipcMain.handle("launch-msra", async (_, ip, askCredentials) => {
    if (askCredentials) {
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
      `;
      node_child_process.spawn("powershell", ["-Command", command]);
    } else {
      node_child_process.spawn("msra", ["/offerRA", ip]);
    }
    return true;
  });
  ipcMain.handle("open-external", async (_, url) => {
    const { shell } = require("electron");
    await shell.openExternal(url);
    return true;
  });
  ipcMain.handle("launch-teamviewer", async (_, id) => {
    const paths = [
      "C:\\Program Files\\TeamViewer\\TeamViewer.exe",
      "C:\\Program Files (x86)\\TeamViewer\\TeamViewer.exe"
    ];
    for (const p of paths) {
      try {
        const fs = require("fs");
        if (fs.existsSync(p)) {
          const args = id ? ["-i", id] : [];
          node_child_process.spawn(p, args);
          return true;
        }
      } catch (e) {
        console.error(`Error checking path ${p}:`, e);
      }
    }
    return false;
  });
  ipcMain.handle("get-local-domain", async () => {
    return process.env.USERDNSDOMAIN || process.env.USERDOMAIN || "";
  });
});
exports.MAIN_DIST = MAIN_DIST;
exports.RENDERER_DIST = RENDERER_DIST;
exports.VITE_DEV_SERVER_URL = VITE_DEV_SERVER_URL;
