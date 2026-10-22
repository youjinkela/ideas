const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/e2e', testMatch: '**/*.spec.js', workers: 1,
  use: { baseURL: 'http://127.0.0.1:47831', channel: 'msedge', headless: true, viewport: { width: 1440, height: 1000 } },
  webServer: { command: '.venv\\Scripts\\python.exe scripts/serve-e2e.py', url: 'http://127.0.0.1:47831/local/session', reuseExistingServer: false, timeout: 30000 },
});
