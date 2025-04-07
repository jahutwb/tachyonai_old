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
    isWaitingForPriceChange: false,
    leftAction: null,  // Przechowuje akcję dla lewej kurtyny (BUY/SELL) - ukryta przed użytkownikiem
    rightAction: null  // Przechowuje akcję dla prawej kurtyny (BUY/SELL) - ukryta przed użytkownikiem
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
    document.getElementById('game-phase-select').style.display = 'block';
    document.getElementById('game-phase-result').style.display = 'none';
    
    // Reset kurtyn
    document.getElementById('left-curtain').classList.remove('curtain-expanded', 'curtain-hidden');
    document.getElementById('right-curtain').classList.remove('curtain-expanded', 'curtain-hidden');
    
    // Ukrywamy informacje o akcjach - użytkownik nie powinien widzieć przypisanych akcji
    const leftActionElement = document.getElementById('left-action');
    const rightActionElement = document.getElementById('right-action');
    
    leftActionElement.style.display = 'none';
    rightActionElement.style.display = 'none';
}

async function showResultPhase(result, stimulusUrl) {
    console.log(`Wyświetlam fazę wynikową: ${result}, URL bodźca: ${stimulusUrl}`);
    
    // Ukryj fazę wyboru
    document.querySelector('.game-phase-select').style.display = 'none';
    
    // Pokaż fazę wyniku
    const resultPhase = document.querySelector('.game-phase-result');
    resultPhase.style.display = 'block';
    
    // Ustaw tekst wyniku
    const resultText = document.getElementById('result-text');
    resultText.textContent = result === 'SUCCESS' ? 'SUKCES!' : 'PORAŻKA!';
    resultText.className = result === 'SUCCESS' ? 'success' : 'failure';
    
    // Załaduj obraz bodźca
    const stimulusImage = document.getElementById('stimulus-image');
    
    if (stimulusUrl) {
        console.log(`Ładowanie obrazu z URL: ${stimulusUrl}`);
        
        try {
            // Pobierz token z localStorage
            const token = localStorage.getItem('token');
            
            if (!token) {
                console.error('Brak tokenu autoryzacyjnego w localStorage');
                return;
            }
            
            // Ustaw na początku placeholder lub ukryj obraz
            stimulusImage.src = '';
            stimulusImage.style.display = 'none';
            
            // Pobierz obraz z uwzględnieniem autoryzacji
            const response = await fetch(stimulusUrl, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`Błąd pobierania obrazu: ${response.status} ${response.statusText}`);
            }
            
            // Konwertuj odpowiedź na blob i utwórz URL
            const blob = await response.blob();
            const imageUrl = URL.createObjectURL(blob);
            
            // Ustaw obraz
            stimulusImage.onload = function() {
                stimulusImage.style.display = 'block';
                console.log('Obraz bodźca załadowany pomyślnie');
            };
            
            stimulusImage.onerror = function() {
                console.error('Błąd ładowania obrazu bodźca');
                stimulusImage.style.display = 'none';
            };
            
            stimulusImage.src = imageUrl;
        } catch (error) {
            console.error('Błąd podczas ładowania obrazu bodźca:', error);
            stimulusImage.style.display = 'none';
        }
    } else {
        console.warn('Brak URL obrazu bodźca');
        stimulusImage.style.display = 'none';
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
        
        // Przypisanie akcji do kurtyn na podstawie danych z serwera
        GameState.leftAction = roundData.left_action;
        GameState.rightAction = roundData.right_action;
        
        console.log(`Lewa kurtyna: ${GameState.leftAction}, Prawa kurtyna: ${GameState.rightAction}`);
        
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
        
        console.log('Odpowiedź z serwera:', resultData);
        
        if (resultData.result === 'SUCCESS') {
            GameState.successes++;
            // Pokaż pozytywny bodziec
            await showResultPhase('SUCCESS', resultData.stimulus_url);
        } else {
            GameState.failures++;
            // Pokaż negatywny bodziec
            await showResultPhase('FAILURE', resultData.stimulus_url);
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