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
      await page.goto('http://localhost:8000/');
      await page.waitForSelector('#register-button');
      
      // Kliknij przycisk rejestracji, aby otworzyć modal
      await page.click('#register-button');
      await page.waitForSelector('#register-modal', { visible: true });
      
      // Wypełnij formularz rejestracji
      await page.type('#register-username', testUsername);
      await page.type('#register-password', testPassword);
      await page.type('#register-confirm-password', testPassword);
      
      // Kliknij przycisk submit i poczekaj na przeładowanie
      await Promise.all([
        page.click('#register-form button[type="submit"]'),
        page.waitForNavigation({ timeout: 5000 }).catch(() => {})
      ]);
      
      // Sprawdź, czy użytkownik jest zalogowany
      await page.waitForSelector('#username-display', { timeout: 5000 });
      const userDisplay = await page.$eval('#username-display', el => el.textContent);
      expect(userDisplay).toContain(testUsername);
    }, 60000);
    
    it('powinna pokazać błąd, gdy nazwa użytkownika jest już zajęta', async () => {
      await page.goto('http://localhost:8000/');
      await page.waitForSelector('#register-button');
      
      // Kliknij przycisk rejestracji, aby otworzyć modal
      await page.click('#register-button');
      await page.waitForSelector('#register-modal', { visible: true });
      
      // Wypełnij formularz rejestracji tym samym użytkownikiem
      await page.type('#register-username', testUsername);
      await page.type('#register-password', testPassword);
      await page.type('#register-confirm-password', testPassword);
      
      // Kliknij przycisk submit
      await page.click('#register-form button[type="submit"]');
      
      // Poczekaj na komunikat o błędzie
      await page.waitForFunction(
        () => document.querySelector('.error-message') !== null || document.querySelector('.alert-error') !== null,
        { timeout: 5000 }
      );
      
      // Sprawdź, czy pojawił się komunikat o błędzie (może być różnie stylowany)
      const errorElement = await page.$('.error-message') || await page.$('.alert-error');
      expect(errorElement).not.toBeNull();
    }, 60000);
  });
  
  describe('Logowanie', () => {
    it('powinno pozwolić użytkownikowi na zalogowanie się', async () => {
      // Wyloguj się, jeśli jesteś zalogowany
      const logoutButton = await page.$('#logout-button');
      if (logoutButton) {
        await page.click('#logout-button');
        await page.waitForSelector('#login-button');
      }
      
      await page.goto('http://localhost:8000/');
      await page.waitForSelector('#login-button');
      
      // Kliknij przycisk logowania, aby otworzyć modal
      await page.click('#login-button');
      await page.waitForSelector('#login-modal', { visible: true });
      
      // Wypełnij formularz logowania
      await page.type('#login-username', testUsername);
      await page.type('#login-password', testPassword);
      
      // Kliknij przycisk submit i poczekaj na zalogowanie
      await Promise.all([
        page.click('#login-form button[type="submit"]'),
        page.waitForNavigation({ timeout: 5000 }).catch(() => {})
      ]);
      
      // Sprawdź, czy użytkownik jest zalogowany
      await page.waitForSelector('#username-display', { timeout: 5000 });
      const userDisplay = await page.$eval('#username-display', el => el.textContent);
      expect(userDisplay).toContain(testUsername);
    }, 60000);
    
    it('powinno pokazać błąd przy nieprawidłowych danych logowania', async () => {
      // Wyloguj się, jeśli jesteś zalogowany
      const logoutButton = await page.$('#logout-button');
      if (logoutButton) {
        await page.click('#logout-button');
        await page.waitForSelector('#login-button');
      }
      
      await page.goto('http://localhost:8000/');
      await page.waitForSelector('#login-button');
      
      // Kliknij przycisk logowania, aby otworzyć modal
      await page.click('#login-button');
      await page.waitForSelector('#login-modal', { visible: true });
      
      // Wypełnij formularz logowania z nieprawidłowym hasłem
      await page.type('#login-username', testUsername);
      await page.type('#login-password', 'nieprawidłowe_hasło');
      
      // Kliknij przycisk submit
      await page.click('#login-form button[type="submit"]');
      
      // Poczekaj na komunikat o błędzie
      await page.waitForFunction(
        () => document.querySelector('.error-message') !== null || document.querySelector('.alert-error') !== null,
        { timeout: 5000 }
      );
      
      // Sprawdź, czy pojawił się komunikat o błędzie (może być różnie stylowany)
      const errorElement = await page.$('.error-message') || await page.$('.alert-error');
      expect(errorElement).not.toBeNull();
    }, 60000);
  });
  
  describe('Wylogowanie', () => {
    it('powinno pozwolić użytkownikowi na wylogowanie się', async () => {
      // Zaloguj się
      await page.goto('http://localhost:8000/');
      await page.waitForSelector('#login-button');
      
      // Kliknij przycisk logowania, aby otworzyć modal
      await page.click('#login-button');
      await page.waitForSelector('#login-modal', { visible: true });
      
      // Wypełnij formularz logowania
      await page.type('#login-username', testUsername);
      await page.type('#login-password', testPassword);
      
      // Kliknij przycisk submit i poczekaj na zalogowanie
      await Promise.all([
        page.click('#login-form button[type="submit"]'),
        page.waitForNavigation({ timeout: 5000 }).catch(() => {})
      ]);
      
      // Poczekaj na przycisk wylogowania
      await page.waitForSelector('#logout-button', { visible: true, timeout: 5000 });
      
      // Kliknij przycisk wylogowania
      await page.click('#logout-button');
      
      // Sprawdź, czy użytkownik jest wylogowany
      await page.waitForSelector('#login-button', { timeout: 5000 });
      const loginButton = await page.$('#login-button');
      expect(loginButton).not.toBeNull();
    }, 60000);
  });
}); 