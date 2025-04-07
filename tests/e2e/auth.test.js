/**
 * Test E2E dla procesów uwierzytelniania w aplikacji tachyonai
 */

const puppeteer = require('puppeteer');

describe('Testy uwierzytelniania', () => {
  const testUsername = `testuser_${Math.floor(Math.random() * 10000)}`;
  const testPassword = 'password123';
  
  // Funkcja pomocnicza do debugowania
  const debug = async (page, message) => {
    console.log(`DEBUG: ${message}`);
    // Zrzut ekranu dla debugowania (tylko podczas testów)
    await page.screenshot({ path: `debug-${Date.now()}.png` });
    // Zrzut HTML dla debugowania
    const html = await page.content();
    console.log(`Current HTML: ${html.substring(0, 500)}...`);
  };

  beforeAll(async () => {
    // Upewnij się, że strona jest gotowa
    await page.goto('http://localhost:8000/');
    await page.waitForSelector('body');
    await debug(page, 'Strona główna załadowana');
  });

  describe('Rejestracja', () => {
    it('powinna pozwolić użytkownikowi na rejestrację', async () => {
      await page.goto('http://localhost:8000/');
      await page.waitForSelector('#register-button');
      await debug(page, 'Przycisk rejestracji widoczny');
      
      // Kliknij przycisk rejestracji, aby otworzyć modal
      await page.click('#register-button');
      await page.waitForSelector('#register-modal', { visible: true });
      await debug(page, 'Modal rejestracji otwarty');
      
      // Wypełnij formularz rejestracji
      await page.type('#register-username', testUsername);
      await page.type('#register-password', testPassword);
      await page.type('#register-confirm-password', testPassword);
      await debug(page, 'Formularz rejestracji wypełniony');
      
      // Kliknij przycisk submit i poczekaj na przeładowanie
      await Promise.all([
        page.click('#register-form button[type="submit"]'),
        // Możliwe, że strona nie przechodzi do innej strony, więc unikamy błędu timeout
        page.waitForNavigation({ timeout: 10000 }).catch(err => console.log('Nawigacja nie nastąpiła, co jest OK'))
      ]);
      
      await debug(page, 'Formularz rejestracji wysłany');
      
      // Sprawdź, czy użytkownik jest zalogowany - dodajemy dłuższy timeout
      try {
        await page.waitForSelector('#username-display', { timeout: 15000 });
        const userDisplay = await page.$eval('#username-display', el => el.textContent);
        expect(userDisplay).toContain(testUsername);
        await debug(page, 'Użytkownik zalogowany');
      } catch (error) {
        await debug(page, `Błąd: ${error.message}`);
        // W przypadku niepowodzenia sprawdź, czy jest jakiś błąd
        const errorElement = await page.$('.error-message') || await page.$('.alert-error');
        if (errorElement) {
          const errorText = await page.$eval('.error-message, .alert-error', el => el.textContent);
          console.log(`Błąd rejestracji: ${errorText}`);
        }
        throw error;
      }
    }, 120000);
    
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
      try {
        await page.waitForFunction(
          () => document.querySelector('.error-message') !== null || document.querySelector('.alert-error') !== null,
          { timeout: 10000 }
        );
        
        // Sprawdź, czy pojawił się komunikat o błędzie (może być różnie stylowany)
        const errorElement = await page.$('.error-message') || await page.$('.alert-error');
        expect(errorElement).not.toBeNull();
        await debug(page, 'Błąd o już istniejącej nazwie użytkownika wyświetlony');
      } catch (error) {
        await debug(page, `Błąd: ${error.message}`);
        throw error;
      }
    }, 120000);
  });
  
  describe('Logowanie', () => {
    it('powinno pozwolić użytkownikowi na zalogowanie się', async () => {
      // Wyloguj się, jeśli jesteś zalogowany
      const logoutButton = await page.$('#logout-button');
      if (logoutButton) {
        await page.click('#logout-button');
        await page.waitForSelector('#login-button');
        await debug(page, 'Użytkownik wylogowany');
      }
      
      await page.goto('http://localhost:8000/');
      await page.waitForSelector('#login-button');
      
      // Kliknij przycisk logowania, aby otworzyć modal
      await page.click('#login-button');
      await page.waitForSelector('#login-modal', { visible: true });
      await debug(page, 'Modal logowania otwarty');
      
      // Wypełnij formularz logowania
      await page.type('#login-username', testUsername);
      await page.type('#login-password', testPassword);
      await debug(page, 'Formularz logowania wypełniony');
      
      // Kliknij przycisk submit i poczekaj na zalogowanie
      await Promise.all([
        page.click('#login-form button[type="submit"]'),
        page.waitForNavigation({ timeout: 10000 }).catch(err => console.log('Nawigacja nie nastąpiła, co jest OK'))
      ]);
      
      // Sprawdź, czy użytkownik jest zalogowany
      try {
        await page.waitForSelector('#username-display', { timeout: 15000 });
        const userDisplay = await page.$eval('#username-display', el => el.textContent);
        expect(userDisplay).toContain(testUsername);
        await debug(page, 'Użytkownik zalogowany');
      } catch (error) {
        await debug(page, `Błąd: ${error.message}`);
        throw error;
      }
    }, 120000);
    
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
      try {
        await page.waitForFunction(
          () => document.querySelector('.error-message') !== null || document.querySelector('.alert-error') !== null,
          { timeout: 10000 }
        );
        
        // Sprawdź, czy pojawił się komunikat o błędzie (może być różnie stylowany)
        const errorElement = await page.$('.error-message') || await page.$('.alert-error');
        expect(errorElement).not.toBeNull();
        await debug(page, 'Błąd nieprawidłowych danych logowania wyświetlony');
      } catch (error) {
        await debug(page, `Błąd: ${error.message}`);
        throw error;
      }
    }, 120000);
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
        page.waitForNavigation({ timeout: 10000 }).catch(err => console.log('Nawigacja nie nastąpiła, co jest OK'))
      ]);
      
      // Poczekaj na przycisk wylogowania
      try {
        await page.waitForSelector('#logout-button', { visible: true, timeout: 15000 });
        
        // Kliknij przycisk wylogowania
        await page.click('#logout-button');
        
        // Sprawdź, czy użytkownik jest wylogowany
        await page.waitForSelector('#login-button', { timeout: 10000 });
        const loginButton = await page.$('#login-button');
        expect(loginButton).not.toBeNull();
        await debug(page, 'Użytkownik wylogowany pomyślnie');
      } catch (error) {
        await debug(page, `Błąd: ${error.message}`);
        throw error;
      }
    }, 120000);
  });
}); 