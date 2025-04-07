/**
 * Test E2E dla procesów uwierzytelniania w aplikacji tachyonai
 */

const puppeteer = require('puppeteer');

describe('Testy uwierzytelniania', () => {
  const testUsername = `testuser_${Math.floor(Math.random() * 10000)}`;
  const testPassword = 'password123';

  beforeAll(async () => {
    // Upewnij się, że strona jest gotowa
    await page.goto('http://localhost:8000/');
    await page.waitForSelector('body');
  });

  describe('Rejestracja', () => {
    it('powinna pozwolić użytkownikowi na rejestrację', async () => {
      await page.goto('http://localhost:8000/signup');
      await page.waitForSelector('#username');
      
      await page.type('#username', testUsername);
      await page.type('#password', testPassword);
      
      await Promise.all([
        page.click('button[type="submit"]'),
        page.waitForNavigation()
      ]);
      
      // Sprawdź, czy rejestracja przebiegła pomyślnie i użytkownik został przekierowany
      const url = page.url();
      expect(url).toContain('http://localhost:8000/game');
    });
    
    it('powinna pokazać błąd, gdy nazwa użytkownika jest już zajęta', async () => {
      await page.goto('http://localhost:8000/signup');
      await page.waitForSelector('#username');
      
      await page.type('#username', testUsername); // Użyj tej samej nazwy użytkownika
      await page.type('#password', testPassword);
      
      await page.click('button[type="submit"]');
      
      // Sprawdź, czy pojawił się komunikat o błędzie
      await page.waitForSelector('.error-message');
      const errorText = await page.$eval('.error-message', el => el.textContent);
      expect(errorText).toContain('już istnieje');
    });
  });
  
  describe('Logowanie', () => {
    it('powinno pozwolić użytkownikowi na zalogowanie się', async () => {
      await page.goto('http://localhost:8000/login');
      await page.waitForSelector('#username');
      
      await page.type('#username', testUsername);
      await page.type('#password', testPassword);
      
      await Promise.all([
        page.click('button[type="submit"]'),
        page.waitForNavigation()
      ]);
      
      // Sprawdź, czy logowanie przebiegło pomyślnie i użytkownik został przekierowany
      const url = page.url();
      expect(url).toContain('http://localhost:8000/game');
    });
    
    it('powinno pokazać błąd przy nieprawidłowych danych logowania', async () => {
      await page.goto('http://localhost:8000/login');
      await page.waitForSelector('#username');
      
      await page.type('#username', testUsername);
      await page.type('#password', 'nieprawidłowe_hasło');
      
      await page.click('button[type="submit"]');
      
      // Sprawdź, czy pojawił się komunikat o błędzie
      await page.waitForSelector('.error-message');
      const errorText = await page.$eval('.error-message', el => el.textContent);
      expect(errorText).toContain('Nieprawidłowe dane logowania');
    });
  });
  
  describe('Wylogowanie', () => {
    it('powinno pozwolić użytkownikowi na wylogowanie się', async () => {
      // Najpierw zaloguj użytkownika
      await login(page, testUsername, testPassword);
      
      // Kliknij przycisk wylogowania
      await page.click('#logout-button');
      
      // Sprawdź, czy użytkownik został przekierowany na stronę logowania
      await page.waitForNavigation();
      const url = page.url();
      expect(url).toContain('http://localhost:8000/login');
      
      // Sprawdź, czy token został usunięty (sprawdzając, czy przekierowanie na stronę gry jest zablokowane)
      await page.goto('http://localhost:8000/game');
      await page.waitForNavigation();
      const newUrl = page.url();
      expect(newUrl).toContain('http://localhost:8000/login');
    });
  });
}); 