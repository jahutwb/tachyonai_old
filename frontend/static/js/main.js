// Główny plik JavaScript dla aplikacji TachyonAI

// Obiekt zarządzający stanem aplikacji
const AppState = {
    currentSessionId: null,
    remainingPairs: 0,
    currentRound: null,
    startPrice: 0,
    sessionProfitFactor: 1.0,
    successes: 0,
    failures: 0
};

// Obsługa przycisku "Rozpocznij grę"
document.addEventListener('DOMContentLoaded', () => {
    const startGameButton = document.getElementById('start-game-button');
    if (startGameButton) {
        startGameButton.addEventListener('click', startGame);
    }
});

// Funkcja do rozpoczęcia gry
async function startGame() {
    // Debugowanie: sprawdź token przed wysłaniem żądania
    const token = getToken();
    console.log('Token przed utworzeniem sesji:', token ? 'token istnieje' : 'brak tokenu');
    
    // Sprawdź ważność tokenu przed rozpoczęciem
    if (!await verifyToken()) {
        console.log('Token jest nieważny lub wygasł - przekierowuję do logowania');
        await refreshToken();
        return;
    }
    
    // Pokaż overlay ładowania
    showLoadingOverlay('Tworzenie nowej sesji...');

    try {
        // Utwórz lub wznów sesję
        console.log('Wysyłanie żądania POST do /api/sessions z tokenem w nagłówku');
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        });

        console.log('Otrzymana odpowiedź:', response.status, response.statusText);
        
        if (!response.ok) {
            const errorData = await response.json();
            console.error('Szczegóły błędu z serwera:', errorData);
            throw new Error(errorData.detail || 'Błąd tworzenia sesji');
        }

        const sessionData = await response.json();
        console.log('Dane sesji:', sessionData);
        AppState.currentSessionId = sessionData.id;
        AppState.remainingPairs = sessionData.remaining_pairs;
        AppState.sessionProfitFactor = sessionData.session_profit_factor;

        // Przejdź do ekranu gry
        window.location.href = `/game?session_id=${sessionData.id}`;
    } catch (error) {
        console.error('Błąd rozpoczęcia gry:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();

        // Dodatkowe debugowanie: sprawdź, czy token nie wygasł próbując pobrać profil użytkownika
        try {
            console.log('Weryfikacja tokenu przez żądanie GET do /users/me');
            const userResponse = await fetch('/users/me', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (userResponse.ok) {
                console.log('Token działa poprawnie - możliwy inny problem z sesją');
                const userData = await userResponse.json();
                console.log('Dane użytkownika:', userData);
            } else {
                console.error('Token może być nieprawidłowy:', userResponse.status);
                // Token wygasł lub jest nieprawidłowy - sugeruj ponowne zalogowanie
                logout();
                alert('Twoja sesja wygasła. Zaloguj się ponownie, aby kontynuować.');
                window.location.href = '/login';
            }
        } catch (userError) {
            console.error('Błąd weryfikacji tokenu:', userError);
        }
    }
}

// Funkcje pomocnicze do zarządzania overlayem ładowania
function showLoadingOverlay(message = 'Ładowanie...') {
    const overlay = document.getElementById('loading-overlay');
    const messageElement = document.getElementById('loading-message');
    if (messageElement) {
        messageElement.textContent = message;
    }
    if (overlay) {
        overlay.style.display = 'flex';
    }
}

function hideLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

// Funkcje pomocnicze do zapytań API z tokenem JWT
async function fetchWithAuth(url, options = {}) {
    const token = getToken();
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };

    const response = await fetch(url, {
        ...options,
        headers
    });

    if (!response.ok) {
        // Jeśli token wygasł (401), wyloguj użytkownika
        if (response.status === 401) {
            logout();
            window.location.href = '/';
            throw new Error('Sesja wygasła. Zaloguj się ponownie.');
        }
        
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Błąd zapytania');
    }

    return response;
}

// Funkcja do obsługi następnej rundy (będzie rozbudowana w przyszłości)
async function loadNextRound() {
    if (AppState.remainingPairs <= 0) {
        window.location.href = `/summary?session_id=${AppState.currentSessionId}`;
        return;
    }

    showLoadingOverlay('Przygotowanie następnej rundy...');

    try {
        const response = await fetchWithAuth(`/api/rounds/next?session_id=${AppState.currentSessionId}`);
        const roundData = await response.json();
        
        AppState.currentRound = roundData;
        
        // Tutaj będzie kod do renderowania kurtyn
        // ...

        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania rundy:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Funkcja do obsługi wyboru kurtyny (będzie rozbudowana w przyszłości)
async function selectCurtain(side) {
    showLoadingOverlay('Przetwarzanie wyboru...');

    try {
        const response = await fetchWithAuth(`/api/rounds/choice`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: AppState.currentSessionId,
                round_id: AppState.currentRound.id,
                side: side
            })
        });

        const resultData = await response.json();
        
        // Tutaj będzie kod do pokazania wyniku
        // ...

        // Aktualizacja statystyk
        AppState.startPrice = resultData.start_price;
        AppState.remainingPairs = resultData.remaining_pairs;
        AppState.sessionProfitFactor = resultData.session_profit_factor;
        
        if (resultData.result === 'SUCCESS') {
            AppState.successes++;
        } else {
            AppState.failures++;
        }

        // Aktualizacja widoku statystyk
        updateStatsView();

        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd wyboru:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Funkcja do aktualizacji widoku statystyk (będzie rozbudowana w przyszłości)
function updateStatsView() {
    // Kod do aktualizacji widoku statystyk w pasku dolnym
    // ...
}

// Exportowanie funkcji, które będą używane w innych plikach
window.AppState = AppState;
window.startGame = startGame;
window.loadNextRound = loadNextRound;
window.selectCurtain = selectCurtain;