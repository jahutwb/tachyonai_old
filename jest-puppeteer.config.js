module.exports = {
  server: {
    command: 'python -m uvicorn backend.main:app --port 8000',
    port: 8000,
    launchTimeout: 10000,
    debug: true,
  },
  launch: {
    headless: true,
    slowMo: 50,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  }
}; 