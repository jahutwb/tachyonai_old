/**
 * Test E2E dla procesu rozgrywki w aplikacji tachyonai
 */

const puppeteer = require('puppeteer');
const axios = require('axios');

// Globalne zmienne pomocnicze
let browser;
let page;
let authToken;
let sessionId;

// Konfiguracja testów
const API_URL = 'http://localhost:8000';
const TEST_USER = {
  username: 'testuser_3804',
  password: 'password123'
};

// Helper do czekania
const waitForTimeout = (ms) => new Promise(resolve => setTimeout(resolve, ms));

describe('Testy rozgrywki i aktualizacji bazy danych', () => {
  beforeAll(async () => {
    // Pobierz token uwierzytelniający przez API
    try {
      const loginResponse = await axios.post(`${API_URL}/token`, 
        `username=${TEST_USER.username}&password=${TEST_USER.password}`,
        {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        }
      );
      
      authToken = loginResponse.data.access_token;
      console.log('Uwierzytelnienie zakończone sukcesem, otrzymano token');
      
      // Utwórz nową sesję przez API
      const sessionResponse = await axios.post(`${API_URL}/api/sessions`, {}, {
        headers: { 
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });
      
      sessionId = sessionResponse.data.id;
      console.log(`Utworzono nową sesję, ID: ${sessionId}`);
      
      // Uruchom przeglądarkę
      browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      });
      
    } catch (error) {
      console.error('Błąd podczas przygotowania testu:', error.message);
      throw error;
    }
  });

  afterAll(async () => {
    await browser.close();
  });

  beforeEach(async () => {
    page = await browser.newPage();
    
    // Dodanie tokena autoryzacyjnego do lokalnego storage przeglądarki
    await page.evaluateOnNewDocument((token) => {
      localStorage.setItem('token', token);
    }, authToken);
    
    // Włącz rejestrowanie logów konsoli
    page.on('console', message => console.log(`[BROWSER LOG]: ${message.text()}`));
    // Ustawienie timeoutu dla operacji nawigacji
    page.setDefaultNavigationTimeout(10000);
  });

  afterEach(async () => {
    await page.close();
  });

  test('Rozgrywka powinna aktualizować liczniki obrazów i pule sesji po każdej rundzie', async () => {
    try {
      // KROK 1: Przejdź bezpośrednio do strony gry z gotową sesją
      console.log('Przechodzę do strony gry z istniejącą sesją');
      await page.goto(`${API_URL}/game?session_id=${sessionId}`);
      
      // KROK 2: Przeprowadzenie kilku rund gry i weryfikacja aktualizacji liczników
      console.log('Rozpoczynam rozgrywkę...');
      
      // Czekaj na pełne załadowanie strony gry
      await page.waitForSelector('.game-container', { timeout: 5000 });
      
      // Przeprowadź 3 rundy
      for (let i = 0; i < 3; i++) {
        console.log(`Rozpoczynam rundę ${i+1}`);
        
        // Poczekaj na załadowanie fazy wyboru
        await page.waitForSelector('.curtain-container', { visible: true, timeout: 5000 });
        
        // Kliknij w lewą kurtynę
        console.log('Klikam lewą kurtynę');
        await page.click('#left-curtain');
        
        // Poczekaj na fazę wyniku (bodźca)
        await page.waitForSelector('#stimulus-image', { visible: true, timeout: 5000 });
        
        // Sprawdź, czy obraz bodźca został załadowany
        const stimulusVisible = await page.evaluate(() => {
          const img = document.querySelector('#stimulus-image');
          return img && img.complete && img.naturalWidth > 0;
        });
        
        console.log(`Obraz bodźca widoczny: ${stimulusVisible}`);
        expect(stimulusVisible).toBe(true);
        
        // Sprawdź wynik rundy (SUCCESS lub FAILURE)
        const roundResult = await page.evaluate(() => {
          const resultElement = document.querySelector('#result-text');
          return resultElement ? resultElement.textContent : null;
        });
        
        console.log(`Wynik rundy: ${roundResult}`);
        
        // Poczekaj na przycisk kontynuacji i kliknij go
        await page.waitForSelector('#continue-btn', { timeout: 5000 });
        await page.click('#continue-btn');
        
        // Poczekaj chwilę, aby dane zostały zaktualizowane w bazie
        await waitForTimeout(1000);
      }
      
      // KROK 3: Weryfikacja sesji z API
      console.log('Pobieranie aktualnych danych sesji z API...');
      const sessionResponse = await axios.get(`${API_URL}/api/sessions/${sessionId}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      
      const sessionData = sessionResponse.data;
      console.log('Dane sesji:', {
        id: sessionData.id,
        status: sessionData.status,
        remaining_pairs: sessionData.remaining_pairs,
        session_profit_factor: sessionData.session_profit_factor
      });
      
      // Sprawdź, czy dane sesji są poprawne
      expect(sessionData.id).toBe(sessionId);
      expect(['ACTIVE', 'COMPLETED']).toContain(sessionData.status);
      expect(sessionData.session_profit_factor).not.toBe(1.0); // Powinien się zmienić po rundach
      
      // KROK 4: Kontynuuj grę aż do zakończenia sesji
      console.log('Kontynuuję grę do zakończenia sesji...');
      
      // Tworzymy osobną instancję strony, aby zrestartować stan
      const gamePage = await browser.newPage();
      // Dodanie tokena autoryzacyjnego do lokalnego storage
      await gamePage.evaluateOnNewDocument((token) => {
        localStorage.setItem('token', token);
      }, authToken);
      
      await gamePage.goto(`${API_URL}/game?session_id=${sessionId}`);
      await gamePage.waitForSelector('.game-container', { timeout: 5000 });
      
      // Kontynuuj grę dopóki sesja nie zostanie zakończona
      let isGameOver = false;
      let attempts = 0;
      const maxAttempts = 10; // Zabezpieczenie przed nieskończoną pętlą
      
      while (!isGameOver && attempts < maxAttempts) {
        attempts++;
        
        try {
          // Sprawdź, czy jesteśmy w fazie wyboru
          const selectPhaseVisible = await gamePage.evaluate(() => {
            const curtainContainer = document.querySelector('.curtain-container');
            return curtainContainer && window.getComputedStyle(curtainContainer).display !== 'none';
          });
          
          if (selectPhaseVisible) {
            console.log(`Próba ${attempts}: Kontynuacja gry - wybór kurtyny`);
            await gamePage.click('#right-curtain');
            
            // Poczekaj na fazę wyniku
            await gamePage.waitForSelector('#stimulus-image', { visible: true, timeout: 5000 });
            
            // Sprawdź pozostałe pary
            const remainingPairs = await gamePage.evaluate(() => {
              const element = document.querySelector('#remaining-pairs');
              return element ? parseInt(element.textContent, 10) : 0;
            });
            
            console.log(`Pozostałe pary: ${remainingPairs}`);
            
            // Kliknij przycisk kontynuacji
            await gamePage.waitForSelector('#continue-btn', { timeout: 5000 });
            await gamePage.click('#continue-btn');
            
            // Jeśli nie ma już par, gra powinna się zakończyć
            if (remainingPairs <= 1) {
              console.log('Ostatnia para, oczekiwanie na zakończenie sesji');
            }
            
            // Poczekaj na aktualizację danych
            await waitForTimeout(1000);
          } else {
            // Sprawdź czy jesteśmy na stronie podsumowania
            const currentUrl = await gamePage.url();
            isGameOver = currentUrl.includes('/summary');
            
            if (isGameOver) {
              console.log('Gra zakończona - jesteśmy na stronie podsumowania');
              break;
            } else {
              console.log('Nie jesteśmy ani w fazie wyboru, ani na podsumowaniu - oczekiwanie');
              await waitForTimeout(1000);
            }
          }
        } catch (error) {
          console.error(`Błąd w próbie ${attempts}:`, error);
          break;
        }
      }
      
      // KROK 5: Weryfikacja podsumowania sesji z API
      console.log('Pobieranie podsumowania sesji z API...');
      const summaryResponse = await axios.get(`${API_URL}/api/sessions/${sessionId}/summary`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      
      const summaryData = summaryResponse.data;
      console.log('Podsumowanie sesji:', {
        id: summaryData.id,
        status: summaryData.status,
        round_count: summaryData.round_count,
        success_count: summaryData.success_count,
        failure_count: summaryData.failure_count,
        session_profit_factor: summaryData.session_profit_factor,
        pos_ranking_length: summaryData.pos_ranking ? summaryData.pos_ranking.length : 0,
        neg_ranking_length: summaryData.neg_ranking ? summaryData.neg_ranking.length : 0
      });
      
      // Sprawdź, czy podsumowanie sesji zawiera prawidłowe dane
      expect(summaryData.id).toBe(sessionId);
      expect(summaryData.round_count).toBeGreaterThan(0);
      expect(summaryData.round_count).toBe(summaryData.success_count + summaryData.failure_count);
      
      // Zamknij stronę gry
      await gamePage.close();
      
      // Test zakończony pomyślnie
      console.log('Test zakończony - wszystkie weryfikacje przeszły pomyślnie');
    } catch (error) {
      console.error('Błąd podczas testu:', error);
      throw error;
    }
  }, 60000); // Timeout 60 sekund
}); 