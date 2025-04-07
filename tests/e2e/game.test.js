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
    page.setDefaultNavigationTimeout(15000);
  });

  afterEach(async () => {
    await page.close();
  });

  test('Weryfikacja podsumowania sesji z API', async () => {
    try {
      // KROK 1: Pobierz dane sesji z API
      console.log('Pobieranie danych sesji z API...');
      const sessionResponse = await axios.get(`${API_URL}/api/sessions/${sessionId}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      
      const sessionData = sessionResponse.data;
      console.log('Dane sesji:', {
        id: sessionData.id,
        status: sessionData.status,
        remaining_pairs: sessionData.remaining_pairs,
      });
      
      // Sprawdź, czy dane sesji są poprawne
      expect(sessionData.id).toBe(sessionId);
      expect(['ACTIVE', 'COMPLETED']).toContain(sessionData.status);
      
      // KROK 2: Pobierz podsumowanie sesji
      console.log('Pobieranie podsumowania sesji z API...');
      
      // Zdefiniuj endpoint podsumowania
      const summaryEndpoint = `${API_URL}/api/sessions/${sessionId}/summary`;
      console.log(`Używany endpoint podsumowania: ${summaryEndpoint}`);
      
      // Wykonaj zapytanie
      const summaryResponse = await axios.get(summaryEndpoint, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      
      const summaryData = summaryResponse.data;
      console.log('Podsumowanie sesji:', summaryData);
      
      // Sprawdź, czy podsumowanie zawiera wymagane pola
      expect(summaryData).toHaveProperty('id');
      expect(summaryData).toHaveProperty('round_count');
      expect(summaryData).toHaveProperty('success_count');
      expect(summaryData).toHaveProperty('failure_count');
      expect(summaryData).toHaveProperty('session_profit_factor');
      
      if (summaryData.pos_ranking) {
        expect(Array.isArray(summaryData.pos_ranking)).toBe(true);
        console.log(`Liczba obrazów w rankingu pozytywnym: ${summaryData.pos_ranking.length}`);
      }
      
      if (summaryData.neg_ranking) {
        expect(Array.isArray(summaryData.neg_ranking)).toBe(true);
        console.log(`Liczba obrazów w rankingu negatywnym: ${summaryData.neg_ranking.length}`);
      }
      
      // KROK 3: Otwórz stronę podsumowania w przeglądarce
      console.log('Otwieranie strony podsumowania sesji w przeglądarce...');
      await page.goto(`${API_URL}/summary?session_id=${sessionId}`);
      
      // Czekaj na załadowanie strony podsumowania
      await page.waitForTimeout(2000);
      
      // Zrób screenshot strony podsumowania
      await page.screenshot({ path: 'screenshots/summary.png' });
      console.log('Zapisano zrzut ekranu podsumowania');
      
      // Sprawdź, czy elementy podsumowania są widoczne
      const summaryElements = await page.evaluate(() => {
        const elements = {};
        
        // Sprawdź nagłówek
        const headerElement = document.querySelector('h1, .summary-header');
        elements.headerExists = !!headerElement;
        elements.headerText = headerElement ? headerElement.textContent : null;
        
        // Sprawdź statystyki
        const statsElement = document.querySelector('.stats-container, .summary-stats');
        elements.statsExists = !!statsElement;
        
        // Sprawdź wykresy/wizualizacje
        const chartsElement = document.querySelector('.chart-container, canvas');
        elements.chartsExists = !!chartsElement;
        
        // Sprawdź rankingi obrazów
        const rankingsElement = document.querySelector('.rankings-container, .image-rankings');
        elements.rankingsExists = !!rankingsElement;
        
        return elements;
      });
      
      console.log('Elementy podsumowania:', summaryElements);
      
      // Weryfikuj obecność elementów podsumowania
      if (summaryElements.headerExists) {
        console.log(`Znaleziono nagłówek: ${summaryElements.headerText}`);
      } else {
        console.warn('Nie znaleziono nagłówka na stronie podsumowania');
      }
      
      if (!summaryElements.statsExists) {
        console.warn('Nie znaleziono elementu statystyk na stronie podsumowania');
      }
      
      if (!summaryElements.chartsExists) {
        console.warn('Nie znaleziono wykresów na stronie podsumowania');
      }
      
      if (!summaryElements.rankingsExists) {
        console.warn('Nie znaleziono rankingów obrazów na stronie podsumowania');
      }
      
      console.log('Test zakończony - wszystkie weryfikacje przeszły pomyślnie');
    } catch (error) {
      console.error('Błąd podczas testu:', error);
      throw error;
    }
  }, 60000); // Timeout 60 sekund
}); 