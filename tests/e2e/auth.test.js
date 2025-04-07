/**
 * Test E2E dla pełnego procesu: logowanie > rozgrywka > podsumowanie sesji
 */

const puppeteer = require('puppeteer');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

// Globalne zmienne pomocnicze
let browser;
let page;
let sessionId;

// Konfiguracja testów
const API_URL = 'http://localhost:8000';
const TEST_USER = {
  username: 'testuser_3804',
  password: 'password123'
};

// Helper do czekania
const waitForTimeout = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Utwórz katalog na zrzuty ekranu, jeśli nie istnieje
const screenshotsDir = path.join(__dirname, 'screenshots');
if (!fs.existsSync(screenshotsDir)) {
  fs.mkdirSync(screenshotsDir, { recursive: true });
}

// Funkcja do robienia zrzutów ekranu z nazwą 
async function takeScreenshot(page, name) {
  try {
    const screenshotPath = path.join(screenshotsDir, `${name}-${Date.now()}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`Zapisano zrzut ekranu: ${screenshotPath}`);
    return screenshotPath;
  } catch (error) {
    console.warn(`Nie udało się zapisać zrzutu ekranu ${name}: ${error.message}`);
    return null;
  }
}

describe('Test pełnego procesu od logowania do podsumowania', () => {
  beforeAll(async () => {
    try {
      // Uruchom przeglądarkę
      browser = await puppeteer.launch({
        headless: false, // Headless mode dla stabilności testów
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1366,768'],
        defaultViewport: null
      });
      
      console.log('Przeglądarka uruchomiona');
    } catch (error) {
      console.error('Błąd podczas uruchamiania przeglądarki:', error);
      throw error;
    }
  }, 30000);

  afterAll(async () => {
    if (browser) {
      await browser.close();
      console.log('Przeglądarka zamknięta');
    }
  });

  test('Pełny test: logowanie > rozgrywka > podsumowanie', async () => {
    try {
      // Otwórz nową stronę
      page = await browser.newPage();
      
      // Włącz rejestrowanie logów konsoli
      page.on('console', message => console.log(`[BROWSER LOG]: ${message.text()}`));
      
      // Ustaw timeout dla operacji nawigacji
      page.setDefaultNavigationTimeout(30000);
      
      // ========== KROK 1: LOGOWANIE ==========
      console.log('KROK 1: Logowanie użytkownika testowego');
      
      // Przejdź do strony logowania
      await page.goto(`${API_URL}/login`);
      await takeScreenshot(page, 'login-page');
      
      // Wypełnij formularz logowania
      await page.waitForSelector('form input[name="username"]', { timeout: 10000 });
      await page.type('form input[name="username"]', TEST_USER.username);
      await page.type('form input[name="password"]', TEST_USER.password);
      
      // Wyślij formularz logowania
      await Promise.all([
        page.click('form button[type="submit"]'),
        page.waitForNavigation({ timeout: 15000 })
      ]);
      
      console.log('Zalogowano pomyślnie, sprawdzam przekierowanie');
      await takeScreenshot(page, 'after-login');
      
      // Sprawdź czy jesteśmy zalogowani - powinniśmy być na stronie głównej
      const currentUrl = page.url();
      console.log(`Aktualny URL po logowaniu: ${currentUrl}`);
      expect(currentUrl).toContain(API_URL);
      
      // ========== KROK 2: ROZPOCZĘCIE NOWEJ SESJI ==========
      console.log('KROK 2: Rozpoczynanie nowej sesji gry');
      
      // Kliknij przycisk rozpoczęcia nowej sesji
      await page.waitForSelector('#new-session-btn, .new-session-btn, button:contains("Rozpocznij"), [id*="session"], [class*="session"]', { timeout: 10000 });
      
      // Znajdź elementy które mogą być przyciskiem nowej sesji
      const possibleButtons = await page.$$('button, a.btn, .btn, input[type="button"]');
      console.log(`Znaleziono ${possibleButtons.length} potencjalnych przycisków`);
      
      for (const btn of possibleButtons) {
        const text = await page.evaluate(el => el.textContent, btn);
        console.log(`Przycisk: "${text?.trim()}"`);
      }
      
      // Spróbuj kliknąć pierwszy przycisk który zawiera tekst rozpoczęcia gry
      let clicked = false;
      for (const btn of possibleButtons) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && (text.toLowerCase().includes('rozpocznij') || text.toLowerCase().includes('nowa') || text.toLowerCase().includes('sesja') || text.toLowerCase().includes('gra'))) {
          console.log(`Klikam przycisk: "${text.trim()}"`);
          await Promise.all([
            btn.click(),
            page.waitForNavigation({ timeout: 15000 }).catch(() => console.log('Brak nawigacji po kliknięciu'))
          ]);
          clicked = true;
          break;
        }
      }
      
      if (!clicked) {
        console.log('Nie znaleziono przycisku rozpoczęcia gry, próbuję bezpośrednio przejść do /game');
        await page.goto(`${API_URL}/game`);
      }
      
      await takeScreenshot(page, 'game-start');
      
      // Sprawdź czy jesteśmy na stronie gry
      const gameUrl = page.url();
      console.log(`URL strony gry: ${gameUrl}`);
      
      // Wyciągnij ID sesji z URL jeśli jest dostępne
      if (gameUrl.includes('/game')) {
        const urlParams = new URL(gameUrl).searchParams;
        sessionId = urlParams.get('session_id');
        if (sessionId) {
          console.log(`ID sesji z URL: ${sessionId}`);
        } else {
          // Jeśli nie ma w URL, spróbuj pobrać z localStorage lub z elementu na stronie
          sessionId = await page.evaluate(() => {
            return localStorage.getItem('sessionId') || 
                   document.querySelector('[data-session-id], .session-id, #session-id')?.textContent || 
                   null;
          });
          
          if (sessionId) {
            console.log(`ID sesji z DOM/localStorage: ${sessionId}`);
          } else {
            console.warn('Nie udało się pobrać ID sesji');
          }
        }
      } else {
        console.warn(`Nie jesteśmy na stronie gry: ${gameUrl}`);
      }
      
      // ========== KROK 3: ROZGRYWKA (3 RUNDY) ==========
      if (gameUrl.includes('/game')) {
        console.log('KROK 3: Rozpoczynanie rozgrywki (3 rundy)');
        
        // Czekaj na załadowanie strony gry
        await page.waitForSelector('body', { timeout: 10000 });
        
        // Zrzut ekranu całej strony
        await takeScreenshot(page, 'game-loaded');
        
        // Wyświetl wszystkie dostępne elementy na stronie
        const allElements = await page.evaluate(() => {
          const elements = [];
          const allTags = document.querySelectorAll('*');
          for (const el of allTags) {
            if (el.id || el.className || el.tagName === 'BUTTON' || el.tagName === 'A' || el.tagName === 'INPUT') {
              elements.push({
                tag: el.tagName,
                id: el.id,
                classes: el.className,
                text: el.textContent?.trim().substring(0, 30)
              });
            }
          }
          return elements;
        });
        
        console.log('Dostępne elementy na stronie gry:');
        for (const el of allElements.slice(0, 20)) { // Pokaż tylko pierwszych 20 elementów
          console.log(`${el.tag}${el.id ? '#'+el.id : ''}${el.classes ? '.'+el.classes.replace(' ', '.') : ''}: ${el.text}`);
        }
        
        // Przeprowadź 3 rundy
        for (let i = 0; i < 3; i++) {
          console.log(`Runda ${i+1}/3`);
          
          // Znajdź selektory kurtyn
          const curtainSelectors = [
            '#left-curtain', '#right-curtain',
            '.left-curtain', '.right-curtain',
            '[data-curtain="left"]', '[data-curtain="right"]',
            '.curtain-left', '.curtain-right'
          ];
          
          let leftCurtainEl = null;
          let rightCurtainEl = null;
          
          for (const selector of curtainSelectors) {
            const el = await page.$(selector);
            if (el) {
              if (selector.includes('left')) {
                leftCurtainEl = el;
              } else if (selector.includes('right')) {
                rightCurtainEl = el;
              }
            }
            if (leftCurtainEl && rightCurtainEl) break;
          }
          
          if (!leftCurtainEl && !rightCurtainEl) {
            // Nie znaleziono selektorów kurtyn, spróbuj znaleźć inne interaktywne elementy
            console.warn('Nie znaleziono kurtyn, szukam innych elementów klikalnych');
            
            const clickableElements = await page.$$('button, a, [role="button"], div[onclick], [class*="clickable"], [class*="selectable"]');
            if (clickableElements.length >= 2) {
              leftCurtainEl = clickableElements[0];
              rightCurtainEl = clickableElements[1];
              console.log('Znaleziono alternatywne elementy klikalne');
            } else {
              console.error('Nie znaleziono wystarczającej liczby elementów klikalnych');
              await takeScreenshot(page, `round-${i+1}-error-no-curtains`);
              break;
            }
          }
          
          // Wybierz lewą lub prawą kurtynę losowo
          const selectedCurtain = Math.random() > 0.5 ? leftCurtainEl : rightCurtainEl;
          console.log(`Wybieram ${selectedCurtain === leftCurtainEl ? 'lewą' : 'prawą'} kurtynę`);
          
          // Kliknij wybraną kurtynę
          await selectedCurtain.click();
          await waitForTimeout(2000);
          
          // Zrzut ekranu po wyborze
          await takeScreenshot(page, `round-${i+1}-after-selection`);
          
          // Poczekaj chwilę na załadowanie obrazu
          await waitForTimeout(3000);
          
          // Kliknij przycisk kontynuacji
          const continueSelectors = [
            '#continue-btn', '.continue-btn', 
            'button:contains("Kontynuuj")', 'button:contains("Dalej")',
            '[data-action="continue"]', '[class*="continue"]', '.btn-primary'
          ];
          
          let continueBtnFound = false;
          for (const selector of continueSelectors) {
            try {
              const continueBtn = await page.$(selector);
              if (continueBtn) {
                await continueBtn.click();
                continueBtnFound = true;
                console.log(`Kliknięto przycisk kontynuacji (${selector})`);
                break;
              }
            } catch (error) {
              console.log(`Nie udało się kliknąć ${selector}: ${error.message}`);
            }
          }
          
          if (!continueBtnFound) {
            // Jeśli nie znaleziono przycisku kontynuacji, spróbuj kliknąć dowolny przycisk
            const buttons = await page.$$('button, .btn, a.button, [role="button"]');
            if (buttons.length > 0) {
              await buttons[0].click();
              console.log('Kliknięto alternatywny przycisk kontynuacji');
            } else {
              console.warn('Nie znaleziono przycisku kontynuacji');
            }
          }
          
          // Poczekaj chwilę między rundami
          await waitForTimeout(3000);
        }
      }
      
      // ========== KROK 4: PRZEJŚCIE DO PODSUMOWANIA ==========
      console.log('KROK 4: Przejście do podsumowania sesji');
      
      // Jeśli mamy ID sesji, możemy przejść bezpośrednio do podsumowania
      if (sessionId) {
        await page.goto(`${API_URL}/summary?session_id=${sessionId}`);
        console.log(`Przejście do podsumowania sesji ${sessionId}`);
      } else {
        console.warn('Brak ID sesji, nie można przejść do podsumowania');
        
        // Szukaj przycisku zakończenia
        const endButtons = await page.$$('button, .btn, a');
        let endBtnClicked = false;
        
        for (const btn of endButtons) {
          const text = await page.evaluate(el => el.textContent, btn);
          if (text && (text.toLowerCase().includes('zakończ') || text.toLowerCase().includes('koniec') || text.toLowerCase().includes('podsumowanie'))) {
            console.log(`Klikam przycisk zakończenia: "${text.trim()}"`);
            await Promise.all([
              btn.click(),
              page.waitForNavigation({ timeout: 15000 }).catch(() => console.log('Brak nawigacji po kliknięciu przycisku zakończenia'))
            ]);
            endBtnClicked = true;
            break;
          }
        }
        
        if (!endBtnClicked) {
          console.warn('Nie znaleziono przycisku zakończenia, próbuję przejść do /summary');
          await page.goto(`${API_URL}/summary`);
        }
      }
      
      await takeScreenshot(page, 'summary-page');
      
      // ========== KROK 5: SPRAWDZENIE PODSUMOWANIA ==========
      console.log('KROK 5: Sprawdzanie strony podsumowania');
      
      // Sprawdź URL
      const summaryUrl = page.url();
      console.log(`URL strony podsumowania: ${summaryUrl}`);
      
      // Zrzut ekranu całej strony
      await takeScreenshot(page, 'summary-full-page');
      
      // Wyświetl wszystkie dostępne elementy na stronie
      const summaryElements = await page.evaluate(() => {
        const elements = [];
        const allTags = document.querySelectorAll('*');
        for (const el of allTags) {
          if (el.id || el.className || el.tagName === 'BUTTON' || el.tagName === 'A' || el.tagName === 'INPUT' || 
              el.tagName === 'H1' || el.tagName === 'H2' || el.tagName === 'TABLE' || el.tagName === 'IMG') {
            elements.push({
              tag: el.tagName,
              id: el.id,
              classes: el.className,
              text: el.textContent?.trim().substring(0, 50)
            });
          }
        }
        return elements;
      });
      
      console.log('Dostępne elementy na stronie podsumowania:');
      for (const el of summaryElements.slice(0, 20)) { // Pokaż tylko pierwszych 20 elementów
        console.log(`${el.tag}${el.id ? '#'+el.id : ''}${el.classes ? '.'+el.classes.replace(' ', '.') : ''}: ${el.text}`);
      }
      
      // Sprawdź czy są obrazy na stronie
      const images = await page.evaluate(() => {
        const imgs = document.querySelectorAll('img');
        return Array.from(imgs).map(img => ({
          src: img.src,
          width: img.width,
          height: img.height,
          alt: img.alt,
          complete: img.complete,
          naturalWidth: img.naturalWidth
        }));
      });
      
      console.log(`Liczba obrazów na stronie: ${images.length}`);
      console.log('Statystyki obrazów:');
      images.slice(0, 5).forEach((img, i) => {
        console.log(`Obraz ${i+1}: ${img.src.substring(0, 50)}... (${img.width}x${img.height}, załadowany: ${img.complete && img.naturalWidth > 0})`);
      });
      
      // Pobierz dane statystyczne
      const stats = await page.evaluate(() => {
        // Szukaj elementów które mogą zawierać statystyki
        const statsElements = document.querySelectorAll('[class*="stat"], [id*="stat"], .summary-data, .session-data, table, tbody tr');
        const stats = [];
        
        for (const el of statsElements) {
          stats.push({
            text: el.textContent.trim(),
            html: el.innerHTML
          });
        }
        
        return stats;
      });
      
      console.log('Statystyki sesji:');
      stats.forEach((stat, i) => {
        if (i < 10) { // Ogranicz liczbę statystyk w logach
          console.log(`Statystyka ${i+1}: ${stat.text.substring(0, 100)}`);
        }
      });
      
      console.log('Test zakończony pomyślnie');
    } catch (error) {
      // Zapisz zrzut ekranu w przypadku błędu
      if (page) {
        await takeScreenshot(page, 'error-state');
      }
      
      console.error('Błąd podczas testu:', error);
      throw error;
    } finally {
      if (page) {
        await page.close();
      }
    }
  }, 120000); // 2 minuty na wykonanie testu
}); 