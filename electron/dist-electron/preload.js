"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("electron", {
  ipcRenderer: {
    on(...args) {
      const [channel, listener] = args;
      return electron.ipcRenderer.on(channel, (event, ...args2) => listener(event, ...args2));
    },
    off(...args) {
      const [channel, ...omit] = args;
      return electron.ipcRenderer.off(channel, ...omit);
    },
    send(...args) {
      const [channel, ...omit] = args;
      return electron.ipcRenderer.send(channel, ...omit);
    },
    invoke(...args) {
      const [channel, ...omit] = args;
      return electron.ipcRenderer.invoke(channel, ...omit);
    }
  },
  launchRdp: (ip) => electron.ipcRenderer.invoke("launch-rdp", ip),
  launchMsra: (ip, askCredentials) => electron.ipcRenderer.invoke("launch-msra", ip, askCredentials),
  launchTeamViewer: (id) => electron.ipcRenderer.invoke("launch-teamviewer", id),
  openExternal: (url) => electron.ipcRenderer.invoke("open-external", url),
  getLocalDomain: () => electron.ipcRenderer.invoke("get-local-domain")
});
