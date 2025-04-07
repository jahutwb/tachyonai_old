/**
 * Konfiguracja testów E2E dla aplikacji tachyonai
 * Ten plik jest uruchamiany przed wykonaniem testów E2E
 */

jest.setTimeout(30000);

// Globalne funkcje pomocnicze
global.waitForTimeout = async (timeout) => {
  await new Promise(resolve => setTimeout(resolve, timeout));
};

/**
 * Funkcje pomocnicze do testów e2e
 */

/**
 * Loguje użytkownika do aplikacji
 * @param {Page} page - Instancja strony Puppeteer
 * @param {string} username - Nazwa użytkownika
 * @param {string} password - Hasło użytkownika
 * @returns {Promise<void>}
 */
async function login(page, username, password) {
  try {
    // Przejdź do strony logowania
    await page.goto('http://localhost:8000/login');
    
    // Wypełnij formularz logowania
    await page.waitForSelector('#login-form');
    await page.type('#username', username);
    await page.type('#password', password);
    
    // Wyślij formularz
    await Promise.all([
      page.click('#login-submit'),
      page.waitForNavigation({ waitUntil: 'networkidle0' })
    ]);
    
    // Sprawdź, czy logowanie się powiodło
    const isLoggedIn = await page.evaluate(() => {
      // Sprawdź, czy jesteśmy na stronie głównej i czy jest widoczna nazwa użytkownika
      const userElement = document.querySelector('#user-display');
      return userElement && userElement.textContent.includes(window.loggedInUsername);
    });
    
    if (!isLoggedIn) {
      console.warn('Logowanie mogło się nie powieść. Sprawdź selektory i stan po logowaniu.');
    }
  } catch (error) {
    console.error('Błąd podczas logowania:', error);
    throw error;
  }
}

/**
 * Rejestruje nowego użytkownika w aplikacji
 * @param {Page} page - Instancja strony Puppeteer
 * @param {string} username - Nazwa użytkownika
 * @param {string} password - Hasło użytkownika
 * @returns {Promise<void>}
 */
async function register(page, username, password) {
  try {
    // Przejdź do strony rejestracji
    await page.goto('http://localhost:8000/register');
    
    // Wypełnij formularz rejestracji
    await page.waitForSelector('#register-form');
    await page.type('#username', username);
    await page.type('#password', password);
    
    // Wyślij formularz
    await Promise.all([
      page.click('#register-submit'),
      page.waitForNavigation({ waitUntil: 'networkidle0' })
    ]);
    
    // Sprawdź, czy rejestracja się powiodła (powinniśmy być zalogowani)
    const isRegistered = await page.evaluate(() => {
      // Sprawdź, czy jesteśmy na stronie głównej i czy jest widoczna nazwa użytkownika
      const userElement = document.querySelector('#user-display');
      return userElement !== null;
    });
    
    if (!isRegistered) {
      console.warn('Rejestracja mogła się nie powieść. Sprawdź selektory i stan po rejestracji.');
    }
  } catch (error) {
    console.error('Błąd podczas rejestracji:', error);
    throw error;
  }
}

module.exports = {
  login,
  register
}; 