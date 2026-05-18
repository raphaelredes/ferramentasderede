/// <reference types="vite-plugin-electron/electron-env" />

declare namespace NodeJS {
  interface ProcessEnv {
    /**
     * The built directory structure
     *
     * ```tree
     * ├─┬─┬ dist
     * │ │ └── index.html
     * │ │
     * │ ├─┬ dist-electron
     * │ │ ├── main.js
     * │ │ └── preload.js
     * │
     * ```
     */
    APP_ROOT: string
    /** /dist/ or /public/ */
    VITE_PUBLIC: string
  }
}

// Used in Renderer process, expose in `preload.ts`.
// The renderer no longer receives a generic `ipcRenderer` — preload exposes the
// `electron` bridge below with a narrow, named surface.
interface ElectronBridge {
  launchRdp: (ip: string) => Promise<boolean>
  launchMsra: (ip: string, askCredentials?: boolean) => Promise<boolean>
  launchTeamViewer: (id?: string) => Promise<boolean>
  openExternal: (url: string) => Promise<boolean>
  getLocalDomain: () => Promise<string>
  showItemInFolder: (path: string) => Promise<boolean>
  saveFileAs: (filename: string, content: string) => Promise<string | null>
  onWindowFocusChange: (callback: (focused: boolean) => void) => () => void
}

interface Window {
  electron: ElectronBridge
}
