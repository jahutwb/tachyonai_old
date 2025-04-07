/**
 * Test E2E dla procesu rozgrywki w aplikacji tachyonai
 */

const puppeteer = require('puppeteer');

describe('Testy rozgrywki', () => {
  const testUsername = `testuser_${Math.floor(Math.random() * 10000)}`;
  const testPassword = 'password123';
  
  beforeAll(async () => {
    // Zarejestruj nowego użytkownika
    await page.goto('http://localhost:8000/signup');
    await page.waitForSelector('#username');
    await page.type('#username', testUsername);
    await page.type('#password', testPassword);
    
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForNavigation()
    ]);
  });
  
  beforeEach(async () => {
    // Upewnij się, że użytkownik jest zalogowany przed każdym testem
    if (!page.url().includes('game')) {
      await login(page, testUsername, testPassword);
    }
  });
  
  describe('Tworzenie nowej sesji', () => {
    it('powinno utworzyć nową sesję po kliknięciu przycisku', async () => {
      await page.goto('http://localhost:8000/game');
      await page.waitForSelector('#new-session-button');
      
      await Promise.all([
        page.click('#new-session-button'),
        page.waitForResponse(response => response.url().includes('/api/sessions') && response.status() === 200)
      ]);
      
      // Sprawdź, czy ekran rozgrywki się wyświetla
      await page.waitForSelector('.curtain-container');
      const curtains = await page.$$('.curtain');
      expect(curtains.length).toBe(2);
      
      // Sprawdź, czy pasek statystyk jest widoczny
      await page.waitForSelector('.stats-bar');
      const statsBar = await page.$('.stats-bar');
      expect(statsBar).not.toBeNull();
    });
  });
  
  describe('Interakcja z kurtynami', () => {
    it('powinna pokazać obraz po kliknięciu kurtyny', async () => {
      await page.goto('http://localhost:8000/game');
      await page.waitForSelector('.curtain');
      
      // Kliknij lewą kurtynę
      const leftCurtain = await page.$('.curtain:nth-child(1)');
      await leftCurtain.click();
      
      // Sprawdź, czy kurtyna się otwiera (animacja)
      await page.waitForSelector('.curtain.open');
      
      // Sprawdź, czy obraz się pokazał
      await page.waitForSelector('.curtain.open img');
      const image = await page.$('.curtain.open img');
      expect(image).not.toBeNull();
      
      // Sprawdź, czy pojawił się wskaźnik oczekiwania na zmianę ceny
      await page.waitForSelector('.price-change-indicator');
    });
    
    it('powinna zakończyć rundę po zmianie ceny i przejść do następnej', async () => {
      await page.goto('http://localhost:8000/game');
      await page.waitForSelector('.curtain');
      
      // Kliknij lewą kurtynę
      const leftCurtain = await page.$('.curtain:nth-child(1)');
      await leftCurtain.click();
      
      // Poczekaj na otwarcie kurtyny
      await page.waitForSelector('.curtain.open');
      
      // Poczekaj na zakończenie rundy (symulacja zmiany ceny i pokazanie wyniku)
      await page.waitForSelector('.round-result', { timeout: 15000 });
      
      // Sprawdź, czy wynik rundy jest widoczny
      const roundResult = await page.$('.round-result');
      expect(roundResult).not.toBeNull();
      
      // Kliknij przycisk "Następna runda"
      await page.waitForSelector('#next-round-button');
      await page.click('#next-round-button');
      
      // Sprawdź, czy nowa runda się załadowała
      await page.waitForSelector('.curtain:not(.open)');
      
      // Sprawdź, czy pasek statystyk został zaktualizowany
      await page.waitForSelector('.stats-bar');
      const roundsPlayed = await page.$eval('.stats-bar .rounds-played', el => el.textContent);
      expect(parseInt(roundsPlayed)).toBeGreaterThan(0);
    });
  });
  
  describe('Zakończenie sesji', () => {
    it('powinna pokazać podsumowanie po zakończeniu wszystkich rund', async () => {
      // Ten test symuluje przejście przez wszystkie rundy w sesji
      // Uwaga: W rzeczywistym teście możemy chcieć zmodyfikować backend, aby dla testów używał mniejszej liczby rund
      
      await page.goto('http://localhost:8000/game');
      await page.waitForSelector('.curtain');
      
      // Utwórz nową sesję z tylko jedną rundą (w celach testowych)
      await page.evaluate(() => {
        // Można użyć LocalStorage do zapisania flagi dla testów
        localStorage.setItem('testMode', 'true');
      });
      
      await page.reload();
      await page.waitForSelector('.curtain');
      
      // Kliknij kurtynę i zakończ rundę
      const curtain = await page.$('.curtain');
      await curtain.click();
      
      // Poczekaj na zakończenie rundy
      await page.waitForSelector('.round-result', { timeout: 15000 });
      
      // Kliknij przycisk "Następna runda"
      await page.waitForSelector('#next-round-button');
      await page.click('#next-round-button');
      
      // Poczekaj na podsumowanie sesji
      await page.waitForSelector('.session-summary', { timeout: 10000 });
      
      // Sprawdź, czy podsumowanie zawiera wymagane elementy
      const summaryElements = await page.$$('.session-summary .summary-item');
      expect(summaryElements.length).toBeGreaterThan(0);
      
      // Sprawdź, czy wykres jest widoczny
      const chart = await page.$('.wealth-chart');
      expect(chart).not.toBeNull();
      
      // Sprawdź, czy ranking obrazów jest widoczny
      const imageRanking = await page.$('.image-ranking');
      expect(imageRanking).not.toBeNull();
    });
  });
}); 