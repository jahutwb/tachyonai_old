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
        // Ukryj fazę wyboru i pokaż fazę wyniku
        document.getElementById('game-phase-select').style.display = 'none';
        document.getElementById('game-phase-result').style.display = 'block';
        
        // Pobierz elementy DOM
        let resultMessage = document.getElementById('result-status');
        let changePercentage = document.getElementById('profit-change');
        const stimulusImage = document.getElementById('stimulus-image');
        
        // Sprawdź, czy elementy istnieją
        if (!resultMessage) {
            console.error('Element #result-status nie istnieje w DOM');
            // Tworzymy element, jeśli nie istnieje
            const newResultMessage = document.createElement('div');
            newResultMessage.id = 'result-status';
            newResultMessage.className = 'result-status';
            document.querySelector('.result-info').appendChild(newResultMessage);
            // Przypisujemy do zmiennej lokalnej
            resultMessage = newResultMessage;
        }
        
        if (!changePercentage) {
            console.error('Element #profit-change nie istnieje w DOM');
            // Tworzymy element, jeśli nie istnieje
            const newChangePercentage = document.createElement('div');
            newChangePercentage.id = 'profit-change';
            newChangePercentage.className = 'profit-change';
            document.querySelector('.result-info').appendChild(newChangePercentage);
            // Przypisujemy do zmiennej lokalnej
            changePercentage = newChangePercentage;
        }
        
        // Ustawienie komunikatu i klasy dla wyniku
        if (result === 'SUCCESS') {
            resultMessage.textContent = 'SUKCES!';
            resultMessage.className = 'result-status success-result';
        } else {
            resultMessage.textContent = 'PORAŻKA!';
            resultMessage.className = 'result-status failure-result';
        }
        
        // Obliczenie i wyświetlenie procentowej zmiany ceny
        const startPrice = GameState.startPrice;
        const endPrice = GameState.endPrice;
        const percentChange = ((endPrice - startPrice) / startPrice) * 100;
        changePercentage.textContent = `Zmiana ceny: ${percentChange.toFixed(2)}%`;
        
        // Wyświetlenie bodźca, jeśli URL jest dostępny
        if (stimulusUrl && stimulusImage) {
            stimulusImage.style.display = 'block';
            stimulusImage.src = stimulusUrl;
            stimulusImage.onerror = function() {
                console.error('Błąd ładowania obrazu bodźca');
                stimulusImage.alt = 'Błąd ładowania obrazu';
                stimulusImage.style.display = 'none';
            };
            stimulusImage.onload = function() {
                console.log('Obraz bodźca załadowany pomyślnie');
            };
        } else {
            console.log('Brak URL bodźca lub elementu obrazu');
            if (stimulusImage) {
                stimulusImage.style.display = 'none';
            }
        }
        
        // Aktualizacja przycisków na podstawie pozostałych par
        if (GameState.remainingPairs <= 0) {
            console.log('Brak pozostałych par - pokazuję przycisk podsumowania');
            document.getElementById('next-round-button').style.display = 'none';
            document.getElementById('summary-button').style.display = 'inline-block';
        } else {
            console.log(`Pozostało par: ${GameState.remainingPairs} - wyświetlam przycisk następnej rundy`);
            document.getElementById('next-round-button').style.display = 'inline-block';
            document.getElementById('summary-button').style.display = 'none';
        }
    } catch (error) {
        console.error('Błąd wyświetlania fazy wynikowej:', error);
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

// Funkcja do obsługi wyboru kurtyny
async function selectCurtain(side) {
    console.log('====== START selectCurtain ======');
    console.log(`Wybrano kurtynę: ${side}, isWaitingForPriceChange: ${GameState.isWaitingForPriceChange}`);
    
    if (GameState.isWaitingForPriceChange) {
        console.warn('Już oczekujemy na zmianę ceny, ignoruję kliknięcie');
        return;
    }

    // Natychmiastowe ustawienie flagi na początku funkcji - blokuje wielokrotne kliknięcia
    GameState.isWaitingForPriceChange = true;
    console.log(`Flaga isWaitingForPriceChange ustawiona na: ${GameState.isWaitingForPriceChange}`);
    
    try {
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
        
        console.log('KROK 1: Pobieranie aktualnej ceny');
        // Pobierz aktualną cenę i wyślij wybór
        const currentPrice = await getCurrentPrice();
        console.log(`KROK 1 zakończony: Cena początkowa: ${currentPrice}`);
        
        // Zapisz cenę początkową
        GameState.startPrice = currentPrice;
        
        // Przygotuj dane do wysłania
        const data = {
            session_id: GameState.sessionId,
            round_id: GameState.currentRound.id,
            side: side
        };
        
        console.log('KROK 2: Wysyłanie wyboru do backendu', data);
        try {
            // Wyślij wybór do backendu
            const response = await fetchWithAuth('/api/rounds/choice', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            
            console.log(`KROK 2 zakończony: Status odpowiedzi: ${response.status}`);
            
            if (!response.ok) {
                throw new Error(`Błąd odpowiedzi serwera: ${response.status} ${response.statusText}`);
            }
            
            console.log('KROK 3: Parsowanie JSON z odpowiedzi');
            const result = await response.json();
            console.log('KROK 3 zakończony: Odpowiedź z backendu:', result);
            
            // Logowanie pełnej odpowiedzi dla zrozumienia jej struktury
            console.log('Pełna odpowiedź serwera (stringify):', JSON.stringify(result, null, 2));
            
            // Sprawdzenie czy odpowiedź zawiera oczekiwane pola
            console.log('Odpowiedź zawiera pole result:', result.hasOwnProperty('result'));
            console.log('Odpowiedź zawiera pole remaining_pairs:', result.hasOwnProperty('remaining_pairs'));
            console.log('Odpowiedź zawiera pole session_status:', result.hasOwnProperty('session_status'));
            
            console.log('KROK 4: Aktualizacja stanu gry');
            // Aktualizacja stanu gry o wynik
            GameState.endPrice = result.end_price || GameState.startPrice;
            GameState.remainingPairs = result.remaining_pairs !== undefined ? result.remaining_pairs : GameState.remainingPairs;
            GameState.sessionProfitFactor = result.session_profit_factor || GameState.sessionProfitFactor;
            
            if (result.result === 'SUCCESS') {
                GameState.successes++;
                console.log(`Sukces! Liczba sukcesów: ${GameState.successes}`);
            } else {
                GameState.failures++;
                console.log(`Porażka! Liczba porażek: ${GameState.failures}`);
            }
            
            // WAŻNE: Zawsze resetujemy flagę czekania przed pokazaniem wyniku
            console.log('KROK 5: Resetowanie flagi isWaitingForPriceChange');
            GameState.isWaitingForPriceChange = false;
            console.log(`Flaga isWaitingForPriceChange zresetowana na: ${GameState.isWaitingForPriceChange}`);
            
            console.log('KROK 6: Pokazywanie fazy wyniku');
            // Pokaż fazę wyniku
            await showResultPhase(result.result, result.stimulus_url);
            console.log('KROK 6 zakończony: Faza wyniku pokazana');
            
            console.log('KROK 7: Aktualizacja widoku statystyk');
            // Aktualizuj widok statystyk
            updateStatsView();
            
            // Logowanie stanu aplikacji po rundzie
            logAppState(`Po rundzie - wynik: ${result.result}`);
            
            console.log('KROK 8: Sprawdzanie statusu sesji');
            // Sprawdź status sesji i pozostałe pary
            console.log(`Status sesji: ${result.session_status}, Pozostałe pary: ${GameState.remainingPairs}`);
            
            // Dodatkowa weryfikacja dla zakończenia sesji
            const isSessionCompleted = (
                result.session_status === 'COMPLETED' || 
                result.remaining_pairs === 0 || 
                GameState.remainingPairs <= 0
            );
            
            console.log(`Czy sesja zakończona: ${isSessionCompleted}`);
            
            if (isSessionCompleted) {
                console.log('Sesja zakończona - pokazuję przycisk podsumowania');
                document.getElementById('next-round-button').style.display = 'none';
                document.getElementById('summary-button').style.display = 'inline-block';
            } else {
                console.log(`Pozostało par: ${GameState.remainingPairs} - pokazuję przycisk następnej rundy`);
                document.getElementById('next-round-button').style.display = 'inline-block';
                document.getElementById('summary-button').style.display = 'none';
            }
            
            console.log('KROK 8 zakończony: Przyciski zaktualizowane');
            
        } catch (apiError) {
            console.error('BŁĄD w komunikacji z API:', apiError);
            // BARDZO WAŻNE: Resetujemy flagę czekania w przypadku błędu API
            GameState.isWaitingForPriceChange = false;
            console.log(`Flaga isWaitingForPriceChange zresetowana po błędzie API: ${GameState.isWaitingForPriceChange}`);
            throw apiError;
        }
        
    } catch (error) {
        console.error('Nieobsłużony błąd podczas przetwarzania wyboru:', error);
        console.error('Pełny stack trace błędu:', error.stack);
        
        // BARDZO WAŻNE: Zawsze resetujemy flagę czekania w przypadku błędu
        GameState.isWaitingForPriceChange = false;
        console.log(`Flaga isWaitingForPriceChange zresetowana po błędzie: ${GameState.isWaitingForPriceChange}`);
        
    } finally {
        // EKSTRA ZABEZPIECZENIE: Ostateczne sprawdzenie i reset flagi
        if (GameState.isWaitingForPriceChange) {
            console.log('UWAGA: Flaga isWaitingForPriceChange nadal ustawiona w bloku finally - resetuję');
            GameState.isWaitingForPriceChange = false;
        }
        
        // Zawsze ukrywamy overlay ładowania
        hideLoadingOverlay();
        console.log('====== KONIEC selectCurtain ======');
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