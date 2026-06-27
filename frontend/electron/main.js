import { app, BrowserWindow, nativeImage, Tray, ipcMain } from 'electron';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const STORE_FILE = 'window-state.json';

function getStorePath() {
  return path.join(app.getPath('userData'), STORE_FILE);
}

function loadWindowState() {
  try {
    const filePath = getStorePath();
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    }
  } catch (error) {
    console.warn('Failed to load window state', error);
  }
  return { width: 1400, height: 900 }; 
}

function saveWindowState(window) {
  if (!window) return;
  const bounds = window.getBounds();
  fs.writeFileSync(getStorePath(), JSON.stringify(bounds), 'utf-8');
}

function createTray() {
  const iconSvg = `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' rx='16' fill='#07101f'/><circle cx='32' cy='32' r='18' fill='none' stroke='#0ea5e9' stroke-width='4'/><circle cx='32' cy='32' r='8' fill='#0ea5e9'/></svg>`;
  const image = nativeImage.createFromDataURL(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(iconSvg)}`);
  const tray = new Tray(image);
  tray.setToolTip('ULTRA-Z');
  return tray;
}

let mainWindow = null;
let tray = null;

async function createMainWindow() {
  const state = loadWindowState();
  mainWindow = new BrowserWindow({
    width: state.width,
    height: state.height,
    minWidth: 1100,
    minHeight: 700,
    title: 'ULTRA-Z',
    backgroundColor: '#050816',
    show: false,
    autoHideMenuBar: true,
    frame: false,
    transparent: true,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  const url = app.isPackaged
    ? `file://${path.join(process.resourcesPath, 'app', 'index.html')}`
    : 'http://127.0.0.1:5173';

  await mainWindow.loadURL(url);

  mainWindow.on('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('close', () => saveWindowState(mainWindow));
  mainWindow.on('minimize', (event) => {
    event.preventDefault();
    mainWindow.hide();
  });

  tray = createTray();
  tray.on('click', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  tray.setContextMenu(null);
}

app.whenReady().then(async () => {
  await createMainWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    } else {
      mainWindow?.show();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

ipcMain.on('window-minimize', () => {
  mainWindow?.hide();
});

ipcMain.on('window-restore', () => {
  mainWindow?.show();
  mainWindow?.focus();
});
