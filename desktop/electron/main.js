const { app, BrowserWindow, Menu, Tray, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow
let tray = null
let backendProcess = null

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'LivingTree AI Agent',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      devTools: process.env.NODE_ENV !== 'production'
    },
    icon: path.join(__dirname, '../client/public/favicon.ico')
  })

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../client/dist/index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.on('minimize', (e) => {
    e.preventDefault()
    mainWindow.hide()
  })
}

const createTray = () => {
  tray = new Tray(path.join(__dirname, '../client/public/favicon.ico'))
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示', click: () => mainWindow.show() },
    { label: '退出', click: () => {
      if (backendProcess) backendProcess.kill()
      app.quit()
    }}
  ])
  tray.setToolTip('LivingTree AI Agent')
  tray.setContextMenu(contextMenu)
  tray.on('click', () => mainWindow.show())
}

const startBackend = () => {
  const backendPath = path.join(__dirname, '../server/main.py')
  backendProcess = spawn('python', [backendPath], {
    cwd: path.join(__dirname, '../server')
  })

  backendProcess.stdout.on('data', (data) => {
    console.log(`Backend: ${data}`)
  })

  backendProcess.stderr.on('data', (data) => {
    console.error(`Backend error: ${data}`)
  })

  backendProcess.on('close', (code) => {
    console.log(`Backend process closed with code ${code}`)
  })
}

app.whenReady().then(() => {
  startBackend()
  createWindow()
  createTray()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (backendProcess) backendProcess.kill()
    app.quit()
  }
})

app.on('quit', () => {
  if (backendProcess) backendProcess.kill()
})

ipcMain.on('minimize-window', () => {
  mainWindow.minimize()
})

ipcMain.on('close-window', () => {
  if (backendProcess) backendProcess.kill()
  app.quit()
})