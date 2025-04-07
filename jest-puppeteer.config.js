module.exports = {
  server: {
    command: 'python -m uvicorn backend.main:app --port 8000',
    port: 8000,
    launchTimeout: 10000,
    debug: true,
    usedPortAction: 'kill'
  },
  launch: {
    headless: "new",
    slowMo: 50,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  }
}; 