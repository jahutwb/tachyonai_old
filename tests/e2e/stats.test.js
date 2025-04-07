/**
 * Test E2E dla podsumowania sesji i statystyk w aplikacji tachyonai
 */

const puppeteer = require('puppeteer');

describe('Testy podsumowania i statystyk', () => {
  const testUsername = `testuser_${Math.floor(Math.random() * 10000)}`;
  const testPassword = 'password123';
  
  beforeAll(async () => {
    // Zarejestruj nowego użytkownika i zaloguj się
    await page.goto('http://localhost:8000/signup');
    await page.waitForSelector('#username');
    await page.type('#username', testUsername);
    await page.type('#password', testPassword);
    
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForNavigation()
    ]);
    
    // Utwórz sesję testową z zakończonymi rundami (przez API lub interfejs)
    await page.goto('http://localhost:8000/game');
    await page.waitForSelector('#new-session-button');
    await page.click('#new-session-button');
    
    // Wykonaj szybkie przejście przez jedną rundę do podsumowania
    // (Możemy użyć skryptu bezpośrednio na stronie, aby przyspieszyć testy)
    await page.evaluate(() => {
      // Symulacja zakończenia sesji dla testu - w rzeczywistym teście
      // można to zrobić przez API lub symulację kliknięć
      localStorage.setItem('testMode', 'true');
      localStorage.setItem('completedSession', 'true');
    });
    
    // Przejdź do strony podsumowania
    await page.goto('http://localhost:8000/summary');
    await page.waitForSelector('.session-summary');
  });
  
  describe('Podsumowanie sesji', () => {
    it('powinno wyświetlać podstawowe statystyki sesji', async () => {
      await page.goto('http://localhost:8000/summary');
      await page.waitForSelector('.session-summary');
      
      // Sprawdź, czy wyświetlane są sukcesy i porażki
      const successCount = await page.$('.success-count');
      expect(successCount).not.toBeNull();
      
      const failureCount = await page.$('.failure-count');
      expect(failureCount).not.toBeNull();
      
      // Sprawdź, czy wyświetlany jest końcowy zysk
      const finalProfit = await page.$('.final-profit');
      expect(finalProfit).not.toBeNull();
    });
    
    it('powinno wyświetlać wykres zmian majątku', async () => {
      await page.goto('http://localhost:8000/summary');
      await page.waitForSelector('.wealth-chart');
      
      const chart = await page.$('.wealth-chart');
      expect(chart).not.toBeNull();
      
      // Sprawdź, czy wykres zawiera elementy graficzne
      const chartElements = await page.$$('.wealth-chart svg');
      expect(chartElements.length).toBeGreaterThan(0);
    });
    
    it('powinno wyświetlać ranking obrazów', async () => {
      await page.goto('http://localhost:8000/summary');
      await page.waitForSelector('.image-ranking');
      
      const imageRanking = await page.$('.image-ranking');
      expect(imageRanking).not.toBeNull();
      
      // Sprawdź, czy lista rankingowa zawiera obrazy
      const rankingItems = await page.$$('.image-ranking .ranking-item');
      expect(rankingItems.length).toBeGreaterThan(0);
      
      // Sprawdź, czy obrazy mają wyświetlone statystyki sukcesu
      const successRate = await page.$('.ranking-item .success-rate');
      expect(successRate).not.toBeNull();
    });
    
    it('powinno umożliwiać rozpoczęcie nowej sesji', async () => {
      await page.goto('http://localhost:8000/summary');
      await page.waitForSelector('#new-session-button');
      
      await Promise.all([
        page.click('#new-session-button'),
        page.waitForNavigation()
      ]);
      
      // Sprawdź, czy przekierowano do ekranu gry
      const url = page.url();
      expect(url).toContain('http://localhost:8000/game');
      
      // Sprawdź, czy nowa sesja została utworzona
      await page.waitForSelector('.curtain-container');
    });
  });
  
  describe('Statystyki globalne', () => {
    it('powinno wyświetlać historię sesji', async () => {
      await page.goto('http://localhost:8000/stats');
      await page.waitForSelector('.session-history');
      
      const sessionHistory = await page.$('.session-history');
      expect(sessionHistory).not.toBeNull();
      
      // Sprawdź, czy lista sesji zawiera przynajmniej jedną sesję
      const sessionItems = await page.$$('.session-history .session-item');
      expect(sessionItems.length).toBeGreaterThan(0);
    });
    
    it('powinno wyświetlać globalne statystyki użytkownika', async () => {
      await page.goto('http://localhost:8000/stats');
      await page.waitForSelector('.global-stats');
      
      const globalStats = await page.$('.global-stats');
      expect(globalStats).not.toBeNull();
      
      // Sprawdź, czy wyświetlane są całkowite statystyki
      const totalSuccess = await page.$('.global-stats .total-success');
      expect(totalSuccess).not.toBeNull();
      
      const totalProfit = await page.$('.global-stats .total-profit');
      expect(totalProfit).not.toBeNull();
      
      const averageProfit = await page.$('.global-stats .average-profit');
      expect(averageProfit).not.toBeNull();
    });
    
    it('powinno umożliwiać przejście do szczegółów wcześniejszej sesji', async () => {
      await page.goto('http://localhost:8000/stats');
      await page.waitForSelector('.session-history .session-item');
      
      // Kliknij pierwszą sesję na liście historii
      await Promise.all([
        page.click('.session-history .session-item:first-child'),
        page.waitForNavigation()
      ]);
      
      // Sprawdź, czy przekierowano do podsumowania sesji
      const url = page.url();
      expect(url).toContain('http://localhost:8000/summary');
      
      // Sprawdź, czy wyświetlane są szczegóły sesji
      await page.waitForSelector('.session-summary');
    });
  });
}); 