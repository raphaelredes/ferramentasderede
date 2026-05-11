import { ipcRenderer, contextBridge } from 'electron'

// Bridge typed helpers only. The previous version exposed a generic
// `ipcRenderer` (on/send/invoke for any channel) which weakened the security
// model: an XSS in the renderer could call any handler the main process
// registers, including future ones added without review. Now every IPC call
// in the renderer goes through one of these named, validated helpers.

contextBridge.exposeInMainWorld('electron', {
  launchRdp: (ip: string) => ipcRenderer.invoke('launch-rdp', ip),
  launchMsra: (ip: string, askCredentials?: boolean) =>
    ipcRenderer.invoke('launch-msra', ip, askCredentials),
  launchTeamViewer: (id?: string) => ipcRenderer.invoke('launch-teamviewer', id),
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
  getLocalDomain: () => ipcRenderer.invoke('get-local-domain'),
  showItemInFolder: (path: string) => ipcRenderer.invoke('show-item-in-folder', path),
  saveFileAs: (filename: string, content: string) =>
    ipcRenderer.invoke('save-file-as', filename, content),

  // Subscribe to focus changes pushed by the main process. Returns an
  // unsubscribe function so the renderer can clean up on unmount — previously
  // the listener leaked across React StrictMode remounts.
  onWindowFocusChange: (callback: (focused: boolean) => void) => {
    const handler = (_event: unknown, focused: boolean) => callback(focused)
    ipcRenderer.on('window-focus-change', handler)
    return () => ipcRenderer.removeListener('window-focus-change', handler)
  },
})
