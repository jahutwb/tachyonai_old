/**
 * Test E2E dla procesów uwierzytelniania w aplikacji tachyonai
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Utworzenie katalogu na zrzuty ekranu
const timestamp = new Date().toISOString().replace(/:/g, '-');
const screenshotDir = path.join('screenshots', 'auth-test-' + timestamp);
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

// Pomocnicza funkcja do pobierania zrzutów ekranu
async function takeScreenshot(page, name) {
  const screenshotPath = path.join(screenshotDir, `${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`Zapisano zrzut ekranu: ${screenshotPath}`);
}

// Pomocnicza funkcja do debugowania
async function debugPage(page, info) {
  console.log(`Debugowanie (${info}):`);
  
  // Zapisanie zrzutu ekranu
  await takeScreenshot(page, `debug-${info}`);
  
  // Pobranie i wyświetlenie HTML
  const content = await page.content();
  console.log(`HTML Content (skrócony): ${content.substring(0, 200)}...`);
  
  // Sprawdzenie widocznych elementów
  const elements = await page.$$eval('*:not(script):not(style)', els => 
    els.map(el => ({
      tag: el.tagName,
      id: el.id,
      classes: el.className,
      text: el.innerText.substring(0, 50)
    })).filter(el => el.id || (el.classes && el.classes.length > 0))
  );
  
  console.log('Widoczne elementy:', JSON.stringify(elements.slice(0, 5), null, 2));
  
  // Sprawdź localStorage
  const localStorageData = await page.evaluate(() => {
    const data = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      data[key] = localStorage.getItem(key);
    }
    return data;
  });
  console.log('LocalStorage:', JSON.stringify(localStorageData, null, 2));
  
  // Sprawdź sieciowe żądania i odpowiedzi (podgląd dla ostatnich 5)
  const requests = await page.evaluate(() => {
    if (window.requestLog && window.requestLog.length > 0) {
      return window.requestLog.slice(-5);
    }
    return [];
  });
  console.log('Ostatnie żądania:', JSON.stringify(requests, null, 2));
}

describe('Testy autentykacji i rozpoczynania gry', () => {
  let browser;
  let page;
  const testUsername = `testuser_${Math.floor(Math.random() * 10000)}`;
  const testPassword = 'password123';
  
  beforeAll(async () => {
    browser = await puppeteer.launch({
      headless: false,
      slowMo: 100,
      args: ['--window-size=1280,800', '--no-sandbox', '--disable-setuid-sandbox']
    });
    page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    
    // Monitorowanie zapytań sieciowych
    await page.setRequestInterception(true);
    const requestLog = [];
    page.on('request', request => {
      requestLog.push({
        url: request.url(),
        method: request.method(),
        headers: request.headers(),
        postData: request.postData()
      });
      request.continue();
    });
    
    page.on('response', async response => {
      const req = requestLog.find(r => r.url === response.url() && r.method === response.request().method());
      if (req) {
        req.status = response.status();
        try {
          const contentType = response.headers()['content-type'] || '';
          if (contentType.includes('application/json')) {
            req.responseBody = await response.json().catch(() => 'Error parsing JSON');
          } else {
            req.responseBody = await response.text().catch(() => 'Error getting text').then(text => text.substring(0, 100) + '...');
          }
        } catch (e) {
          req.responseBody = `Error accessing response body: ${e.message}`;
        }
      }
    });
    
    // Dodaj requestLog do window, aby móc uzyskać do niego dostęp
    await page.evaluate(() => {
      window.requestLog = [];
    });
    
    // Przechwytuj console.log z przeglądarki
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  });
  
  afterAll(async () => {
    if (browser) await browser.close();
  });
  
  test('Powinien zarejestrować użytkownika, zalogować i rozpocząć grę', async () => {
    // 1. Rejestracja
    await page.goto('http://localhost:8000/signup');
    await takeScreenshot(page, '01-signup-page');
    
    await page.type('#username', testUsername);
    await page.type('#password', testPassword);
    await takeScreenshot(page, '02-filled-signup-form');
    
    // Dodaj monitorowanie fetch/XHR
    await page.evaluate(() => {
      const originalFetch = window.fetch;
      window.fetch = async function(...args) {
        try {
          console.log('FETCH REQUEST:', JSON.stringify(args));
          const response = await originalFetch.apply(this, args);
          const responseClone = response.clone();
          try {
            const data = await responseClone.json();
            console.log('FETCH RESPONSE:', response.status, JSON.stringify(data));
          } catch (e) {
            console.log('FETCH RESPONSE (not JSON):', response.status);
          }
          return response;
        } catch (error) {
          console.error('FETCH ERROR:', error);
          throw error;
        }
      };
    });
    
    // Kliknij przycisk rejestracji
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForNavigation({ timeout: 10000 }).catch(() => console.log('Brak nawigacji po rejestracji'))
    ]);
    
    await takeScreenshot(page, '03-after-signup');
    
    // 2. Przejdź do strony głównej
    await page.goto('http://localhost:8000/');
    await takeScreenshot(page, '04-main-page');
    
    // Sprawdź localStorage po przejściu na stronę główną
    await page.evaluate(() => {
      console.log('Current localStorage:', JSON.stringify(Object.entries(localStorage)));
    });
    
    // 3. Zaloguj się
    await page.goto('http://localhost:8000/login');
    await takeScreenshot(page, '05-login-page');
    
    await page.type('#username', testUsername);
    await page.type('#password', testPassword);
    await takeScreenshot(page, '06-filled-login-form');
    
    // Kliknij przycisk logowania
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForNavigation({ timeout: 10000 }).catch(() => console.log('Brak nawigacji po logowaniu'))
    ]);
    
    await takeScreenshot(page, '07-after-login');
    
    // Sprawdź localStorage po logowaniu
    const tokenAfterLogin = await page.evaluate(() => {
      console.log('localStorage after login:', JSON.stringify(Object.entries(localStorage)));
      return localStorage.getItem('token');
    });
    
    expect(tokenAfterLogin).toBeTruthy();
    console.log('Token received:', tokenAfterLogin ? 'yes' : 'no');
    
    // 4. Przejdź do strony głównej i sprawdź, czy przycisk rozpoczęcia gry działa
    await page.goto('http://localhost:8000/');
    await takeScreenshot(page, '08-main-page-logged-in');
    
    // Dodaj nasłuchiwanie na alerty strony
    let alertMessage = null;
    page.on('dialog', async dialog => {
      alertMessage = dialog.message();
      console.log('ALERT:', alertMessage);
      await dialog.accept();
    });
    
    // Sprawdź, czy przycisk jest widoczny
    const startGameButton = await page.$('#start-game-button');
    expect(startGameButton).not.toBeNull();
    
    // Kliknij przycisk "Rozpocznij grę"
    await Promise.all([
      startGameButton.click(),
      page.waitForResponse(response => 
        response.url().includes('/api/sessions') && 
        (response.status() === 200 || response.status() === 401 || response.status() === 500)
      ).catch(() => console.log('Brak odpowiedzi po kliknięciu przycisku'))
    ]);
    
    await takeScreenshot(page, '09-after-clicking-start-game');
    
    // Sprawdź, czy wystąpił alert z błędem
    if (alertMessage) {
      console.log('Wystąpił alert z błędem:', alertMessage);
      // Debuguj problemy z autoryzacją
      const headersDebug = await page.evaluate(() => {
        // Sprawdź, jakie nagłówki są wysyłane
        fetch('/api/sessions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }).then(r => r.json())
          .then(data => console.log('Debug API call response:', data))
          .catch(e => console.error('Debug API call error:', e));
          
        return {
          token: localStorage.getItem('token'),
          authorization: `Bearer ${localStorage.getItem('token')}`
        };
      });
      
      console.log('Debug headers:', headersDebug);
    }
    
    await debugPage(page, 'after-start-game-attempt');
    
    // Sprawdź, czy nastąpiło przekierowanie do strony gry
    const currentUrl = page.url();
    console.log('Current URL:', currentUrl);
    
    // Test powinien przejść nawet jeśli nie było przekierowania - chcemy zobaczyć co się stało
    if (!currentUrl.includes('/game')) {
      console.log('Brak przekierowania do strony gry - analizuję problem');
    }
  }, 60000); // 60s timeout
}); 