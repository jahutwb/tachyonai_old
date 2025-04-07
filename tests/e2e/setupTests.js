/**
 * Konfiguracja testów E2E dla aplikacji tachyonai
 * Ten plik jest uruchamiany przed wykonaniem testów E2E
 */

jest.setTimeout(30000);

// Globalne funkcje pomocnicze
global.waitForTimeout = async (timeout) => {
  await new Promise(resolve => setTimeout(resolve, timeout));
};

// Funkcja logująca użytkownika
global.login = async (page, username = 'testuser', password = 'password123') => {
  await page.goto('http://localhost:8000/login');
  await page.waitForSelector('#username');
  await page.type('#username', username);
  await page.type('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForNavigation();
};

// Funkcja rejestrująca użytkownika
global.register = async (page, username = 'newtestuser', password = 'password123') => {
  await page.goto('http://localhost:8000/signup');
  await page.waitForSelector('#username');
  await page.type('#username', username);
  await page.type('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForNavigation();
}; 