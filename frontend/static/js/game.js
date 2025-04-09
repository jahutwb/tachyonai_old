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
  API_TIMEOUT: 10000, // 10 sekund timeout dla zapytań API
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
  PROFIT_CHANGE: '#profit-change',
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
    const timeoutId = setTimeout(() => controller.abort(), CONFIG.API_TIMEOUT);
    
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
      return await this.fetchWithAuth(`/api/sessions/${sessionId}/status`);
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
        method: 'POST'
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
        method: 'POST'
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
      return await this.fetchWithAuth('/api/sessions/new', {
        method: 'POST'
      });
    } catch (error) {
      Logger.error('Błąd podczas tworzenia nowej sesji', error);
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
    this.showPhase(DOM.PHASE_SELECT);
    
    // Reset stanu kurtyn
    const leftCurtain = document.querySelector(DOM.LEFT_CURTAIN);
    const rightCurtain = document.querySelector(DOM.RIGHT_CURTAIN);
    
    if (leftCurtain) {
      leftCurtain.classList.remove('curtain-expanded', 'curtain-hidden');
    }
    
    if (rightCurtain) {
      rightCurtain.classList.remove('curtain-expanded', 'curtain-hidden');
    }
    
    // Ukryj teksty akcji
    const leftAction = document.querySelector(DOM.LEFT_ACTION);
    const rightAction = document.querySelector(DOM.RIGHT_ACTION);
    
    if (leftAction) leftAction.style.display = 'none';
    if (rightAction) rightAction.style.display = 'none';
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
  static displayResult(result, stimulusUrl, percentChange) {
    // Ustawienie statusu wyniku
    const resultStatus = document.querySelector(DOM.RESULT_STATUS);
    if (resultStatus) {
      resultStatus.textContent = result === 'SUCCESS' ? 'SUKCES!' : 'PORAŻKA!';
      resultStatus.className = `result-status ${result === 'SUCCESS' ? 'success-result' : 'failure-result'}`;
    }
    
    // Wyświetlenie zmiany procentowej
    const profitChange = document.querySelector(DOM.PROFIT_CHANGE);
    if (profitChange) {
      profitChange.textContent = `Zmiana ceny: ${percentChange.toFixed(2)}%`;
    }
    
    // Wyświetlenie obrazu bodźca
    const stimulusImage = document.querySelector(DOM.STIMULUS_IMAGE);
    if (stimulusImage && stimulusUrl) {
      stimulusImage.style.display = 'block';
      stimulusImage.src = stimulusUrl;
      
      stimulusImage.onerror = () => {
        Logger.error('Błąd ładowania obrazu bodźca');
        stimulusImage.alt = 'Błąd ładowania obrazu';
        stimulusImage.style.display = 'none';
      };
      
      stimulusImage.onload = () => {
        Logger.log('Obraz bodźca załadowany pomyślnie');
      };
    } else if (stimulusImage) {
      stimulusImage.style.display = 'none';
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
    const messageElement = document.querySelector(DOM.LOADING_MESSAGE);
    
    if (messageElement) messageElement.textContent = message;
    if (overlay) overlay.style.display = 'flex';
  }
  
  /**
   * Ukrywa overlay ładowania
   */
  static hideLoadingOverlay() {
    const overlay = document.querySelector(DOM.LOADING_OVERLAY);
    if (overlay) overlay.style.display = 'none';
  }
  
  /**
   * Pokazuje dialog wyboru sesji
   */
  static showSessionDialog(sessionData) {
    // Ukryj wszystkie fazę gry
    const phases = [DOM.PHASE_SELECT, DOM.PHASE_RESULT];
    phases.forEach(selector => {
      const element = document.querySelector(selector);
      if (element) {
        element.style.display = 'none';
      }
    });
    
    // Stwórz i pokaż dialog
    const dialogOverlay = document.createElement('div');
    dialogOverlay.className = 'dialog-overlay';
    
    const dialogContainer = document.createElement('div');
    dialogContainer.className = 'dialog-container';
    
    let dialogContent = '';
    
    if (sessionData.session_status === 'ACTIVE') {
      // Dialog dla aktywnej sesji
      dialogContent = `
        <h2>Wykryto aktywną sesję</h2>
        <div class="session-stats">
          <p>Wyniki aktualnej sesji:</p>
          <ul>
            <li>Sukcesy: <span class="stat-value">${sessionData.session_stats.success_count}</span></li>
            <li>Porażki: <span class="stat-value">${sessionData.session_stats.failure_count}</span></li>
            <li>Współczynnik sukcesu: <span class="stat-value">${sessionData.session_stats.success_rate.toFixed(1)}%</span></li>
            <li>Zysk: <span class="stat-value">${((sessionData.session_stats.profit_factor - 1) * 100).toFixed(2)}%</span></li>
            <li>Pozostałe pary: <span class="stat-value">${sessionData.session_stats.remaining_pairs}</span></li>
          </ul>
        </div>
        <div class="dialog-buttons">
          <button id="continue-session" class="btn btn-primary">Kontynuuj sesję</button>
          <button id="new-session" class="btn btn-secondary">Rozpocznij nową sesję</button>
        </div>
      `;
      
      if (sessionData.has_unfinished_round) {
        dialogContent += `
          <div class="info-box">
            <p>Masz niedokończoną rundę, która zostanie załadowana po kontynuacji sesji.</p>
          </div>
        `;
      }
    } else if (sessionData.session_status === 'PENDING') {
      // Dialog dla oczekującej sesji (nowa pula)
      dialogContent = `
        <h2>Nowa pula gotowa</h2>
        <div class="session-stats">
          <p>Statystyki nowej puli bodźców:</p>
          <div class="pool-stats">
            <div class="pool-stat-group">
              <h3>Bodźce pozytywne:</h3>
              <ul>
                <li>Losowe: <span class="stat-value">${sessionData.new_pool_stats.pos_origins.random || 0}</span></li>
                <li>Zakupione: <span class="stat-value">${sessionData.new_pool_stats.pos_origins.bought || 0}</span></li>
                <li>Dzieci: <span class="stat-value">${sessionData.new_pool_stats.pos_origins.child || 0}</span></li>
              </ul>
            </div>
            <div class="pool-stat-group">
              <h3>Bodźce negatywne:</h3>
              <ul>
                <li>Losowe: <span class="stat-value">${sessionData.new_pool_stats.neg_origins.random || 0}</span></li>
                <li>Zakupione: <span class="stat-value">${sessionData.new_pool_stats.neg_origins.bought || 0}</span></li>
                <li>Dzieci: <span class="stat-value">${sessionData.new_pool_stats.neg_origins.child || 0}</span></li>
              </ul>
            </div>
          </div>
          <p>Łączna liczba par: <span class="stat-value">${sessionData.new_pool_stats.total_pairs}</span></p>
        </div>
        <div class="dialog-buttons">
          <button id="continue-session" class="btn btn-primary">Rozpocznij sesję z nową pulą</button>
          <button id="new-session" class="btn btn-secondary">Wygeneruj inną pulę</button>
        </div>
      `;
    } else {
      // Domyślny dialog, nigdy nie powinien być pokazywany, ale dla bezpieczeństwa
      dialogContent = `
        <h2>Rozpocznij nową sesję</h2>
        <div class="dialog-buttons">
          <button id="new-session" class="btn btn-primary">Rozpocznij nową sesję</button>
        </div>
      `;
    }
    
    dialogContainer.innerHTML = dialogContent;
    dialogOverlay.appendChild(dialogContainer);
    document.body.appendChild(dialogOverlay);
    
    return {
      overlay: dialogOverlay,
      container: dialogContainer
    };
  }
  
  /**
   * Usuwa dialog wyboru sesji
   */
  static removeSessionDialog(dialog) {
    if (dialog && dialog.overlay) {
      document.body.removeChild(dialog.overlay);
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
    this.data = {
      sessionId: null,
      currentRound: null,
      stats: {
        successes: 0,
        failures: 0,
        remainingPairs: 0,
        sessionProfitFactor: 1.0
      },
      prices: {
        startPrice: 0,
        endPrice: 0
      },
      isProcessing: false
    };
    this.apiService = new ApiService();
    
    // Inicjalizacja gry
    this.initialize();
  }
  
  /**
   * Inicjalizuje grę pobierając ID sesji z parametrów URL lub tworząc nową sesję
   */
  async initialize() {
    try {
      Logger.state(GameStates.INITIALIZING);
      UIController.showLoadingOverlay('Inicjalizacja gry...');
      
      // Pobierz ID sesji z parametrów URL
      const urlParams = new URLSearchParams(window.location.search);
      let sessionId = urlParams.get('session_id');
      
      // Jeśli jest sessionId w URL, użyj go bezpośrednio
      if (sessionId) {
        Logger.info(`Znaleziono ID sesji w URL: ${sessionId}`);
        this.data.sessionId = parseInt(sessionId, 10);
        
        // Podłącz obsługę zdarzeń
        this.attachEventListeners();
        
        // Przejdź do ładowania pierwszej rundy
        this.state = GameStates.LOADING_ROUND;
        await this.loadNewRound();
      } else {
        // Sprawdź status sesji
        Logger.info('Brak ID sesji w URL, sprawdzam status sesji...');
        const sessionStatus = await this.apiService.checkSessionStatus();
        
        if (sessionStatus.session_exists) {
          Logger.info(`Znaleziono istniejącą sesję o statusie: ${sessionStatus.session_status}`, sessionStatus);
          
          // Pokaż dialog wyboru
          const dialog = UIController.showSessionDialog(sessionStatus);
          
          // Obsługa wyboru użytkownika w dialogu
          const continueButton = dialog.container.querySelector('#continue-session');
          const newSessionButton = dialog.container.querySelector('#new-session');
          
          if (continueButton) {
            continueButton.addEventListener('click', async () => {
              try {
                UIController.showLoadingOverlay('Wznawianie sesji...');
                
                // Wznów sesję
                const sessionResponse = await this.apiService.resumeSession(sessionStatus.session_id);
                this.data.sessionId = sessionResponse.id;
                
                // Aktualizuj URL
                const newUrl = new URL(window.location.href);
                newUrl.searchParams.set('session_id', this.data.sessionId);
                window.history.pushState({}, '', newUrl);
                
                // Jeśli istnieje niedokończona runda, załaduj ją
                if (sessionStatus.has_unfinished_round && sessionStatus.unfinished_round_id) {
                  Logger.info(`Znaleziono niedokończoną rundę: ${sessionStatus.unfinished_round_id}`);
                  // Tutaj możesz dodać logikę ładowania niedokończonej rundy
                }
                
                // Usuń dialog
                UIController.removeSessionDialog(dialog);
                
                // Podłącz obsługę zdarzeń
                this.attachEventListeners();
                
                // Załaduj początkowe statystyki
                if (sessionStatus.session_stats) {
                  this.data.stats.successes = sessionStatus.session_stats.success_count;
                  this.data.stats.failures = sessionStatus.session_stats.failure_count;
                  this.data.stats.remainingPairs = sessionStatus.session_stats.remaining_pairs;
                  this.data.stats.sessionProfitFactor = sessionStatus.session_stats.profit_factor;
                  
                  // Aktualizuj UI
                  UIController.updateStats(this.data.stats);
                }
                
                // Przejdź do ładowania rundy
                this.state = GameStates.LOADING_ROUND;
                await this.loadNewRound();
              } catch (error) {
                Logger.error('Błąd podczas wznawiania sesji', error);
                alert('Nie udało się wznowić sesji. Spróbuj ponownie.');
                UIController.hideLoadingOverlay();
              }
            });
          }
          
          if (newSessionButton) {
            newSessionButton.addEventListener('click', async () => {
              try {
                UIController.showPoolGenerationSpinner();
                
                // Utwórz nową sesję
                const sessionResponse = await this.apiService.createSession();
                this.data.sessionId = sessionResponse.id;
                
                // Aktualizuj URL
                const newUrl = new URL(window.location.href);
                newUrl.searchParams.set('session_id', this.data.sessionId);
                window.history.pushState({}, '', newUrl);
                
                // Usuń dialog
                UIController.removeSessionDialog(dialog);
                
                // Podłącz obsługę zdarzeń
                this.attachEventListeners();
                
                // Zresetuj statystyki
                this.data.stats.successes = 0;
                this.data.stats.failures = 0;
                this.data.stats.remainingPairs = sessionResponse.remaining_pairs;
                this.data.stats.sessionProfitFactor = sessionResponse.session_profit_factor;
                
                // Aktualizuj UI
                UIController.updateStats(this.data.stats);
                
                // Przejdź do ładowania rundy
                this.state = GameStates.LOADING_ROUND;
                await this.loadNewRound();
              } catch (error) {
                Logger.error('Błąd podczas tworzenia nowej sesji', error);
                alert('Nie udało się utworzyć nowej sesji. Spróbuj ponownie.');
                UIController.stopPoolGenerationSpinner();
              }
            });
          }
        } else {
          // Jeśli nie ma żadnej sesji, utwórz nową
          Logger.info('Brak wcześniejszych sesji, tworzenie nowej sesji...');
          try {
            const response = await this.apiService.createSession();
            if (response && response.id) {
              sessionId = response.id;
              // Zaktualizuj URL, aby zawierał ID sesji (bez przeładowania strony)
              const newUrl = new URL(window.location.href);
              newUrl.searchParams.set('session_id', sessionId);
              window.history.pushState({}, '', newUrl);
              Logger.info(`Utworzono nową sesję z ID: ${sessionId}`);
              
              this.data.sessionId = parseInt(sessionId, 10);
              
              // Podłącz obsługę zdarzeń
              this.attachEventListeners();
              
              // Przejdź do ładowania pierwszej rundy
              this.state = GameStates.LOADING_ROUND;
              await this.loadNewRound();
            } else {
              throw new Error('Nie udało się utworzyć nowej sesji');
            }
          } catch (error) {
            throw new Error(`Nie udało się utworzyć nowej sesji: ${error.message}`);
          }
        }
      }
    } catch (error) {
      Logger.error('Błąd podczas inicjalizacji gry', error);
      alert('Nie udało się zainicjalizować gry. Spróbuj ponownie lub skontaktuj się z administratorem.');
    } finally {
      UIController.hideLoadingOverlay();
    }
  }
  
  /**
   * Podłącza nasłuchiwanie zdarzeń
   */
  attachEventListeners() {
    // Kliknięcia kurtyn
    const leftCurtain = document.querySelector(DOM.LEFT_CURTAIN);
    const rightCurtain = document.querySelector(DOM.RIGHT_CURTAIN);
    
    if (leftCurtain) {
      leftCurtain.addEventListener('click', () => this.handleCurtainClick('LEFT'));
    }
    
    if (rightCurtain) {
      rightCurtain.addEventListener('click', () => this.handleCurtainClick('RIGHT'));
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
    if (this.state !== GameStates.WAITING_FOR_CHOICE || this.data.isProcessing) {
      Logger.log(`Ignoruję kliknięcie kurtyny ${side} - nieprawidłowy stan: ${this.state}`);
      return;
    }
    
    // Ustaw flagę blokującą wielokrotne kliknięcia
    this.data.isProcessing = true;
    
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
    } finally {
      // Zawsze resetuj flagę blokady
      this.data.isProcessing = false;
    }
  }
  
  /**
   * Obsługuje kliknięcie przycisku następnej rundy
   */
  async handleNextRoundClick() {
    if (this.state !== GameStates.SHOWING_RESULT || this.data.isProcessing) {
      return;
    }
    
    this.data.isProcessing = true;
    
    try {
      this.state = GameStates.LOADING_ROUND;
      Logger.state(GameStates.LOADING_ROUND);
      await this.loadNewRound();
    } catch (error) {
      Logger.error('Błąd podczas ładowania nowej rundy', error);
      alert('Nie udało się załadować nowej rundy. Spróbuj ponownie.');
    } finally {
      this.data.isProcessing = false;
    }
  }
  
  /**
   * Obsługuje kliknięcie przycisku podsumowania
   */
  handleSummaryClick() {
    if (this.state !== GameStates.SHOWING_RESULT && this.state !== GameStates.SESSION_COMPLETED) {
      return;
    }
    
    // Przekieruj do strony podsumowania
    window.location.href = `/summary?session_id=${this.data.sessionId}`;
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
      
      // Przejdź do stanu oczekiwania na wybór
      this.state = GameStates.WAITING_FOR_CHOICE;
      Logger.state(GameStates.WAITING_FOR_CHOICE);
      
      // Ukryj loading
      UIController.hideLoadingOverlay();
    } catch (error) {
      Logger.error('Błąd podczas ładowania nowej rundy', error);
      throw error;
    }
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
      
      if (result.result === 'SUCCESS') {
        this.data.stats.successes++;
      } else {
        this.data.stats.failures++;
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
      const percentChange = ((endPrice - startPrice) / startPrice) * 100;
      
      // Wyświetl fazę wyniku z odpowiednio formatowanym komunikatem
      UIController.prepareResultPhase();
      UIController.displayResult(
        result.result,
        result.stimulus_url,
        percentChange
      );
    } catch (error) {
      Logger.error('Błąd podczas wyświetlania wyniku', error);
      throw error;
    }
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