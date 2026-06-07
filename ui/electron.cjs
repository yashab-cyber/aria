const { app, BrowserWindow } = require('electron');
const path = require('path');

// Disable GPU / Hardware acceleration to bypass permission/driver issues with /dev/dri
app.disableHardwareAcceleration();

// Disable security warning for local self-signed SSL certs
app.commandLine.appendSwitch('ignore-certificate-errors');
// Disable sandbox if running in restricted permission environments (like Kali root/Docker)
app.commandLine.appendSwitch('no-sandbox');
// Disable /dev/shm usage and fallback to temporary files for shared memory
app.commandLine.appendSwitch('disable-dev-shm-usage');

function createWindow() {
  const win = new BrowserWindow({
    width: 1300,
    height: 880,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    backgroundColor: '#06060c',
    autoHideMenuBar: true,
    title: "A.R.I.A. Agent Terminal"
  });

  // Determine environment
  const isDev = process.env.NODE_ENV === 'development' || process.argv.includes('--dev');

  if (isDev) {
    win.loadURL('https://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
