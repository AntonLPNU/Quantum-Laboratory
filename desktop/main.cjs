'use strict';

const { app, BrowserWindow, Menu, dialog, screen, session, shell } = require('electron');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const APP_ID = 'ua.lpnu.quantumlaboratory';
const WINDOW_FILE = 'window-state.json';
let backend = null;
let mainWindow = null;
let appOrigin = null;
let quitting = false;

function log(message) {
  const profile = process.env.USERPROFILE || '';
  const safe = (profile ? String(message).replaceAll(profile, '<user>') : String(message))
    .replace(/[\r\n]/g, ' ').slice(0, 500);
  try {
    const folder = path.join(app.getPath('userData'), 'logs');
    fs.mkdirSync(folder, { recursive: true });
    fs.appendFileSync(path.join(folder, 'desktop.log'), `${new Date().toISOString()} ${safe}\n`);
  } catch (_) { /* A log failure must not prevent application shutdown. */ }
}

function backendPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'backend', 'QuantumLaboratoryCore.exe')
    : path.join(__dirname, 'build', 'QuantumLaboratoryCore', 'QuantumLaboratoryCore.exe');
}

function startBackend(executable, token, recordsDir) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(executable)) return reject(new Error(`Вбудоване Python-ядро відсутнє: ${executable}`));
    const child = spawn(executable, [], {
      cwd: path.dirname(executable), windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, QUANTUM_LAB_DESKTOP_TOKEN: token,
        QUANTUM_LAB_DESKTOP_RECORDS: recordsDir },
    });
    backend = child;
    let pending = '';
    let settled = false;
    const timer = setTimeout(() => fail(new Error('Python API не запустився за 45 секунд.')), 45000);
    function fail(error) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
    }
    child.on('error', fail);
    child.on('exit', (code) => {
      if (!quitting) log(`Backend exited with code ${code}`);
      if (!settled) fail(new Error(`Python-ядро завершило роботу до запуску (код ${code}).`));
      else if (!quitting && mainWindow && !mainWindow.isDestroyed()) {
        dialog.showErrorBox('Quantum Laboratory', 'Python-ядро несподівано завершило роботу. Перезапустіть програму.');
      }
    });
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      pending += chunk;
      if (pending.length > 16384) pending = pending.slice(-16384);
      let newline;
      while ((newline = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, newline).trim();
        pending = pending.slice(newline + 1);
        if (line.startsWith('QL_READY ')) {
          try {
            const port = JSON.parse(line.slice(9)).port;
            if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('invalid backend port');
            if (!settled) { settled = true; clearTimeout(timer); resolve(port); }
          } catch (error) { fail(error); }
        } else if (line.startsWith('QL_ERROR ')) log(line);
      }
    });
    child.stderr.setEncoding('utf8');
    child.stderr.on('data', (chunk) => log(`Backend diagnostic: ${String(chunk).slice(0, 300)}`));
  });
}

function healthCheck(port, token) {
  return new Promise((resolve, reject) => {
    const req = http.get({ hostname: '127.0.0.1', port, path: '/api/health', timeout: 3000,
      headers: { Host: `127.0.0.1:${port}`, 'X-Quantum-Lab-Token': token } }, (res) => {
      let body = '';
      res.on('data', (part) => { body += part; if (body.length > 4096) req.destroy(); });
      res.on('end', () => {
        try {
          if (res.statusCode !== 200 || JSON.parse(body).status !== 'ok') throw new Error('API health check failed');
          resolve();
        } catch (error) { reject(error); }
      });
    });
    req.on('timeout', () => req.destroy(new Error('API health check timed out')));
    req.on('error', reject);
  });
}

function windowBounds() {
  const fallback = { width: 1440, height: 900 };
  try {
    const saved = JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), WINDOW_FILE), 'utf8'));
    if (![saved.x, saved.y, saved.width, saved.height].every(Number.isFinite)) return fallback;
    const valid = screen.getAllDisplays().some(({ workArea }) =>
      saved.x < workArea.x + workArea.width - 100 && saved.x + saved.width > workArea.x + 100 &&
      saved.y < workArea.y + workArea.height - 100 && saved.y + saved.height > workArea.y + 100);
    return valid ? { x: saved.x, y: saved.y, width: Math.max(960, saved.width), height: Math.max(640, saved.height) } : fallback;
  } catch (_) { return fallback; }
}

function saveWindowBounds() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  try {
    const bounds = mainWindow.isMaximized() ? mainWindow.getNormalBounds() : mainWindow.getBounds();
    fs.writeFileSync(path.join(app.getPath('userData'), WINDOW_FILE), JSON.stringify(bounds));
  } catch (error) { log(`Could not save window bounds: ${error.message}`); }
}

function openExternal(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'https:') void shell.openExternal(parsed.href);
  } catch (_) { /* Reject malformed URLs. */ }
}

function createWindow(port, token) {
  appOrigin = `http://127.0.0.1:${port}`;
  const privateSession = session.fromPartition('quantum-laboratory-private');
  privateSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  privateSession.webRequest.onBeforeSendHeaders((details, callback) => {
    const headers = { ...details.requestHeaders };
    if (new URL(details.url).origin === appOrigin) headers['X-Quantum-Lab-Token'] = token;
    callback({ requestHeaders: headers });
  });
  privateSession.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: new URL(details.url).origin !== appOrigin });
  });
  mainWindow = new BrowserWindow({
    ...windowBounds(), minWidth: 960, minHeight: 640, show: false,
    title: 'Quantum Laboratory', icon: path.join(__dirname, 'assets', 'icon.ico'),
    webPreferences: {
      partition: 'quantum-laboratory-private', contextIsolation: true,
      nodeIntegration: false, sandbox: true, webSecurity: true,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { openExternal(url); return { action: 'deny' }; });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (new URL(url).origin !== appOrigin) { event.preventDefault(); openExternal(url); }
  });
  mainWindow.on('close', saveWindowBounds);
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.loadURL(appOrigin).catch((error) => {
    log(`Could not load UI: ${error.message}`);
    dialog.showErrorBox('Quantum Laboratory', 'Не вдалося завантажити інтерфейс. Перезапустіть програму.');
  });
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Файл', submenu: [{ label: 'Закрити Quantum Laboratory', role: 'quit' }] },
    { label: 'Вікно', submenu: [
      { label: 'Згорнути', role: 'minimize' }, { label: 'Розгорнути', role: 'maximize' },
      { label: 'Відновити', role: 'restore' }, { type: 'separator' },
      { label: 'Масштаб 100%', role: 'resetZoom' },
    ] },
    { label: 'Довідка', submenu: [{ label: 'Про програму', click: () => dialog.showMessageBox(mainWindow, {
      type: 'info', title: 'Quantum Laboratory', message: 'Quantum Laboratory 0.5.0 Research Preview',
      detail: 'Науковий Python-рушій працює локально. Просторове розташування спінів на 3D-сцені є схематичним.',
    }) }] },
  ]));
}

function stopBackend() {
  if (!backend || backend.killed || backend.exitCode !== null) return;
  backend.stdin.end();
  const ownedProcess = backend;
  const timeout = setTimeout(() => { if (ownedProcess.exitCode === null) ownedProcess.kill(); }, 5000);
  timeout.unref();
  ownedProcess.once('exit', () => clearTimeout(timeout));
}

app.setAppUserModelId(APP_ID);
app.on('before-quit', () => { quitting = true; stopBackend(); });
app.on('window-all-closed', () => app.quit());
app.whenReady().then(async () => {
  const token = crypto.randomBytes(32).toString('hex');
  const recordsDir = path.join(app.getPath('userData'), 'experiments');
  try {
    fs.mkdirSync(recordsDir, { recursive: true });
    const port = await startBackend(backendPath(), token, recordsDir);
    await healthCheck(port, token);
    createWindow(port, token);
  } catch (error) {
    log(`Startup failed: ${error.message}`);
    dialog.showErrorBox('Quantum Laboratory — помилка запуску', `${error.message}\n\nЖурнал: ${path.join(app.getPath('userData'), 'logs', 'desktop.log')}`);
    app.quit();
  }
});
