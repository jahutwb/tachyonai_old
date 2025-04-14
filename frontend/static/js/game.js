/**
 * TachyonAI - Game Module
 *
 * Implementacja interfejsu gry przetwarzającego rundy, wybory użytkownika i wyniki.
 * Architektura oparta na maszynie stanów i jasnym rozdzieleniu odpowiedzialności.
 */

/**
 * =====================================
 * DEFINICJE STAŁYCH I KONFIGURACJA
 * =====================================
 */

// Stany gry
const GameStates = {
  INITIALIZING: 'initializing',       // Inicjalizacja gry
  LOADING_ROUND: 'loading_round',     // Ładowanie nowej rundy
  WAITING_FOR_CHOICE: 'waiting_for_choice', // Oczekiwanie na wybór użytkownika
  PROCESSING_CHOICE: 'processing_choice',  // Przetwarzanie wyboru
  SHOWING_RESULT: 'showing_result',   // Wyświetlanie wyniku
  SESSION_COMPLETED: 'session_completed'  // Sesja zakończona
};

// Konfiguracja
const CONFIG = {
  API_TIMEOUT: 10000, // 10 sekund timeout dla standardowych zapytań API
  SESSION_API_TIMEOUT: 180000, // 180 sekund timeout dla operacji związanych z sesjami
  PRICE_REFRESH_INTERVAL: 1000, // Interwał odświeżania ceny (ms)
  RESULT_DISPLAY_TIME: 2000, // Czas wyświetlania wyniku (ms)
  DEBUG: true // Włącza zaawansowane logowanie
};

// Selektory DOM
const DOM = {
  // Kontenery faz
  PHASE_SELECT: '#game-phase-select',
  PHASE_RESULT: '#game-phase-result',

  // Kurtyny
  LEFT_CURTAIN: '#left-curtain',
  RIGHT_CURTAIN: '#right-curtain',
  LEFT_ACTION: '#left-action',
  RIGHT_ACTION: '#right-action',

  // Wyniki
  RESULT_STATUS: '#result-status',
  STIMULUS_IMAGE: '#stimulus-image',

  // Przyciski
  NEXT_ROUND_BUTTON: '#next-round-button',
  SUMMARY_BUTTON: '#summary-button',

  // Statystyki
  SUCCESS_COUNT: '#success-count',
  FAILURE_COUNT: '#failure-count',
  SUCCESS_RATE: '#success-rate',
  PROFIT_FACTOR: '#profit-factor',
  REMAINING_PAIRS: '#remaining-pairs',

  // Overlay ładowania
  LOADING_OVERLAY: '#loading-overlay',
  LOADING_MESSAGE: '#loading-message'
};

/**
 * =====================================
 * KLASA LOGGER - OBSŁUGA LOGOWANIA
 * =====================================
 */
class Logger {
  static log(message, data = null) {
    if (CONFIG.DEBUG) {
      if (data) {
        console.log(`%c${message}`, 'color: #3498db', data);
      } else {
        console.log(`%c${message}`, 'color: #3498db');
      }
    }
  }

  static info(message, data = null) {
    if (CONFIG.DEBUG) {
      if (data) {
        console.log(`%c[Info] ${message}`, 'color: #3498db', data);
      } else {
        console.log(`%c[Info] ${message}`, 'color: #3498db');
      }
    }
  }

  static error(message, error = null) {
    console.error(`%c${message}`, 'color: #e74c3c', error);
    if (error && error.stack) {
      console.error(error.stack);
    }
  }

  static state(stateName, data = null) {
    if (CONFIG.DEBUG) {
      console.log(`%c[Stan: ${stateName}]`, 'color: #2ecc71; font-weight: bold', data);
    }
  }

  static api(method, url, data = null) {
    if (CONFIG.DEBUG) {
      console.log(`%c[API] ${method} ${url}`, 'color: #9b59b6', data);
    }
  }
}

/**
 * =====================================
 * KLASA API SERVICE - KOMUNIKACJA Z BACKENDEM
 * =====================================
 */
class ApiService {
  /**
   * Wykonuje zapytanie z uwzględnieniem autoryzacji
   */
  async fetchWithAuth(url, options = {}) {
    Logger.api(options.method || 'GET', url, options.body);

    const token = localStorage.getItem('token');
    if (!token) {
      window.location.href = '/login';
      throw new Error('Brak tokenu autoryzacyjnego');
    }

    const controller = new AbortController();
    const timeoutValue = options.timeout || CONFIG.API_TIMEOUT;
    const timeoutId = setTimeout(() => controller.abort(), timeoutValue);

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`Błąd HTTP: ${response.status} ${response.statusText}`);
      }

      // Dla zapytań bez odpowiedzi (np. DELETE)
      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new Error('Zapytanie przerwane - przekroczono limit czasu');
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Pobiera aktualną cenę
   */
  async getCurrentPrice() {
    try {
      const response = await this.fetchWithAuth('/api/price/current');
      return response.price;
    } catch (error) {
      Logger.error('Błąd podczas pobierania aktualnej ceny', error);
      throw error;
    }
  }

  /**
   * Pobiera nową rundę dla sesji
   */
  async getNewRound(sessionId) {
    try {
      return await this.fetchWithAuth(`/api/rounds/next?session_id=${sessionId}`);
    } catch (error) {
      Logger.error('Błąd podczas pobierania nowej rundy', error);
      throw error;
    }
  }

  /**
   * Wysyła wybór użytkownika i otrzymuje wynik
   */
  async submitChoice(sessionId, roundId, side) {
    try {
      const data = {
        session_id: sessionId,
        round_id: roundId,
        side: side
      };

      return await this.fetchWithAuth('/api/rounds/choice', {
        method: 'POST',
        body: JSON.stringify(data)
      });
    } catch (error) {
      Logger.error('Błąd podczas wysyłania wyboru', error);
      throw error;
    }
  }

  /**
   * Pobiera aktualny stan sesji
   */
  async getSessionStatus(sessionId) {
    try {
      return await this.fetchWithAuth(`/api/sessions/${sessionId}/status`, {
        timeout: CONFIG.SESSION_API_TIMEOUT
      });
    } catch (error) {
      Logger.error('Błąd podczas pobierania statusu sesji', error);
      throw error;
    }
  }

  /**
   * Sprawdza status sesji (istniejąca, oczekująca, nowa)
   */
  async checkSessionStatus() {
    try {
      return await this.fetchWithAuth('/api/sessions', {
        method: 'POST',
        timeout: CONFIG.SESSION_API_TIMEOUT
      });
    } catch (error) {
      Logger.error('Błąd podczas sprawdzania statusu sesji', error);
      throw error;
    }
  }

  /**
   * Wznawia istniejącą sesję
   */
  async resumeSession(sessionId) {
    try {
      return await this.fetchWithAuth(`/api/sessions/resume/${sessionId}`, {
        method: 'POST',
        timeout: CONFIG.SESSION_API_TIMEOUT
      });
    } catch (error) {
      Logger.error(`Błąd podczas wznawiania sesji ${sessionId}`, error);
      throw error;
    }
  }

  /**
   * Tworzy nową sesję
   */
  async createSession() {
    try {
      return await this.fetchWithAuth('/api/sessions', {
        method: 'POST',
        timeout: CONFIG.SESSION_API_TIMEOUT
      });
    } catch (error) {
      Logger.error('Błąd podczas tworzenia nowej sesji', error);
      throw error;
    }
  }

  /**
   * Pobiera rundy dla sesji
   */
  async getRoundsForSession(sessionId) {
    try {
      return await this.fetchWithAuth(`/api/sessions/${sessionId}/rounds`);
    } catch (error) {
      Logger.error(`Błąd podczas pobierania rund dla sesji ${sessionId}`, error);
      throw error;
    }
  }
}

/**
 * =====================================
 * KLASA UI CONTROLLER - ZARZĄDZANIE INTERFEJSEM
 * =====================================
 */
class UIController {
  /**
   * Pokazuje określoną fazę gry i ukrywa pozostałe
   */
  static showPhase(phaseSelector) {
    const phases = [DOM.PHASE_SELECT, DOM.PHASE_RESULT];

    phases.forEach(selector => {
      const element = document.querySelector(selector);
      if (element) {
        element.style.display = selector === phaseSelector ? 'block' : 'none';
      }
    });
  }

  /**
   * Przygotowuje interfejs do wyświetlenia fazy wyboru
   */
  static prepareChoicePhase() {
    console.log('[Debug] Przygotowywanie fazy wyboru...');
    this.showPhase(DOM.PHASE_SELECT);

    // Reset stanu kurtyn
    const leftCurtain = document.querySelector(DOM.LEFT_CURTAIN);
    const rightCurtain = document.querySelector(DOM.RIGHT_CURTAIN);

    console.log('[Debug] Elementy kurtyn:', { leftCurtain, rightCurtain });

    if (leftCurtain) {
      leftCurtain.classList.remove('curtain-expanded', 'curtain-hidden');
      leftCurtain.style.display = 'flex'; // Upewnij się, że kurtyna jest widoczna
    } else {
      console.error('[Debug] Nie znaleziono elementu lewej kurtyny!');
    }

    if (rightCurtain) {
      rightCurtain.classList.remove('curtain-expanded', 'curtain-hidden');
      rightCurtain.style.display = 'flex'; // Upewnij się, że kurtyna jest widoczna
    } else {
      console.error('[Debug] Nie znaleziono elementu prawej kurtyny!');
    }

    // Ukryj teksty akcji
    const leftAction = document.querySelector(DOM.LEFT_ACTION);
    const rightAction = document.querySelector(DOM.RIGHT_ACTION);

    if (leftAction) leftAction.style.display = 'none';
    if (rightAction) rightAction.style.display = 'none';

    // Upewnij się, że kontener gry jest widoczny
    const gameContainer = document.querySelector(DOM.PHASE_SELECT);
    if (gameContainer) {
      gameContainer.style.display = 'block';
      console.log('[Debug] Kontener gry ustawiony jako widoczny');
    } else {
      console.error('[Debug] Nie znaleziono kontenera gry!');
    }

    console.log('[Debug] Faza wyboru przygotowana');
  }

  /**
   * Przygotowuje interfejs do wyświetlenia fazy wyniku
   */
  static prepareResultPhase() {
    this.showPhase(DOM.PHASE_RESULT);
  }

  /**
   * Rozszerza wybraną kurtynę i ukrywa drugą
   */
  static expandCurtain(side) {
    const leftCurtain = document.querySelector(DOM.LEFT_CURTAIN);
    const rightCurtain = document.querySelector(DOM.RIGHT_CURTAIN);

    if (side === 'LEFT') {
      leftCurtain.classList.add('curtain-expanded');
      rightCurtain.classList.add('curtain-hidden');
    } else {
      rightCurtain.classList.add('curtain-expanded');
      leftCurtain.classList.add('curtain-hidden');
    }
  }

  /**
   * Wyświetla wynik i bodziec
   */
  static displayResult(result, stimulusUrl, profitFraction) {
    // Ustawienie statusu wyniku
    const resultStatus = document.querySelector(DOM.RESULT_STATUS);
    if (resultStatus) {
        // Konwertujemy profit_fraction na procent
        const profitPercent = (profitFraction * 100).toFixed(2);
        const profitSign = profitPercent >= 0 ? '+' : '';

        // Obsługa wyniku jako enum (API zwraca SUCCESS lub FAILURE jako string)
        let resultText, resultClass;
        if (result === 'SUCCESS') {
            resultText = 'Sukces';
            resultClass = 'success';
        } else if (result === 'FAILURE') {
            resultText = 'Porażka';
            resultClass = 'failure';
        } else {
            Logger.error('Nieznany wynik rundy', result);
            resultText = 'Nieznany wynik';
            resultClass = 'failure';
        }

        resultStatus.textContent = `${resultText}: ${profitSign}${profitPercent}%`;
        resultStatus.className = resultClass;
    }

    // Wyświetlenie obrazu bodźca
    const stimulusImage = document.querySelector(DOM.STIMULUS_IMAGE);
    if (stimulusImage && stimulusUrl) {
        stimulusImage.style.display = 'block';

        // Upewnij się, że używamy /full zamiast /thumbnail dla większych obrazów
        if (!stimulusUrl.includes('/full')) {
            stimulusUrl = stimulusUrl.replace('/thumbnail', '/full');
        }

        stimulusImage.src = stimulusUrl;

        console.log('[Debug] URL obrazu bodźca:', stimulusUrl);

        // Dodaj możliwość powiększenia obrazu po kliknięciu
        stimulusImage.onclick = function() {
            window.open(stimulusUrl, '_blank');
        };

        stimulusImage.onerror = function() {
            Logger.error('Błąd ładowania obrazu bodźca', { url: stimulusUrl });
            stimulusImage.src = '/static/images/default-stimulus.png';
        };
        stimulusImage.onload = function() {
            Logger.info('Obraz bodźca załadowany', { url: stimulusUrl });
        };
    }
  }

  /**
   * Aktualizuje statystyki na podstawie stanu gry
   */
  static updateStats(stats) {
    // Aktualizacja liczników
    const successCount = document.querySelector(DOM.SUCCESS_COUNT);
    const failureCount = document.querySelector(DOM.FAILURE_COUNT);
    const successRate = document.querySelector(DOM.SUCCESS_RATE);
    const profitFactor = document.querySelector(DOM.PROFIT_FACTOR);
    const remainingPairs = document.querySelector(DOM.REMAINING_PAIRS);

    if (successCount) successCount.textContent = stats.successes;
    if (failureCount) failureCount.textContent = stats.failures;

    const total = stats.successes + stats.failures;
    if (successRate && total > 0) {
      const rate = (stats.successes / total) * 100;
      successRate.textContent = `${rate.toFixed(0)}%`;
    } else if (successRate) {
      successRate.textContent = '0%';
    }

    if (profitFactor) {
      const profitPercentage = (stats.sessionProfitFactor - 1) * 100;
      profitFactor.textContent = `${profitPercentage.toFixed(2)}%`;
    }

    if (remainingPairs) remainingPairs.textContent = stats.remainingPairs;
  }

  /**
   * Aktualizuje widoczność przycisków na podstawie stanu sesji
   */
  static updateButtons(isSessionCompleted) {
    const nextRoundButton = document.querySelector(DOM.NEXT_ROUND_BUTTON);
    const summaryButton = document.querySelector(DOM.SUMMARY_BUTTON);

    if (nextRoundButton) {
      nextRoundButton.style.display = isSessionCompleted ? 'none' : 'inline-block';
    }

    if (summaryButton) {
      summaryButton.style.display = isSessionCompleted ? 'inline-block' : 'none';
    }
  }

  /**
   * Pokazuje overlay ładowania z opcjonalnym komunikatem
   */
  static showLoadingOverlay(message = 'Ładowanie...') {
    const overlay = document.querySelector(DOM.LOADING_OVERLAY);
    const messageEl = document.querySelector(DOM.LOADING_MESSAGE);

    if (overlay && messageEl) {
      messageEl.textContent = message;
      overlay.style.display = 'flex';
    }
  }

  /**
   * Aktualizuje komunikat ładowania
   */
  static updateLoadingMessage(message) {
    const messageEl = document.querySelector(DOM.LOADING_MESSAGE);
    if (messageEl) {
      messageEl.innerHTML = message;
    }
  }

  /**
   * Ukrywa overlay ładowania
   */
  static hideLoadingOverlay() {
    const overlay = document.querySelector(DOM.LOADING_OVERLAY);
    if (overlay) {
      overlay.style.display = 'none';
    }
  }

  /**
   * Wyświetla dialog wyboru sesji
   */
  static showSessionDialog(sessionData) {
    // Tworzymy warstwę overlay
    const overlay = document.createElement('div');
    overlay.className = 'dialog-overlay';

    // Tworzymy kontener dla dialogu
    const dialogContainer = document.createElement('div');
    dialogContainer.className = 'dialog-container';

    let dialogContent = `
      <h2>Wybór sesji</h2>
    `;

    if (sessionData.session_status === 'ACTIVE') {
      // Aktywna sesja
      dialogContent += `
        <div class="session-stats">
          <p>Masz aktywną sesję z następującymi statystykami:</p>
          <ul>
            <li>Sukcesy: <span class="stat-value">${sessionData.session_stats.success_count}</span></li>
            <li>Porażki: <span class="stat-value">${sessionData.session_stats.failure_count}</span></li>
            <li>Wskaźnik sukcesu: <span class="stat-value">${sessionData.session_stats.success_rate.toFixed(1)}%</span></li>
            <li>Współczynnik zysku: <span class="stat-value">${sessionData.session_stats.profit_factor.toFixed(3)}</span></li>
            <li>Pozostałe pary: <span class="stat-value">${sessionData.session_stats.remaining_pairs}</span></li>
          </ul>
        </div>
      `;

      if (sessionData.has_unfinished_round) {
        dialogContent += `
          <div class="info-box">
            <p>Uwaga: Masz niedokończoną rundę, która zostanie wznowiona.</p>
          </div>
        `;
      }

    } else if (sessionData.session_status === 'PENDING') {
      // Oczekująca sesja (wygenerowana pula)
      const poolStats = sessionData.new_pool_stats || sessionData.pool_origin_stats || { pos_origins: {}, neg_origins: {} };
      const posOrigins = poolStats.positive || poolStats.pos_origins || {};
      const negOrigins = poolStats.negative || poolStats.neg_origins || {};

      dialogContent += `
        <div class="session-stats">
          <p>Wygenerowano nową pulę bodźców:</p>
          <div class="pool-stats">
            <div class="pool-stat-group">
              <h3>Bodźce pozytywne</h3>
              <ul>
                <li>Z poprzedniej sesji: <span class="stat-value">${posOrigins.bought || 0}</span></li>
                <li>Dzieci (algorytm): <span class="stat-value">${posOrigins.child || 0}</span></li>
                <li>Losowe: <span class="stat-value">${posOrigins.random || 0}</span></li>
              </ul>
            </div>
            <div class="pool-stat-group">
              <h3>Bodźce negatywne</h3>
              <ul>
                <li>Z poprzedniej sesji: <span class="stat-value">${negOrigins.bought || 0}</span></li>
                <li>Dzieci (algorytm): <span class="stat-value">${negOrigins.child || 0}</span></li>
                <li>Losowe: <span class="stat-value">${negOrigins.random || 0}</span></li>
              </ul>
            </div>
          </div>
        </div>
      `;

      // Informacja o algorytmie quasi-genetycznym
      if ((posOrigins.child || 0) > 0 || (negOrigins.child || 0) > 0) {
        dialogContent += `
          <div class="info-box">
            <p>Nowa sesja zawiera bodźce wygenerowane algorytmem quasi-genetycznym na podstawie poprzedniej sesji.</p>
          </div>
        `;
      } else if ((posOrigins.random || 0) > 0 || (negOrigins.random || 0) > 0) {
        dialogContent += `
          <div class="info-box">
            <p>Nowa sesja zawiera losowo wybrane bodźce.</p>
          </div>
        `;
      }
    } else if (sessionData.session_status === 'GENERATING') {
      // Sesja w trakcie generowania - pokazujemy tylko informację
      dialogContent += `
        <div class="session-stats">
          <p>Trwa generowanie nowej puli bodźców...</p>
          <div id="loading-dots">...</div>
        </div>
        <div class="info-box">
          <p>Proces może potrwać kilka chwil, zwłaszcza jeśli używany jest algorytm quasi-genetyczny.</p>
        </div>
      `;
    } else if (sessionData.session_status === 'ERROR') {
      // Błąd w trakcie generowania
      dialogContent += `
        <div class="session-stats">
          <p>Wystąpił błąd podczas generowania puli bodźców.</p>
        </div>
        <div class="info-box">
          <p>Spróbuj ponownie lub skontaktuj się z administratorem systemu.</p>
        </div>
      `;
    }

    // Przyciski akcji
    dialogContent += `<div class="dialog-buttons">`;

    if (sessionData.session_status === 'ACTIVE') {
      dialogContent += `
        <button id="resume-session-btn" class="button primary-button">Kontynuuj sesję</button>
        <button id="new-session-btn" class="button">Utwórz nową sesję</button>
      `;
    } else if (sessionData.session_status === 'PENDING') {
      dialogContent += `
        <button id="activate-session-btn" class="button primary-button">Rozpocznij sesję</button>
        <button id="new-session-btn" class="button">Utwórz inną sesję</button>
      `;
    } else if (sessionData.session_status === 'GENERATING') {
      dialogContent += `
        <button id="check-status-btn" class="button primary-button">Sprawdź ponownie</button>
      `;
    } else if (sessionData.session_status === 'ERROR') {
      dialogContent += `
        <button id="new-session-btn" class="button primary-button">Utwórz nową sesję</button>
      `;
    }

    dialogContent += `</div>`;

    // Ustawiamy treść dialogu
    dialogContainer.innerHTML = dialogContent;

    // Dodajemy kontener do overlaya
    overlay.appendChild(dialogContainer);

    // Dodajemy overlay do DOM
    document.body.appendChild(overlay);

    // Zwracamy obiekt z overlayem i kontenerem dla łatwiejszego zarządzania
    return {
      overlay: overlay,
      container: dialogContainer,
      buttons: {
        activate: overlay.querySelector('#activate-session-btn'),
        new: overlay.querySelector('#new-session-btn'),
        resume: overlay.querySelector('#resume-session-btn'),
        check: overlay.querySelector('#check-status-btn')
      }
    };
  }

  /**
   * Usuwa dialog wyboru sesji
   */
  static removeSessionDialog(dialog) {
    if (!dialog) return;

    // Dialog może być bezpośrednim elementem DOM lub obiektem z właściwością overlay
    if (dialog.overlay) {
      document.body.removeChild(dialog.overlay);
    } else if (dialog.parentNode) {
      dialog.parentNode.removeChild(dialog);
    } else if (typeof dialog === 'object' && dialog instanceof Element) {
      if (document.body.contains(dialog)) {
        document.body.removeChild(dialog);
      }
    } else {
      console.error('Nie można usunąć dialogu:', dialog);
    }
  }

  /**
   * Pokazuje animację ładowania podczas generowania nowej puli
   */
  static showPoolGenerationSpinner() {
    this.showLoadingOverlay('Generowanie nowej puli bodźców...');

    // Dodaj animowaną kropkę
    const messageElement = document.querySelector(DOM.LOADING_MESSAGE);
    if (messageElement) {
      const dotAnimation = document.createElement('span');
      dotAnimation.id = 'loading-dots';
      dotAnimation.textContent = '...';
      messageElement.appendChild(dotAnimation);

      // Animuj kropki
      let dots = 0;
      const animationInterval = setInterval(() => {
        dots = (dots + 1) % 4;
        dotAnimation.textContent = '.'.repeat(dots);
      }, 500);

      // Zapisz interval, aby móc go później wyczyścić
      this.poolGenerationInterval = animationInterval;
    }
  }

  /**
   * Zatrzymuje animację ładowania puli
   */
  static stopPoolGenerationSpinner() {
    this.hideLoadingOverlay();
    if (this.poolGenerationInterval) {
      clearInterval(this.poolGenerationInterval);
      this.poolGenerationInterval = null;
    }
  }
}

/**
 * =====================================
 * KLASA GAME CONTROLLER - GŁÓWNA LOGIKA GRY
 * =====================================
 */
class GameController {
  constructor() {
    // Inicjalizacja stanu
    this.state = GameStates.INITIALIZING;
    Logger.state(this.state);

    // Referencje do innych komponentów
    this.apiService = new ApiService();

    // Dane gry
    this.data = {
      sessionId: null,
      currentRound: null,
      prices: {
        startPrice: 0,
        endPrice: 0
      },
      stats: {
        successes: 0,
        failures: 0,
        remainingPairs: 0,
        sessionProfitFactor: 0
      }
    };

    // Inicjalizacja gry
    this.initialize();
  }

  /**
   * Inicjalizuje grę - sprawdza stan sesji i ustawia odpowiednie parametry
   */
  async initialize() {
    try {
      UIController.showLoadingOverlay('Inicjalizacja gry...');

      // Sprawdź czy jest sessionId w URL
      const urlParams = new URLSearchParams(window.location.search);
      const sessionId = urlParams.get('session_id');

      if (sessionId) {
        UIController.updateLoadingMessage('Ładowanie istniejącej sesji...');
        Logger.info(`Znaleziono ID sesji w URL: ${sessionId}`);

        // Jeśli mamy ID sesji, pobierz jej stan
        try {
          this.data.sessionId = parseInt(sessionId);
          const sessionInfo = await this.apiService.resumeSession(sessionId);
          await this.setupSessionData(sessionInfo);

          // Podłącz listenery zdarzeń po załadowaniu sesji
          this.attachEventListeners();
        } catch (error) {
          Logger.error(`Błąd podczas ładowania sesji ${sessionId}`, error);
          UIController.updateLoadingMessage(`Błąd: ${error.message || 'Nie udało się załadować sesji'}. Tworzenie nowej...`);
          await this.checkAndCreateSession();
        }
      } else {
        // Jeśli nie ma ID sesji w URL, sprawdź czy istnieje aktywna sesja lub stwórz nową
        await this.checkAndCreateSession();

        // Podłącz listenery zdarzeń po utworzeniu/załadowaniu sesji
        this.attachEventListeners();
      }

    } catch (error) {
      Logger.error('Błąd podczas inicjalizacji gry', error);
      UIController.hideLoadingOverlay();

      // Pokaż komunikat o błędzie
      const errorMessage = document.createElement('div');
      errorMessage.className = 'error-message';
      errorMessage.innerHTML = `
        <h3>Nie udało się zainicjalizować gry</h3>
        <p>${error.message || 'Sprawdź połączenie z serwerem i odśwież stronę.'}</p>
        <button id="reload-btn" class="button primary-button">Spróbuj ponownie</button>
      `;
      document.querySelector('#game-container').appendChild(errorMessage);

      // Dodaj obsługę przycisku ponownego ładowania
      document.querySelector('#reload-btn').addEventListener('click', () => {
        window.location.reload();
      });
    }
  }

  /**
   * Ustawia dane sesji na podstawie odpowiedzi z API
   */
  async setupSessionData(sessionData) {
    try {
      // Ustawienie ID sesji
      this.data.sessionId = sessionData.id;

      // Aktualizacja statystyk sesji
      this.data.stats.successes = sessionData.success_count || 0;
      this.data.stats.failures = sessionData.failure_count || 0;
      this.data.stats.remainingPairs = sessionData.remaining_pairs || 0;
      this.data.stats.sessionProfitFactor = sessionData.session_profit_factor || 1.0;

      // Aktualizacja UI
      UIController.updateStats(this.data.stats);

      // Jeśli mamy niedokończoną rundę, załaduj ją
      if (sessionData.has_unfinished_round) {
        Logger.info(`Wznawianie niedokończonej rundy: ${sessionData.unfinished_round_id}`);
        UIController.updateLoadingMessage('Wznawianie niedokończonej rundy...');
        await this.loadRound(sessionData.unfinished_round_id);
      } else {
        // W przeciwnym razie załaduj nową rundę
        Logger.info('Brak niedokończonej rundy, tworzenie nowej rundy...');
        UIController.updateLoadingMessage('Ładowanie nowej rundy...');
        await this.loadNewRound();
      }

      // Sprawdź, czy sesja jest zakończona
      if (sessionData.status === "COMPLETED") {
        this.state = GameStates.SESSION_COMPLETED;
        Logger.state(GameStates.SESSION_COMPLETED);
        UIController.updateButtons(true);
      } else {
        // Upewnij się, że przejdziemy do stanu oczekiwania na wybór
        if (this.state !== GameStates.WAITING_FOR_CHOICE) {
          this.state = GameStates.WAITING_FOR_CHOICE;
          Logger.state(GameStates.WAITING_FOR_CHOICE);
        }
      }

      // Ukryj overlay ładowania
      UIController.hideLoadingOverlay();
    } catch (error) {
      Logger.error('Błąd podczas konfigurowania sesji', error);
      UIController.hideLoadingOverlay();
      throw error;
    }
  }

  /**
   * Ładuje nową rundę
   */
  async loadNewRound() {
    UIController.showLoadingOverlay('Ładowanie rundy...');

    try {
      // Pobierz nową rundę z API
      const roundData = await this.apiService.getNewRound(this.data.sessionId);

      // Zaktualizuj stan gry
      this.data.currentRound = roundData;
      this.data.prices.startPrice = roundData.start_price;
      this.data.prices.endPrice = 0;

      // Logowanie stanu
      Logger.log('Załadowano nową rundę', roundData);

      // Przygotuj interfejs
      UIController.prepareChoicePhase();

      // Podłącz listenery kurtyn
      this.attachEventListeners();

      // Przejdź do stanu oczekiwania na wybór
      this.state = GameStates.WAITING_FOR_CHOICE;
      Logger.state(GameStates.WAITING_FOR_CHOICE);

      // Ukryj loading
      UIController.hideLoadingOverlay();
    } catch (error) {
      Logger.error('Błąd podczas ładowania nowej rundy', error);
      // Próba odzyskania - nawet w przypadku błędu przygotuj interfejs
      UIController.prepareChoicePhase();
      this.attachEventListeners();
      this.state = GameStates.WAITING_FOR_CHOICE;
      Logger.state(GameStates.WAITING_FOR_CHOICE);
      UIController.hideLoadingOverlay();
      alert(`Błąd podczas ładowania rundy: ${error.message || 'Nieznany błąd'}. Spróbuj odświeżyć stronę.`);
      throw error;
    }
  }

  /**
   * Ładuje rundę o podanym ID
   */
  async loadRound(roundId) {
    UIController.showLoadingOverlay('Ładowanie rundy...');

    try {
      // Pobierz rundę z API
      const roundData = await this.apiService.getRound(roundId);

      // Zaktualizuj stan gry
      this.data.currentRound = roundData;
      this.data.prices.startPrice = roundData.start_price;
      this.data.prices.endPrice = 0;

      // Logowanie stanu
      Logger.log('Załadowano rundę', roundData);

      // Przygotuj interfejs
      UIController.prepareChoicePhase();

      // Podłącz listenery kurtyn
      this.attachEventListeners();

      // Przejdź do stanu oczekiwania na wybór
      this.state = GameStates.WAITING_FOR_CHOICE;
      Logger.state(GameStates.WAITING_FOR_CHOICE);

      // Ukryj loading
      UIController.hideLoadingOverlay();
    } catch (error) {
      Logger.error('Błąd podczas ładowania rundy', error);
      throw error;
    }
  }

  /**
   * Podłącza nasłuchiwanie zdarzeń
   */
  attachEventListeners() {
    // Kliknięcia kurtyn
    const leftCurtain = document.querySelector(DOM.LEFT_CURTAIN);
    const rightCurtain = document.querySelector(DOM.RIGHT_CURTAIN);

    console.log('[Debug] Przypisywanie zdarzeń kliknięcia do kurtyn:', { leftCurtain, rightCurtain });

    if (leftCurtain) {
      // Usuwamy stare listeners, aby uniknąć duplikacji
      leftCurtain.removeEventListener('click', () => this.handleCurtainClick('LEFT'));
      leftCurtain.addEventListener('click', () => this.handleCurtainClick('LEFT'));
      console.log('[Debug] Zdarzenie kliknięcia przypisane do lewej kurtyny');
    } else {
      console.error('[Debug] Nie można znaleźć lewej kurtyny do przypisania zdarzenia!');
    }

    if (rightCurtain) {
      // Usuwamy stare listeners, aby uniknąć duplikacji
      rightCurtain.removeEventListener('click', () => this.handleCurtainClick('RIGHT'));
      rightCurtain.addEventListener('click', () => this.handleCurtainClick('RIGHT'));
      console.log('[Debug] Zdarzenie kliknięcia przypisane do prawej kurtyny');
    } else {
      console.error('[Debug] Nie można znaleźć prawej kurtyny do przypisania zdarzenia!');
    }

    // Przycisk następnej rundy
    const nextRoundButton = document.querySelector(DOM.NEXT_ROUND_BUTTON);
    if (nextRoundButton) {
      nextRoundButton.addEventListener('click', () => this.handleNextRoundClick());
    }

    // Przycisk podsumowania
    const summaryButton = document.querySelector(DOM.SUMMARY_BUTTON);
    if (summaryButton) {
      summaryButton.addEventListener('click', () => this.handleSummaryClick());
    }
  }

  /**
   * Obsługuje kliknięcie kurtyny
   */
  async handleCurtainClick(side) {
    // Ignoruj kliknięcia jeśli nie jesteśmy w stanie oczekiwania na wybór
    if (this.state !== GameStates.WAITING_FOR_CHOICE) {
      Logger.log(`Ignoruję kliknięcie kurtyny ${side} - nieprawidłowy stan: ${this.state}`);
      return;
    }

    try {
      // Przejdź do stanu przetwarzania wyboru
      this.state = GameStates.PROCESSING_CHOICE;
      Logger.state(GameStates.PROCESSING_CHOICE, { side });

      // Pokaż wizualnie wybraną kurtynę
      UIController.expandCurtain(side);

      // Przetwórz wybór
      await this.processChoice(side);
    } catch (error) {
      Logger.error('Błąd podczas obsługi kliknięcia kurtyny', error);
      alert('Wystąpił błąd podczas przetwarzania wyboru. Spróbuj ponownie.');

      // Resetuj stan i wróć do oczekiwania na wybór
      this.state = GameStates.WAITING_FOR_CHOICE;
      UIController.prepareChoicePhase();
    }
  }

  /**
   * Obsługuje kliknięcie przycisku następnej rundy
   */
  async handleNextRoundClick() {
    if (this.state !== GameStates.SHOWING_RESULT) {
      return;
    }

    try {
      this.state = GameStates.LOADING_ROUND;
      Logger.state(GameStates.LOADING_ROUND);
      await this.loadNewRound();
    } catch (error) {
      Logger.error('Błąd podczas ładowania nowej rundy', error);
      alert('Nie udało się załadować nowej rundy. Spróbuj ponownie.');
    }
  }

  /**
   * Obsługuje kliknięcie przycisku podsumowania
   */
  async handleSummaryClick() {
    if (this.state !== GameStates.SHOWING_RESULT && this.state !== GameStates.SESSION_COMPLETED) {
      return;
    }

    // Pobierz ID sesji
    const sessionId = this.data.sessionId;

    // Najpierw przekieruj do podsumowania
    window.location.href = `/summary?session_id=${sessionId}`;
  }

  /**
   * Przetwarza wybór użytkownika
   */
  async processChoice(side) {
    UIController.showLoadingOverlay('Przetwarzanie wyboru...');

    try {
      // Pobierz aktualną cenę
      const currentPrice = await this.apiService.getCurrentPrice();
      this.data.prices.startPrice = currentPrice;

      // Wyślij wybór do API
      const result = await this.apiService.submitChoice(
        this.data.sessionId,
        this.data.currentRound.id,
        side
      );

      // Zaktualizuj statystyki
      this.data.prices.endPrice = result.end_price;
      this.data.stats.remainingPairs = result.remaining_pairs;
      this.data.stats.sessionProfitFactor = result.session_profit_factor;

      // Handle result enum (API returns SUCCESS or FAILURE as string)
      if (result.result === 'SUCCESS') {
        this.data.stats.successes++;
      } else if (result.result === 'FAILURE') {
        this.data.stats.failures++;
      } else {
        Logger.error('Nieznany wynik rundy', result.result);
      }

      // Sprawdź, czy sesja jest zakończona
      const isSessionCompleted = (
        result.session_status === 'COMPLETED' ||
        result.remaining_pairs === 0
      );

      // Zaktualizuj UI
      UIController.updateStats(this.data.stats);
      UIController.updateButtons(isSessionCompleted);

      // Pokaż wynik
      await this.showResult(result);

      // Jeśli sesja jest zakończona, zaktualizuj stan
      if (isSessionCompleted) {
        this.state = GameStates.SESSION_COMPLETED;
        Logger.state(GameStates.SESSION_COMPLETED);
      }
    } catch (error) {
      Logger.error('Błąd podczas przetwarzania wyboru', error);
      throw error;
    } finally {
      UIController.hideLoadingOverlay();
    }
  }

  /**
   * Wyświetla wynik wyboru
   */
  async showResult(result) {
    this.state = GameStates.SHOWING_RESULT;
    Logger.state(GameStates.SHOWING_RESULT, result);

    try {
      // Oblicz procentową zmianę ceny
      const startPrice = this.data.prices.startPrice;
      const endPrice = this.data.prices.endPrice;
      const profitFraction = (endPrice - startPrice) / startPrice;

      // Wyświetl fazę wyniku z odpowiednio formatowanym komunikatem
      UIController.prepareResultPhase();
      UIController.displayResult(
        result.result,
        result.stimulus_url,
        profitFraction
      );
    } catch (error) {
      Logger.error('Błąd podczas wyświetlania wyniku', error);
      throw error;
    }
  }

  /**
   * Sprawdza status sesji i tworzy nową lub proponuje wznowienie istniejącej
   */
  async checkAndCreateSession() {
    try {
      // Sprawdź status sesji (czy istnieje aktywna, oczekująca, czy trzeba stworzyć nową)
      UIController.updateLoadingMessage('Sprawdzanie statusu sesji...');
      const sessionData = await this.apiService.checkSessionStatus();

      if (sessionData.session_exists) {
        Logger.info(`Wykryto sesję w statusie: ${sessionData.session_status}`);

        if (sessionData.session_status === 'GENERATING') {
          // Sesja w trakcie generowania - pokazujemy dialog z informacją
          await this.handleGeneratingSession(sessionData);
        } else if (sessionData.session_status === 'ACTIVE') {
          // Wykryto aktywną sesję - automatyczne wznowienie bez dialogu
          UIController.updateLoadingMessage('Wznawianie aktywnej sesji...');
          try {
            this.data.sessionId = sessionData.session_id;
            const sessionDetails = await this.apiService.resumeSession(sessionData.session_id);
            await this.setupSessionData(sessionDetails);
          } catch (error) {
            Logger.error('Błąd podczas wznawiania sesji', error);
            // Jeśli błąd dotyczy braku rund, spróbuj wymusić utworzenie nowej rundy
            try {
              await this.loadNewRound();
            } catch (innerError) {
              Logger.error('Nie udało się utworzyć nowej rundy po błędzie', innerError);
              UIController.updateLoadingMessage(`Błąd: ${error.message || 'Nie udało się wznowić sesji'}`);
              throw error;
            }
          }
        } else if (sessionData.session_status === 'PENDING') {
          // Wykryto sesję PENDING - automatyczne aktywowanie bez dialogu
          UIController.updateLoadingMessage('Aktywowanie oczekującej sesji...');
          try {
            console.log(`Automatyczne aktywowanie sesji PENDING ${sessionData.session_id}...`);
            const activatedSession = await this.apiService.resumeSession(sessionData.session_id);
            console.log('Sesja aktywowana:', activatedSession);

            this.data.sessionId = sessionData.session_id;
            await this.setupSessionData(activatedSession);

            // Jawnie ładujemy pierwszą rundę dla aktywowanej sesji
            try {
              await this.loadNewRound();
            } catch (roundError) {
              Logger.error('Błąd podczas ładowania pierwszej rundy', roundError);
              UIController.updateLoadingMessage(`Błąd: ${roundError.message || 'Nie udało się załadować rundy'}`);
              alert(`Sesja została aktywowana, ale wystąpił błąd podczas ładowania pierwszej rundy: ${roundError.message}`);
            }
          } catch (error) {
            Logger.error('Błąd podczas automatycznego aktywowania sesji PENDING', error);
            UIController.updateLoadingMessage(`Błąd: ${error.message || 'Nie udało się aktywować sesji'}`);
            // Wyświetl dodatkowy komunikat
            alert(`Nie udało się aktywować sesji: ${error.message}. Spróbuj ponownie.`);
          }
        } else {
          // Inne statusy - pokaż dialog wyboru
          const dialog = UIController.showSessionDialog(sessionData);
          UIController.hideLoadingOverlay();

          // Dodaj obsługę przycisków
          if (sessionData.session_status === 'PENDING') {
            // Obsługa aktywacji oczekującej sesji
            document.querySelector('#activate-session-btn').addEventListener('click', async () => {
              UIController.showLoadingOverlay('Aktywowanie sesji...');
              try {
                console.log(`Aktywowanie sesji ${sessionData.session_id}...`);
                const token = localStorage.getItem('token');
                console.log(`Token autoryzacji: ${token ? 'dostępny' : 'brak'}`);

                const activatedSession = await this.apiService.resumeSession(sessionData.session_id);
                console.log('Sesja aktywowana:', activatedSession);

                this.data.sessionId = sessionData.session_id;
                await this.setupSessionData(activatedSession);

                // Upewniamy się, że dialog jest usunięty przed załadowaniem nowej rundy
                UIController.removeSessionDialog(dialog);

                // Jawnie ładujemy pierwszą rundę dla aktywowanej sesji
                try {
                  await this.loadNewRound();
                } catch (roundError) {
                  Logger.error('Błąd podczas ładowania pierwszej rundy', roundError);
                  UIController.updateLoadingMessage(`Błąd: ${roundError.message || 'Nie udało się załadować rundy'}`);
                  alert(`Sesja została aktywowana, ale wystąpił błąd podczas ładowania pierwszej rundy: ${roundError.message}`);
                }
              } catch (error) {
                Logger.error('Błąd podczas aktywowania sesji', error);
                UIController.updateLoadingMessage(`Błąd: ${error.message || 'Nie udało się aktywować sesji'}`);
                // Wyświetl dodatkowy komunikat
                alert(`Nie udało się aktywować sesji: ${error.message}. Spróbuj ponownie.`);
              }
            });

            // Obsługa tworzenia nowej sesji
            document.querySelector('#new-session-btn').addEventListener('click', async () => {
              UIController.showLoadingOverlay('Tworzenie nowej sesji...');
              try {
                const newSession = await this.apiService.createSession();
                this.data.sessionId = newSession.id;
                await this.setupSessionData(newSession);
                UIController.removeSessionDialog(dialog);
              } catch (error) {
                Logger.error('Błąd podczas tworzenia nowej sesji', error);
                UIController.updateLoadingMessage(`Błąd: ${error.message || 'Nie udało się utworzyć nowej sesji'}`);
              }
            });
          } else if (sessionData.session_status === 'ERROR') {
            // Obsługa nowej sesji po błędzie
            document.querySelector('#new-session-btn').addEventListener('click', async () => {
              UIController.showLoadingOverlay('Tworzenie nowej sesji...');
              try {
                const newSession = await this.apiService.createSession();
                this.data.sessionId = newSession.id;
                await this.setupSessionData(newSession);
                UIController.removeSessionDialog(dialog);
              } catch (error) {
                Logger.error('Błąd podczas tworzenia nowej sesji', error);
                UIController.updateLoadingMessage(`Błąd: ${error.message || 'Nie udało się utworzyć nowej sesji'}`);
              }
            });
          }
        }
      } else {
        // Brak sesji - tworzymy nową
        Logger.info('Brak istniejącej sesji, tworzenie nowej');
        UIController.updateLoadingMessage('Tworzenie nowej sesji... (może to potrwać do 60 sekund)');

        try {
          const newSession = await this.apiService.createSession();
          this.data.sessionId = newSession.id;
          await this.setupSessionData(newSession);
        } catch (error) {
          Logger.error('Błąd podczas tworzenia nowej sesji', error);
          UIController.updateLoadingMessage(`Błąd: ${error.message || 'Nie udało się utworzyć nowej sesji'}`);
          throw error;
        }
      }
    } catch (error) {
      Logger.error('Błąd podczas sprawdzania/tworzenia sesji', error);
      UIController.hideLoadingOverlay();

      // Wyświetl przyjazny komunikat o błędzie
      const errorContainer = document.querySelector('#game-container');
      if (errorContainer) {
        const errorMessage = document.createElement('div');
        errorMessage.className = 'error-message';
        errorMessage.innerHTML = `
          <h3>Problem z połączeniem</h3>
          <p>Generowanie nowej sesji może zająć dłuższy czas. Możesz spróbować ponownie za chwilę lub odświeżyć stronę.</p>
          <p class="error-details">${error.message}</p>
          <button id="retry-btn" class="button primary-button">Spróbuj ponownie</button>
        `;

        // Wyczyść istniejącą zawartość i dodaj komunikat
        errorContainer.innerHTML = '';
        errorContainer.appendChild(errorMessage);

        // Dodaj obsługę przycisku
        document.querySelector('#retry-btn').addEventListener('click', () => {
          window.location.reload();
        });
      }

      throw error;
    }
  }

  /**
   * Obsługa sesji w trakcie generowania
   */
  async handleGeneratingSession(sessionData) {
    // Pokazujemy dialog z informacją o generowaniu
    const dialog = UIController.showSessionDialog(sessionData);
    UIController.hideLoadingOverlay();

    // Co 5 sekund sprawdzamy status
    const checkStatus = async () => {
      try {
        const updatedStatus = await this.apiService.getSessionStatus(sessionData.session_id);
        if (updatedStatus.session_status !== 'GENERATING') {
          // Status się zmienił, odświeżamy stronę
          UIController.removeSessionDialog(dialog);
          UIController.showLoadingOverlay('Pula została wygenerowana, odświeżanie...');
          await this.checkAndCreateSession();
        } else {
          // Nadal generowanie, sprawdzamy ponownie za 5 sekund
          setTimeout(checkStatus, 5000);
        }
      } catch (error) {
        Logger.error('Błąd podczas sprawdzania statusu generowania', error);
        // W przypadku błędu też sprawdzamy ponownie za 5 sekund
        setTimeout(checkStatus, 5000);
      }
    };

    // Rozpocznij sprawdzanie statusu
    setTimeout(checkStatus, 5000);

    // Obsługa przycisku ręcznego sprawdzenia statusu
    document.querySelector('#check-status-btn').addEventListener('click', async () => {
      UIController.removeSessionDialog(dialog);
      UIController.showLoadingOverlay('Sprawdzanie statusu sesji...');
      await this.checkAndCreateSession();
    });
  }
}

/**
 * =====================================
 * INICJALIZACJA APLIKACJI
 * =====================================
 */
document.addEventListener('DOMContentLoaded', () => {
  // Utworzenie instancji kontrolera gry
  const gameController = new GameController();

  // Wyświetlanie nazwy użytkownika (jeśli dostępne)
  const token = localStorage.getItem('token');
  if (token) {
    try {
      const tokenData = JSON.parse(atob(token.split('.')[1]));
      const usernameDisplay = document.getElementById('username-display');
      if (usernameDisplay && tokenData.sub) {
        usernameDisplay.textContent = tokenData.sub;
      }
    } catch (error) {
      Logger.error('Błąd podczas dekodowania tokenu', error);
    }
  }

  // Obsługa przycisku wylogowania
  const logoutButton = document.getElementById('logout-button');
  if (logoutButton) {
    logoutButton.addEventListener('click', () => {
      localStorage.removeItem('token');
      window.location.href = '/login';
    });
  }
});