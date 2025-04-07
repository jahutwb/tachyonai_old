# Testy End-to-End (E2E) dla aplikacji tachyonai

Ten katalog zawiera testy end-to-end dla aplikacji tachyonai, które symulują rzeczywiste interakcje użytkownika z aplikacją przy użyciu Puppeteer.

## Struktura katalogów

```
tests/e2e/
├── setupTests.js        # Plik konfiguracyjny dla testów
├── auth.test.js         # Testy uwierzytelniania (rejestracja, logowanie, wylogowanie)
├── game.test.js         # Testy rozgrywki (tworzenie sesji, interakcja z kurtynami)
└── stats.test.js        # Testy statystyk i podsumowania sesji
```

## Wymagania

- Node.js (>= 16.x)
- npm
- Puppeteer
- Jest

## Instalacja zależności

```bash
npm install
```

## Uruchamianie testów

Przed uruchomieniem testów upewnij się, że serwer aplikacji jest włączony. Możesz uruchomić go ręcznie:

```bash
python -m uvicorn backend.main:app --port 8000
```

Lub skorzystać z automatycznego uruchamiania serwera przez Puppeteer (skonfigurowane w pliku `jest-puppeteer.config.js`):

```bash
npm run test:e2e
```

## Uruchamianie pojedynczego testu

```bash
npx jest tests/e2e/auth.test.js --config=jest.config.js
```

## Generowanie raportu z testów

```bash
npx jest --config=jest.config.js --json --outputFile=test-results.json
```

## Debugowanie testów

Aby uruchomić testy w trybie bez headless (z widoczną przeglądarką), należy zmodyfikować plik `jest-puppeteer.config.js`:

```javascript
module.exports = {
  // ...
  launch: {
    headless: false,  // zmień na false
    slowMo: 100,      // zwiększ wartość dla wolniejszego wykonania (w ms)
    // ...
  }
};
```

## Tworzenie własnych testów E2E

1. Stwórz nowy plik w katalogu `tests/e2e/` z nazwą zakończoną na `.test.js`
2. Zaimportuj wymagane zależności
3. Użyj składni Jest do definiowania testów
4. Skorzystaj z API Puppeteer do interakcji ze stroną

Przykład:

```javascript
describe('Mój nowy test', () => {
  beforeAll(async () => {
    await page.goto('http://localhost:8000/');
  });
  
  it('powinien wykonać jakąś akcję', async () => {
    await page.click('#moj-przycisk');
    const wynik = await page.$('#wynik');
    expect(wynik).not.toBeNull();
  });
});
```

## Integracja z CI/CD

Testy E2E są automatycznie uruchamiane w ramach GitHub Actions po każdym push do repozytorium lub pull request do gałęzi `master`. Konfiguracja znajduje się w pliku `.github/workflows/e2e-tests.yml`. 