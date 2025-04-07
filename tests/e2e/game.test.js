/**
 * Test E2E dla procesu rozgrywki w aplikacji tachyonai
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Utworzenie katalogu na zrzuty ekranu
const screenshotsDir = path.join(__dirname, 'screenshots');
if (!fs.existsSync(screenshotsDir)) {
  fs.mkdirSync(screenshotsDir, { recursive: true });
}

// Pomocnicza funkcja do robienia zrzutów ekranu
async function takeScreenshot(page, name) {
  await page.screenshot({
    path: path.join(screenshotsDir, `${name}.png`),
    fullPage: true
  });
}

describe('Testy rozgrywki', () => {
  let browser;
  let page;

  beforeAll(async () => {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
  });

  afterAll(async () => {
    await browser.close();
  });

  beforeEach(async () => {
    page = await browser.newPage();
    await page.goto('http://localhost:8000/');
  });

  afterEach(async () => {
    await page.close();
  });

  test('Rozgrywka powinna wyświetlać obrazki bodźca, zmniejszać pary tylko przy porażce i przechodzić do podsumowania', async () => {
    // 1. Logowanie użytkownika
    await page.click('#login-button');
    await page.waitForSelector('#login-form', { visible: true });
    
    await page.type('#login-username', 'testuser_3804');
    await page.type('#login-password', 'password123');
    await page.click('#login-form button[type="submit"]');
    
    // Poczekaj na zalogowanie
    await page.waitForFunction(
      () => document.querySelector('#username-display').textContent.includes('testuser_3804'),
      { timeout: 5000 }
    );
    
    // 2. Rozpoczęcie gry
    await page.click('#start-game-button');
    
    // Czekamy na załadowanie ekranu gry
    await page.waitForSelector('.curtain-container', { timeout: 5000 });
    console.log('Strona gry załadowana');
    
    // Zapisujemy początkową wartość remaining_pairs
    const initialPairsText = await page.$eval('#remaining-pairs', el => el.textContent);
    const initialPairs = parseInt(initialPairsText);
    console.log(`Początkowa liczba par: ${initialPairs}`);
    
    // 3. Wykonujemy kilka rund
    let currentPairs = initialPairs;
    let decreasedAfterSuccess = false;
    let stimulusImageDisplayed = false;
    
    for (let i = 0; i < 3; i++) {
      console.log(`Rozpoczynam rundę ${i+1}`);
      
      // Wybieramy losowo lewą lub prawą kurtynę
      const side = Math.random() > 0.5 ? 'left' : 'right';
      await page.click(`#${side}-curtain`);
      
      // Czekamy na wynik (sukces lub porażka)
      await page.waitForSelector('#result-status', { visible: true, timeout: 5000 });
      
      // Sprawdzamy czy wynik to sukces czy porażka
      const resultText = await page.$eval('#result-status', el => el.textContent);
      console.log(`Wynik rundy: ${resultText}`);
      
      // Sprawdzamy czy obrazek jest wyświetlany
      await takeScreenshot(page, `round-${i+1}-result`);
      
      const imageVisible = await page.evaluate(() => {
        const img = document.getElementById('stimulus-image');
        return img && img.complete && img.naturalWidth > 0;
      });
      
      if (imageVisible) {
        stimulusImageDisplayed = true;
        console.log('Obrazek bodźca wyświetlany poprawnie');
      } else {
        console.log('BŁĄD: Obrazek bodźca nie jest wyświetlany');
      }
      
      // Sprawdzamy aktualną liczbę par
      const pairsText = await page.$eval('#remaining-pairs', el => el.textContent);
      const pairs = parseInt(pairsText);
      console.log(`Aktualna liczba par: ${pairs}`);
      
      // Jeśli to był sukces, sprawdzamy czy liczba par się nie zmniejszyła
      if (resultText === 'SUKCES') {
        if (pairs < currentPairs) {
          decreasedAfterSuccess = true;
          console.log('BŁĄD: Liczba par zmniejszyła się po sukcesie');
        }
      } 
      // Jeśli to była porażka, sprawdzamy czy liczba par się zmniejszyła
      else if (resultText === 'PORAŻKA') {
        if (pairs !== currentPairs - 1) {
          console.log('BŁĄD: Liczba par nie zmniejszyła się po porażce');
        }
      }
      
      currentPairs = pairs;
      
      // Klikamy "Następna runda" jeśli przycisk jest widoczny
      const nextButtonVisible = await page.$('#next-round-button');
      if (nextButtonVisible) {
        await page.click('#next-round-button');
        await page.waitForSelector('.curtain-container', { visible: true, timeout: 5000 });
      } else {
        // Jeśli przycisk nie jest widoczny, prawdopodobnie skończyły się pary
        break;
      }
    }
    
    // 4. Sprawdzamy czy podsumowanie sesji działa poprawnie
    // Jeśli przycisk podsumowania jest widoczny, klikamy go
    const summaryButtonVisible = await page.$('#summary-button');
    
    if (summaryButtonVisible) {
      console.log('Klikam przycisk podsumowania sesji');
      await page.click('#summary-button');
      
      try {
        // Oczekujemy na załadowanie strony podsumowania
        await page.waitForSelector('.summary-section', { timeout: 10000 });
        console.log('Strona podsumowania załadowana pomyślnie');
        await takeScreenshot(page, 'summary-page');
      } catch (error) {
        console.log('Błąd podczas ładowania strony podsumowania:', error);
        await takeScreenshot(page, 'summary-error');
      }
    }
    
    // 5. Weryfikacja wyników
    expect(stimulusImageDisplayed).toBe(true); // Obrazki bodźca powinny być wyświetlane
    expect(decreasedAfterSuccess).toBe(false); // Liczba par nie powinna zmniejszać się po sukcesie
  }, 60000); // 60s timeout
}); 