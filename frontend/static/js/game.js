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
    rightAction: null, // Przechowuje akcję dla prawej kurtyny (BUY/SELL) - ukryta przed użytkownikiem
    profit_fraction: 0
};

// Funkcja diagnostyczna do logowania stanu aplikacji
function logAppState(action) {
    console.group(`App State - ${action}`);
    console.log(`Session ID: ${GameState.sessionId}`);
    console.log(`Current Round: ${GameState.currentRound ? GameState.currentRound.id : 'none'}`);
    console.log(`Successes: ${GameState.successes}`);
    console.log(`Failures: ${GameState.failures}`);
    console.log(`Remaining Pairs: ${GameState.remainingPairs}`);
    console.log(`Session Profit Factor: ${GameState.sessionProfitFactor}`);
    console.log(`Start Price: ${GameState.startPrice}`);
    console.log(`End Price: ${GameState.endPrice}`);
    console.log(`Is Waiting For Price Change: ${GameState.isWaitingForPriceChange}`);
    console.log(`Left Action: ${GameState.leftAction}`);
    console.log(`Right Action: ${GameState.rightAction}`);
    console.log(`JWT Token: ${localStorage.getItem('token') ? 'Present' : 'Missing'}`);
    console.groupEnd();
}

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
    
    try {
        // Ukryj fazę wyboru - poprawiony selektor z .game-phase-select na #game-phase-select
        const selectPhaseElement = document.getElementById('game-phase-select');
        if (!selectPhaseElement) {
            console.error('Element #game-phase-select nie został znaleziony');
            // Próba alternatywnego selektora jako ostateczna próba
            const altSelectPhase = document.querySelector('.game-container');
            if (altSelectPhase) {
                console.log('Znaleziono alternatywny element .game-container');
                altSelectPhase.style.display = 'none';
            } else {
                console.error('Alternatywny element .game-container również nie został znaleziony');
            }
        } else {
            selectPhaseElement.style.display = 'none';
        }
        
        // Pokaż fazę wyniku
        const resultPhase = document.getElementById('game-phase-result');
        if (!resultPhase) {
            console.error('Element #game-phase-result nie został znaleziony');
            return;  // Przerwij wykonanie jeśli nie znaleziono elementu
        }
        resultPhase.style.display = 'block';
        
        // Ustaw tekst wyniku - element w HTML to result-status, nie result-text
        const resultText = document.getElementById('result-status');
        if (!resultText) {
            console.error('Element #result-status nie został znaleziony');
        } else {
            resultText.textContent = result === 'SUCCESS' ? 'SUKCES!' : 'PORAŻKA!';
            resultText.className = result === 'SUCCESS' ? 'success' : 'failure';
        }
        
        // Wyświetl informacje o zmianie zysku
        const profitChangeElement = document.getElementById('profit-change');
        if (profitChangeElement) {
            // Użyj wartości z odpowiedzi serwera zamiast GameState.profit_fraction
            const profitFraction = GameState.endPrice ? 
                (GameState.endPrice - GameState.startPrice) / GameState.startPrice : 0;
            
            const profitValue = profitFraction != 0 ? 
                (profitFraction > 0 ? `+${(profitFraction * 100).toFixed(2)}%` : `${(profitFraction * 100).toFixed(2)}%`) :
                '0.00%';
            
            profitChangeElement.textContent = profitValue;
            profitChangeElement.className = profitFraction > 0 ? 'positive' : 'negative';
        } else {
            console.error('Element #profit-change nie został znaleziony');
        }
        
        // Zarządzanie przyciskami w zależności od pozostałych par
        const nextRoundButton = document.getElementById('next-round-button');
        const summaryButton = document.getElementById('summary-button');
        
        if (GameState.remainingPairs <= 0) {
            // Ostatnia runda - pokaż tylko przycisk podsumowania
            if (nextRoundButton) nextRoundButton.style.display = 'none';
            if (summaryButton) summaryButton.style.display = 'inline-block';
            console.log('Ostatnia runda - wyświetlam tylko przycisk podsumowania');
        } else {
            // Normalna runda - pokaż przycisk następnej rundy, ukryj podsumowanie
            if (nextRoundButton) nextRoundButton.style.display = 'inline-block';
            if (summaryButton) summaryButton.style.display = 'none';
            console.log(`Pozostało par: ${GameState.remainingPairs} - wyświetlam przycisk następnej rundy`);
        }
        
        // Załaduj obraz bodźca
        const stimulusImage = document.getElementById('stimulus-image');
        if (!stimulusImage) {
            console.error('Element #stimulus-image nie został znaleziony');
            return;
        }
        
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
    } catch (error) {
        console.error('Błąd wyświetlania fazy wynikowej:', error);
        hideLoadingOverlay();
    }
}

// Funkcja do pobierania aktualnej ceny BTC
async function getCurrentPrice() {
    try {
        const response = await fetchWithAuth('/api/price/current');
        if (!response.ok) {
            throw new Error(`Błąd pobierania ceny: ${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        return data.price;
    } catch (error) {
        console.error('Błąd podczas pobierania aktualnej ceny:', error);
        return 50000.0; // Wartość domyślna w przypadku błędu
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
        
        logAppState('Inicjalizacja gry zakończona');
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
    try {
        logAppState('Przed załadowaniem nowej rundy');
        
        const response = await fetchWithAuth(`/api/rounds/next?session_id=${GameState.sessionId}`);
        if (!response.ok) {
            throw new Error(`Błąd pobierania następnej rundy: ${response.status} ${response.statusText}`);
        }
        
        const roundData = await response.json();
        console.log('Odpowiedź serwera:', roundData);
        
        // Aktualizuj stan gry o nową rundę
        GameState.currentRound = roundData;
        GameState.leftAction = roundData.left_action;
        GameState.rightAction = roundData.right_action;
        GameState.startPrice = roundData.start_price;
        GameState.endPrice = 0;  // Resetujemy tylko endPrice
        GameState.isWaitingForPriceChange = false;  // Resetujemy flagę czekania
        
        // Zaloguj stan aplikacji
        logAppState('Po załadowaniu nowej rundy');
        
        // Pokaż fazę wyboru
        showSelectPhase();
        
        // Aktualizuj widok statystyk
        updateStatsView();
        
        console.log(`Lewa kurtyna: ${GameState.leftAction}, Prawa kurtyna: ${GameState.rightAction}`);
        
    } catch (error) {
        console.error('Błąd podczas ładowania następnej rundy:', error);
        hideLoadingOverlay();
    }
}

// Inicjalizacja i przetwarzanie wyboru kurtyny
async function selectCurtain(side) {
    if (GameState.isWaitingForPriceChange) {
        console.warn('Już oczekujemy na zmianę ceny, ignoruję kliknięcie');
        return;
    }

    try {
        console.log(`Wybrano kurtynę: ${side}`);
        
        // Rozszerz wybraną kurtynę i ukryj drugą
        const leftCurtain = document.getElementById('left-curtain');
        const rightCurtain = document.getElementById('right-curtain');
        
        if (side === 'LEFT') {
            leftCurtain.classList.add('curtain-expanded');
            rightCurtain.classList.add('curtain-hidden');
        } else {
            rightCurtain.classList.add('curtain-expanded');
            leftCurtain.classList.add('curtain-hidden');
        }
        
        // Pobierz cenę początkową
        const startPrice = await getCurrentPrice();
        console.log(`Cena początkowa: ${startPrice}`);
        
        // Aktualizuj stan gry
        GameState.startPrice = startPrice;
        GameState.isWaitingForPriceChange = true;  // Ustawiamy flagę czekania na true
        
        // Wyślij wybór do serwera
        const response = await fetchWithAuth('/api/rounds/choice', {
            method: 'POST',
            body: JSON.stringify({
                round_id: GameState.currentRound.id,
                session_id: GameState.sessionId,
                side: side
            })
        });
        
        if (!response.ok) {
            throw new Error(`Błąd wysyłania wyboru: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('Odpowiedź z serwera po wyborze:', result);
        
        // Aktualizuj stan gry
        GameState.endPrice = result.end_price;
        GameState.isWaitingForPriceChange = false;  // Ustawiamy flagę czekania na false po otrzymaniu wyniku
        GameState.sessionProfitFactor = result.session_profit_factor;
        GameState.remainingPairs = result.remaining_pairs;
        
        if (result.result === 'SUCCESS') {
            GameState.successes++;
        } else {
            GameState.failures++;
        }
        
        // Zaloguj stan aplikacji
        logAppState(`Po rundzie - wynik: ${result.result}`);
        
        // Pokaż fazę wyniku bez opóźnienia
        await showResultPhase(result.result, result.stimulus_url);
        
        // Aktualizuj widok statystyk
        updateStatsView();
        
    } catch (error) {
        console.error('Błąd podczas przetwarzania wyboru:', error);
        GameState.isWaitingForPriceChange = false;  // Reset flagi czekania w przypadku błędu
        hideLoadingOverlay();
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