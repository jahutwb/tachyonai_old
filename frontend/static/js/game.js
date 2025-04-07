// Stan aplikacji
const GameState = {
    sessionId: null,
    currentRound: null,
    successes: 0,
    failures: 0,
    remainingPairs: 6,
    sessionProfitFactor: 1.0,
    startPrice: 0,
    endPrice: 0,
    isWaitingForPriceChange: false
};

// Pomocnicze funkcje
function updateStatsView() {
    document.getElementById('success-count').textContent = GameState.successes;
    document.getElementById('failure-count').textContent = GameState.failures;
    
    const totalRounds = GameState.successes + GameState.failures;
    const successRate = totalRounds > 0 ? Math.round((GameState.successes / totalRounds) * 100) : 0;
    document.getElementById('success-rate').textContent = `${successRate}%`;
    
    const profit = ((GameState.sessionProfitFactor - 1) * 100).toFixed(2);
    document.getElementById('profit-factor').textContent = `${profit}%`;
    
    document.getElementById('remaining-pairs').textContent = GameState.remainingPairs;
}

function showLoadingOverlay(message) {
    document.getElementById('loading-message').textContent = message;
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoadingOverlay() {
    document.getElementById('loading-overlay').style.display = 'none';
}

function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/';
        return;
    }

    if (!options.headers) {
        options.headers = {};
    }

    options.headers['Authorization'] = `Bearer ${token}`;
    if (options.method && options.method !== 'GET' && !options.headers['Content-Type']) {
        options.headers['Content-Type'] = 'application/json';
    }

    return fetch(url, options);
}

function showSelectPhase() {
    document.getElementById('game-phase-select').style.display = 'flex';
    document.getElementById('game-phase-result').style.display = 'none';
    
    // Reset kurtyn
    const leftCurtain = document.getElementById('left-curtain');
    const rightCurtain = document.getElementById('right-curtain');
    
    leftCurtain.classList.remove('curtain-expanded', 'curtain-hidden');
    rightCurtain.classList.remove('curtain-expanded', 'curtain-hidden');
}

function showResultPhase(result, profitFraction, imageUrl) {
    document.getElementById('game-phase-select').style.display = 'none';
    document.getElementById('game-phase-result').style.display = 'block';
    
    // Ustawienie rezultatu
    const resultStatus = document.getElementById('result-status');
    resultStatus.textContent = result === 'SUCCESS' ? 'SUKCES' : 'PORAŻKA';
    resultStatus.className = `result-status ${result.toLowerCase()}`;
    
    // Ustawienie zmiany zysku
    const profitChange = document.getElementById('profit-change');
    const profitPercent = (profitFraction * 100).toFixed(2);
    const sign = profitFraction >= 0 ? '+' : '';
    profitChange.textContent = `${sign}${profitPercent}%`;
    profitChange.className = `profit-change ${profitFraction >= 0 ? 'positive' : 'negative'}`;
    
    // Ustawienie obrazu
    document.getElementById('stimulus-image').src = imageUrl;
    
    // Przyciski
    if (GameState.remainingPairs > 0) {
        document.getElementById('next-round-button').style.display = 'block';
        document.getElementById('summary-button').style.display = 'none';
    } else {
        document.getElementById('next-round-button').style.display = 'none';
        document.getElementById('summary-button').style.display = 'block';
    }
}

// Inicjalizacja i ładowanie sesji
async function initGame() {
    showLoadingOverlay('Inicjalizacja gry...');
    
    // Pobierz ID sesji z URL (jeśli istnieje)
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    try {
        if (sessionId) {
            // Użyj istniejącej sesji
            GameState.sessionId = sessionId;
            await loadSessionState();
        } else {
            // Utwórz nową sesję
            await createNewSession();
        }
        
        // Załaduj pierwszą rundę
        await loadNextRound();
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd inicjalizacji gry:', error);
        alert('Wystąpił błąd podczas inicjalizacji gry. Spróbuj ponownie.');
        window.location.href = '/';
    }
}

async function loadSessionState() {
    const response = await fetchWithAuth(`/api/sessions/${GameState.sessionId}`);
    if (!response.ok) {
        throw new Error('Nie można załadować stanu sesji');
    }
    
    const session = await response.json();
    GameState.successes = session.success_count || 0;
    GameState.failures = session.failure_count || 0;
    GameState.remainingPairs = session.remaining_pairs;
    GameState.sessionProfitFactor = session.session_profit_factor;
    
    // Aktualizacja widoku statystyk
    updateStatsView();
}

async function createNewSession() {
    showLoadingOverlay('Tworzenie nowej sesji...');
    
    const response = await fetchWithAuth('/api/sessions', {
        method: 'POST'
    });
    
    if (!response.ok) {
        throw new Error('Nie można utworzyć nowej sesji');
    }
    
    const session = await response.json();
    GameState.sessionId = session.id;
    GameState.successes = 0;
    GameState.failures = 0;
    GameState.remainingPairs = session.remaining_pairs;
    GameState.sessionProfitFactor = session.session_profit_factor;
    
    // Aktualizacja URL z ID sesji
    const newUrl = `${window.location.pathname}?session_id=${GameState.sessionId}`;
    window.history.pushState({ path: newUrl }, '', newUrl);
    
    // Aktualizacja widoku statystyk
    updateStatsView();
}

// Obsługa rund
async function loadNextRound() {
    showLoadingOverlay('Przygotowanie rundy...');
    
    try {
        const response = await fetchWithAuth(`/api/rounds/next?session_id=${GameState.sessionId}`);
        
        if (!response.ok) {
            throw new Error('Nie można załadować następnej rundy');
        }
        
        const roundData = await response.json();
        GameState.currentRound = roundData;
        
        // Przejście do fazy wyboru
        showSelectPhase();
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania rundy:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

async function selectCurtain(side) {
    if (GameState.isWaitingForPriceChange) return;
    
    const leftCurtain = document.getElementById('left-curtain');
    const rightCurtain = document.getElementById('right-curtain');
    
    // Animacja kurtyn
    if (side === 'LEFT') {
        leftCurtain.classList.add('curtain-expanded');
        rightCurtain.classList.add('curtain-hidden');
    } else {
        leftCurtain.classList.add('curtain-hidden');
        rightCurtain.classList.add('curtain-expanded');
    }
    
    showLoadingOverlay('Oczekiwanie na zmianę ceny...');
    GameState.isWaitingForPriceChange = true;
    
    try {
        const response = await fetchWithAuth(`/api/rounds/choice`, {
            method: 'POST',
            body: JSON.stringify({
                session_id: GameState.sessionId,
                round_id: GameState.currentRound.id,
                side: side
            })
        });
        
        if (!response.ok) {
            throw new Error('Błąd przetwarzania wyboru');
        }
        
        const resultData = await response.json();
        
        // Aktualizacja stanu
        GameState.startPrice = resultData.start_price;
        GameState.endPrice = resultData.end_price;
        GameState.remainingPairs = resultData.remaining_pairs;
        GameState.sessionProfitFactor = resultData.session_profit_factor;
        
        if (resultData.result === 'SUCCESS') {
            GameState.successes++;
            // Pokaż pozytywny bodziec
            showResultPhase('SUCCESS', resultData.profit_fraction, resultData.stimulus_url);
        } else {
            GameState.failures++;
            // Pokaż negatywny bodziec
            showResultPhase('FAILURE', resultData.profit_fraction, resultData.stimulus_url);
        }
        
        // Aktualizacja widoku statystyk
        updateStatsView();
        
        GameState.isWaitingForPriceChange = false;
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd wyboru:', error);
        alert(`Błąd: ${error.message}`);
        GameState.isWaitingForPriceChange = false;
        hideLoadingOverlay();
        
        // Przywróć stan początkowy (reset animacji kurtyn)
        showSelectPhase();
    }
}

function goToSummary() {
    window.location.href = `/summary?session_id=${GameState.sessionId}`;
}

// Obsługa zdarzeń
document.addEventListener('DOMContentLoaded', () => {
    // Inicjalizacja gry
    initGame();
    
    // Obsługa kliknięcia kurtyn
    document.getElementById('left-curtain').addEventListener('click', () => selectCurtain('LEFT'));
    document.getElementById('right-curtain').addEventListener('click', () => selectCurtain('RIGHT'));
    
    // Obsługa przycisków akcji
    document.getElementById('next-round-button').addEventListener('click', loadNextRound);
    document.getElementById('summary-button').addEventListener('click', goToSummary);
}); 