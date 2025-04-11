// Stan aplikacji dla strony podsumowania
const SummaryState = {
    sessionId: null,
    sessionData: null,
    rounds: [],
    wealthChart: null
};

// Zmienne globalne
let currentSession = null;
let sessionRounds = [];
let sessionWealthChart = null;

// Elementy DOM - z bezpiecznym pobieraniem
const sessionStatsContainer = document.getElementById('session-stats');
const sessionWealthChartContainer = document.getElementById('session-wealth-chart');
const posRankingContainer = document.getElementById('pos-ranking');
const negRankingContainer = document.getElementById('neg-ranking');
const roundsDetailsContainer = document.getElementById('rounds-details');
const roundsTable = document.getElementById('rounds-table');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingMessage = document.getElementById('loading-message');
const detailsToggleButton = document.getElementById('details-toggle-button');
const newSessionButton = document.getElementById('new-session-button');

// Pomocnicze funkcje dla bezpiecznego dostępu do DOM
function getElement(id) {
    const element = document.getElementById(id);
    return element;
}

// Pomocnicze funkcje
function showLoading(message) {
    const loadingMessage = getElement('loading-message');
    const loadingOverlay = getElement('loading-overlay');
    
    if (loadingMessage) loadingMessage.textContent = message;
    if (loadingOverlay) loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    const loadingOverlay = getElement('loading-overlay');
    if (loadingOverlay) loadingOverlay.style.display = 'none';
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

// Inicjalizacja strony podsumowania
async function initSummary() {
    showLoadingOverlay('Ładowanie podsumowania sesji...');
    
    // Pobierz ID sesji z URL
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    if (!sessionId) {
        alert('Nieprawidłowy identyfikator sesji.');
        window.location.href = '/';
        return;
    }
    
    SummaryState.sessionId = sessionId;
    
    try {
        // Pobierz dane sesji
        await loadSessionData();
        
        // Pobierz dane rund
        await loadRoundsData();
        
        // Zaktualizuj UI
        updateSummaryUI();
        
        // Generuj wykres bogactwa
        generateWealthChart();
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania podsumowania:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Ładowanie danych sesji
async function loadSessionData() {
    const response = await fetchWithAuth(`/api/sessions/${SummaryState.sessionId}/summary`);
    
    if (!response.ok) {
        throw new Error('Nie można załadować danych sesji');
    }
    
    SummaryState.sessionData = await response.json();
}

// Ładowanie danych rund
async function loadRoundsData() {
    const response = await fetchWithAuth(`/api/sessions/${SummaryState.sessionId}/rounds`);
    
    if (!response.ok) {
        throw new Error('Nie można załadować danych rund');
    }
    
    SummaryState.rounds = await response.json();
}

// Aktualizacja UI podsumowania
function updateSummaryUI() {
    const data = SummaryState.sessionData;
    
    // Aktualizacja statystyk
    document.getElementById('session-successes').textContent = data.success_count;
    document.getElementById('session-failures').textContent = data.failure_count;
    document.getElementById('session-difference').textContent = data.success_count - data.failure_count;
    
    const totalRounds = data.success_count + data.failure_count;
    const successRate = totalRounds > 0 ? Math.round((data.success_count / totalRounds) * 100) : 0;
    document.getElementById('session-success-rate').textContent = `${successRate}%`;
    
    const profit = ((data.session_profit_factor - 1) * 100).toFixed(2);
    document.getElementById('session-profit').textContent = `${profit}%`;
    
    // Aktualizacja rankingu bodźców pozytywnych
    updatePositiveRanking();
}

// Generowanie wykresu bogactwa
function generateWealthChart() {
    const rounds = SummaryState.rounds;
    
    if (!rounds || rounds.length === 0) {
        return;
    }
    
    // Przygotuj dane dla wykresu
    const labels = rounds.map((_, index) => `Runda ${index + 1}`);
    const wealthData = [];
    
    let cumulativeWealth = 1.0;
    for (const round of rounds) {
        cumulativeWealth *= (1 + round.profit_fraction);
        wealthData.push(cumulativeWealth);
    }
    
    // Przekształć na procentowy zysk
    const percentWealthData = wealthData.map(value => ((value - 1) * 100).toFixed(2));
    
    // Stwórz wykres
    const ctx = document.getElementById('wealth-chart').getContext('2d');
    
    SummaryState.wealthChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Zysk (%)',
                data: percentWealthData,
                backgroundColor: 'rgba(125, 64, 254, 0.2)',
                borderColor: 'rgba(125, 64, 254, 1)',
                borderWidth: 2,
                pointRadius: 4,
                pointBackgroundColor: 'rgba(125, 64, 254, 1)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Zysk (%)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Runda'
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Zysk: ${context.raw}%`;
                        }
                    }
                }
            }
        }
    });
}

// Aktualizacja rankingu bodźców pozytywnych
function updatePositiveRanking() {
    const rankingContainer = document.getElementById('positive-stimulus-ranking');
    rankingContainer.innerHTML = '';
    
    const positivePool = SummaryState.sessionData.pos_pool_json || [];
    
    if (positivePool.length === 0) {
        rankingContainer.innerHTML = '<p>Brak danych o bodźcach pozytywnych.</p>';
        return;
    }
    
    // Sortuj według liczby sukcesów (malejąco)
    const sortedStimuli = [...positivePool].sort((a, b) => b.successes - a.successes);
    
    // Wyświetl tylko te z conajmniej 1 sukcesem
    const successfulStimuli = sortedStimuli.filter(stimulus => stimulus.successes > 0);
    
    if (successfulStimuli.length === 0) {
        rankingContainer.innerHTML = '<p>Brak bodźców z sukcesami.</p>';
        return;
    }
    
    // Stwórz elementy rankingu
    successfulStimuli.forEach((stimulus, index) => {
        const stimulusElement = document.createElement('div');
        stimulusElement.className = 'stimulus-card';
        
        stimulusElement.innerHTML = `
            <div class="stimulus-image">
                <img src="/api/images/${stimulus.id}/thumbnail" alt="Bodziec #${stimulus.id}">
            </div>
            <div class="stimulus-details">
                <div class="stimulus-id">ID: ${stimulus.id}</div>
                <div class="stimulus-success">Sukcesy w sesji: ${stimulus.successes}</div>
                <div class="stimulus-profit">Zysk: ${(stimulus.cumulative_factor - 1) * 100} %</div>
                <div class="stimulus-origin">Pochodzenie: ${translateOrigin(stimulus.origin)}</div>
                ${stimulus.origin === 'child' && stimulus.parent ? `
                    <div class="stimulus-parent">Rodzic: #${stimulus.parent}</div>
                ` : ''}
            </div>
        `;
        
        rankingContainer.appendChild(stimulusElement);
    });
}

// Wyświetlanie szczegółów rund
function toggleRoundsDetails() {
    const detailsContainer = document.getElementById('rounds-details');
    const button = document.getElementById('show-details-button');
    
    if (detailsContainer.style.display === 'none') {
        detailsContainer.style.display = 'block';
        button.textContent = 'Ukryj szczegóły rund';
        populateRoundsDetails();
    } else {
        detailsContainer.style.display = 'none';
        button.textContent = 'Szczegółowy przebieg rund';
    }
}

// Wypełnianie tabeli z detalami rund
function populateRoundsDetails() {
    const tableBody = document.getElementById('rounds-table-body');
    tableBody.innerHTML = '';
    
    const rounds = SummaryState.rounds;
    
    if (!rounds || rounds.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="7">Brak danych o rundach.</td></tr>';
        return;
    }
    
    rounds.forEach((round, index) => {
        const row = document.createElement('tr');
        
        // Formatowanie daty
        const date = new Date(round.created_at);
        const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
        
        // Formatowanie zmiany procentowej
        const profitPercent = (round.profit_fraction * 100).toFixed(2);
        const profitSign = round.profit_fraction >= 0 ? '+' : '';
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${formattedDate}</td>
            <td>${round.pos_image_id}</td>
            <td>${round.neg_image_id}</td>
            <td>${round.user_choice_side === 'LEFT' ? 'Lewa' : 'Prawa'}</td>
            <td class="${round.profit_fraction >= 0 ? 'positive' : 'negative'}">${profitSign}${profitPercent}%</td>
            <td class="${round.result.toLowerCase()}">${round.result === 'SUCCESS' ? 'SUKCES' : 'PORAŻKA'}</td>
        `;
        
        tableBody.appendChild(row);
    });
}

// Tworzenie nowej sesji
async function createNewSession() {
    showLoadingOverlay('Generowanie nowej sesji...');
    
    try {
        const response = await fetchWithAuth('/api/sessions', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Nie można utworzyć nowej sesji');
        }
        
        const session = await response.json();
        window.location.href = `/game?session_id=${session.id}`;
    } catch (error) {
        console.error('Błąd tworzenia sesji:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Pomocnicza funkcja tłumacząca pochodzenie bodźca
function translateOrigin(origin) {
    switch (origin) {
        case 'child': return 'Potomek';
        case 'bought': return 'Kupiony';
        case 'random': return 'Losowy';
        default: return origin;
    }
}

// Sprawdzanie, czy użytkownik jest zalogowany
document.addEventListener('DOMContentLoaded', async function() {
    try {
        // Utwórz container dla statystyk puli - na początku pusty
        let statsContainer = document.createElement('div');
        statsContainer.id = 'pool-stats-container';
        statsContainer.className = 'pool-stats-box';
        statsContainer.style.display = 'none'; // Początkowe ukrycie
        
        // Znajdź przycisk nowej sesji i dodaj kontener po nim
        const newSessionButton = document.getElementById('new-session-button');
        if (newSessionButton && newSessionButton.parentNode) {
            // Dodaj spinner do przycisku aby wskazać, że oczekujemy na generowanie puli
            newSessionButton.disabled = true;
            newSessionButton.classList.add('loading');
            newSessionButton.innerHTML = '<div class="spinner"></div> Oczekiwanie na pulę...';
            
            // Dodaj kontener statystyk pod przyciskiem
            newSessionButton.parentNode.insertAdjacentElement('afterend', statsContainer);
        }
        
        console.log('Inicjalizacja strony podsumowania...');
        
        // Inicjalizacja tokenów i pobierania danych
        initializeTokenCheck();
        
        // Pobierz dane sesji z URL
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');
        
        if (sessionId) {
            // Ładowanie szczegółów sesji i inicjalizacja podsumowania
            console.log(`Pobieranie danych dla sesji ${sessionId}...`);
            await Promise.all([
                fetchSessionDetails(sessionId),
                fetchRoundsData(sessionId),
                fetchSessionImages(sessionId)
            ]);
            
            // Rozpocznij sprawdzanie dostępności puli dla nowej sesji
            console.log('Rozpoczynam sprawdzanie dostępności nowej puli...');
            checkPoolReadiness(sessionId);
        } else {
            console.error('Brak ID sesji w URL');
            alert('Brak identyfikatora sesji. Przekierowanie do strony głównej...');
            window.location.href = '/';
        }
        
        // Dodaj obsługę kliknięcia przycisku nowej sesji
        if (newSessionButton) {
            newSessionButton.addEventListener('click', startNewSession);
        }
        
    } catch (error) {
        console.error('Błąd inicjalizacji strony:', error);
        alert('Wystąpił błąd podczas ładowania strony podsumowania.');
    }
});

// Funkcja ładująca podsumowanie sesji
async function loadSessionSummary(sessionId) {
    try {
        showLoading('Ładowanie podsumowania sesji...');
        
        // Pobierz ID sesji z URL
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');
        
        if (!sessionId) {
            alert('Nieprawidłowy identyfikator sesji.');
            window.location.href = '/';
            return;
        }
        
        // Pobieranie danych sesji
        const sessionResponse = await fetch(`/api/sessions/${sessionId}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!sessionResponse.ok) {
            throw new Error('Błąd podczas pobierania danych sesji');
        }
        
        currentSession = await sessionResponse.json();
        
        // Pobieranie rund sesji
        const roundsResponse = await fetch(`/api/sessions/${sessionId}/rounds`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!roundsResponse.ok) {
            throw new Error('Błąd podczas pobierania danych rund');
        }
        
        sessionRounds = await roundsResponse.json();
        
        // Pobieranie podsumowania sesji
        const summaryResponse = await fetch(`/api/sessions/${sessionId}/summary`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!summaryResponse.ok) {
            console.error('Błąd pobierania podsumowania sesji:', await summaryResponse.text());
            
            // Kontynuuj bez podsumowania
            renderSessionStats({
                success_count: currentSession.success_count || 0,
                failure_count: currentSession.failure_count || 0,
                session_profit_factor: currentSession.session_profit_factor || 1.0,
                remaining_pairs: currentSession.remaining_pairs || 0,
            });
            renderWealthChart(sessionRounds);
            renderRoundsDetails(sessionRounds);
            
            hideLoading();
            return;
        }
        
        const sessionSummary = await summaryResponse.json();
        console.log('Podsumowanie sesji:', sessionSummary);
        
        // Sprawdź, czy sesja jest zakończona i rozpocznij generowanie nowej puli
        if (sessionSummary.status === "COMPLETED") {
            console.log("Sesja zakończona, sprawdzam/rozpoczynam generowanie nowej puli...");
            checkPoolReadiness(sessionSummary.id);
        }
        
        // Renderowanie danych
        renderSessionStats(sessionSummary);
        renderWealthChart(sessionRounds);
        
        // Renderowanie rankingów bodźców
        if (sessionSummary.pos_ranking && sessionSummary.pos_ranking.length > 0) {
            renderStimuliRanking(sessionSummary.pos_ranking, 'pos');
        } else {
            console.log('Brak danych rankingowych dla bodźców pozytywnych lub pusta lista');
            const positiveRanking = getElement('positive-stimulus-ranking');
            if (positiveRanking) {
                positiveRanking.innerHTML = '<p>Brak danych dla rankingu bodźców pozytywnych</p>';
            }
        }
        
        renderRoundsDetails(sessionRounds);
        
        hideLoading();
    } catch (error) {
        console.error('Błąd ładowania podsumowania sesji:', error);
        hideLoading();
        alert('Wystąpił błąd podczas ładowania podsumowania sesji. Spróbuj ponownie.');
    }
}

// Funkcja renderująca statystyki sesji
function renderSessionStats(summary) {
    // Bezpieczne pobieranie elementów
    const sessionSuccesses = getElement('session-successes');
    const sessionFailures = getElement('session-failures');
    const sessionDifference = getElement('session-difference');
    const sessionSuccessRate = getElement('session-success-rate');
    const sessionProfit = getElement('session-profit');
    
    // Sprawdzamy dostępność każdego elementu przed aktualizacją
    const successCount = summary.success_count || 0;
    const failureCount = summary.failure_count || 0;
    
    if (sessionSuccesses) sessionSuccesses.textContent = successCount;
    if (sessionFailures) sessionFailures.textContent = failureCount;
    if (sessionDifference) sessionDifference.textContent = successCount - failureCount;
    
    const totalRounds = successCount + failureCount;
    const successRate = totalRounds > 0 ? Math.round((successCount / totalRounds) * 100) : 0;
    if (sessionSuccessRate) sessionSuccessRate.textContent = `${successRate}%`;
    
    const profit = ((summary.session_profit_factor - 1) * 100).toFixed(2);
    if (sessionProfit) sessionProfit.textContent = `${profit}%`;
}

// Funkcja renderująca wykres bogactwa
function renderWealthChart(rounds) {
    const ctx = getElement('wealth-chart');
    
    if (!ctx) {
        console.error('Nie znaleziono elementu dla wykresu bogactwa');
        return;
    }

    // Przygotowanie danych
    // Dodajemy rundę "zerową", od której startujemy
    const labels = ['Runda 0', ...rounds.map((_, index) => `Runda ${index + 1}`)];
    const wealthData = [0]; // Zaczynamy od 0% (początkowy stan)
    let cumulativeWealth = 1.0; // Zaczynamy od 1.0 (100%)
    
    for (const round of rounds) {
        if (round.profit_fraction !== undefined && round.profit_fraction !== null) {
            cumulativeWealth *= (1 + round.profit_fraction);
        }
        wealthData.push((cumulativeWealth - 1) * 100); // Konwersja na procenty
    }
    
    // Tworzenie wykresu za pomocą Chart.js
    if (sessionWealthChart) {
        sessionWealthChart.destroy();
    }
    
    try {
        sessionWealthChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Skumulowany zysk (%)',
                    data: wealthData,
                    borderColor: '#7D40FE',
                    backgroundColor: 'rgba(125, 64, 254, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.2
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#CCCCCC'
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#CCCCCC',
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#FFFFFF'
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                return `Zysk: ${context.raw.toFixed(2)}%`;
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Błąd przy tworzeniu wykresu:', error);
    }
}

// Funkcja renderująca ranking bodźców
function renderStimuliRanking(ranking, type) {
    if (type !== 'pos') {
        console.log(`Ranking bodźców typu ${type} pominięty - obsługiwane są tylko bodźce pozytywne`);
        return;
    }

    const container = getElement('positive-stimulus-ranking');
    if (!container) {
        console.error('Nie znaleziono kontenera dla rankingu bodźców pozytywnych');
        return;
    }

    if (!ranking || ranking.length === 0) {
        container.innerHTML = '<p>Brak danych dla rankingu bodźców pozytywnych</p>';
        return;
    }

    const successfulStimuli = ranking.filter(stimulus => stimulus.successes > 0);

    if (successfulStimuli.length === 0) {
        container.innerHTML = '<p>Brak bodźców z sukcesami w tej sesji</p>';
        return;
    }

    const sortedStimuli = [...successfulStimuli].sort((a, b) => {
        if (a.successes !== b.successes) {
            return b.successes - a.successes;
        } else {
            return (b.cumulative_factor - 1) - (a.cumulative_factor - 1);
        }
    });

    let html = '';

    sortedStimuli.forEach((stimulus, index) => {
        const profit = ((stimulus.cumulative_factor - 1) * 100).toFixed(2);

        // Obsługa pola origin
        let originLabel = 'Losowy';
        if (stimulus.origin.startsWith('child_of_')) {
            if (stimulus.origin.includes('_noise_')) {
                originLabel = 'Szum potomny';
            } else {
                originLabel = 'Potomek';
            }
        } else if (stimulus.origin === 'bought') {
            originLabel = 'Kupiony';
        }

        html += `
            <div class="stimulus-card">
                <div class="stimulus-image">
                    <img src="/api/images/${stimulus.id}/thumbnail" alt="Bodziec #${stimulus.id}">
                </div>
                <div class="stimulus-details">
                    <div class="stimulus-id">ID: ${stimulus.id}</div>
                    <div class="stimulus-success">Sukcesów w sesji: ${stimulus.successes}</div>
                    <div class="stimulus-failure">Porażki w sesji: ${stimulus.failures}</div>
                    <div class="stimulus-profit">Zysk: ${profit}%</div>
                    <div>Pochodzenie: ${originLabel}</div>
                    ${stimulus.origin === 'child' && stimulus.parent ? `
                        <div class="stimulus-parent">Rodzic: #${stimulus.parent}</div>
                    ` : ''}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    console.log(`Wyrenderowano ranking bodźców pozytywnych z ${sortedStimuli.length} elementami`);
}


// Funkcja renderująca szczegóły rund
function renderRoundsDetails(rounds) {
    const roundsTableBody = getElement('rounds-table-body');
    
    if (!roundsTableBody) {
        console.error('Nie znaleziono tabeli z detalami rund');
        return;
    }
    
    if (!rounds || rounds.length === 0) {
        roundsTableBody.innerHTML = '<tr><td colspan="7">Brak danych o rundach</td></tr>';
        return;
    }
    
    // Przygotowanie HTML
    let html = '';
    
    rounds.forEach((round, index) => {
        const dateTime = new Date(round.created_at).toLocaleString();
        const priceChange = round.profit_fraction ? (round.profit_fraction * 100).toFixed(2) : '0.00';
        const profit = round.profit_fraction ? (round.profit_fraction * 100).toFixed(2) : '0.00';
        
        html += `
            <tr>
                <td>${index + 1}</td>
                <td>${dateTime}</td>
                <td>${round.pos_image_id || 'N/A'}</td>
                <td>${round.neg_image_id || 'N/A'}</td>
                <td>${round.user_choice_side === 'LEFT' ? 'Lewa' : 'Prawa'}</td>
                <td>${priceChange > 0 ? '+' : ''}${priceChange}%</td>
                <td class="${round.result === 'SUCCESS' ? 'success' : 'failure'}">${round.result === 'SUCCESS' ? 'SUKCES' : 'PORAŻKA'}</td>
            </tr>
        `;
    });
    
    roundsTableBody.innerHTML = html;
}

// Funkcja przełączająca widoczność szczegółów rund
function toggleRoundsDetails() {
    const detailsContainer = document.getElementById('rounds-details');
    const button = document.getElementById('show-details-button');
    
    if (!detailsContainer || !button) {
        console.error('Nie znaleziono elementów do przełączania widoku szczegółów');
        return;
    }
    
    if (detailsContainer.style.display === 'none' || !detailsContainer.style.display) {
        detailsContainer.style.display = 'block';
        button.textContent = 'Ukryj szczegółowy przebieg rund';
    } else {
        detailsContainer.style.display = 'none';
        button.textContent = 'Pokaż szczegółowy przebieg rund';
    }
}

// Funkcja rozpoczynająca nową sesję
async function startNewSession() {
    console.log('Rozpoczynanie nowej sesji...');
    try {
        const newSessionButton = document.getElementById('new-session-button');
        if (!newSessionButton) return;
        
        // Pokaż spinner tylko na przycisku
        newSessionButton.disabled = true;
        newSessionButton.classList.add('loading');
        newSessionButton.innerHTML = '<div class="spinner"></div> Rozpoczynanie sesji...';
        
        // Sprawdzenie tokenu
        const token = localStorage.getItem('token');
        if (!token) {
            console.error('Brak tokenu autoryzacji. Przekierowanie do logowania.');
            window.location.href = '/';
            return;
        }
        
        // Wywołanie endpointu sessions, który powinien znaleźć sesję PENDING i ją aktywować
        // lub utworzyć nową sesję, jeśli nie ma PENDING
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})  // Pusty obiekt - backend znajdzie istniejącą sesję PENDING
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`Błąd rozpoczęcia sesji: ${errorData.detail || 'Nieznany błąd'}`);
        }
        
        const data = await response.json();
        console.log('Odpowiedź z serwera:', data);
        
        // Sprawdź czy mamy ID sesji w odpowiedzi
        if (data.session_id) {
            // Przekierowanie do strony gry z sesją
            window.location.href = `/game?session_id=${data.session_id}`;
        } else {
            throw new Error('Brak identyfikatora sesji w odpowiedzi');
        }
    } catch (error) {
        console.error('Błąd podczas rozpoczynania sesji:', error);
        
        // Przywróć oryginalny wygląd przycisku
        const newSessionButton = document.getElementById('new-session-button');
        if (newSessionButton) {
            newSessionButton.disabled = false;
            newSessionButton.classList.remove('loading');
            newSessionButton.innerHTML = 'Nowa sesja';
        }
        
        alert('Wystąpił błąd podczas rozpoczynania sesji. Spróbuj ponownie.');
    }
}

// Zmienna stanu do kontrolowania sprawdzania puli
let isCheckingPool = false;

// Funkcja sprawdzająca czy nowa pula jest gotowa
async function checkPoolReadiness(sessionId, retryCount = 0) {
    // Jeśli sprawdzanie jest już zatrzymane, zwracamy false
    if (!isCheckingPool) {
        return false;
    }

    if (retryCount >= 30) {  // 30 prób * 2 sekundy = 1 minuta
        console.log('Maksymalna liczba prób sprawdzenia gotowości puli osiągnięta');
        isCheckingPool = false;
        return false;
    }

    try {
        console.log(`Sprawdzam gotowość puli dla sesji ${sessionId}, próba: ${retryCount}`);
        const response = await fetchWithAuth(`/api/sessions/${sessionId}/pool-info`);
        const data = await response.json();

        if (data && data.has_pending_session) {
            console.log('Sesja PENDING istnieje');
            if (data.has_generated_pools) {
                console.log('Pula jest gotowa!');
                // Wyświetl statystyki nowej puli
                await displayPoolStatistics(sessionId);
                // Zatrzymujemy sprawdzanie po znalezieniu gotowej puli
                isCheckingPool = false;
                return true;
            }
            console.log('Pula nie jest jeszcze wygenerowana, sprawdzam ponownie za 2 sekundy...');
            await new Promise(resolve => setTimeout(resolve, 2000));
            return await checkPoolReadiness(sessionId, retryCount + 1);
        }

        // Nie ma jeszcze sesji PENDING - sprawdzamy ponownie za 2 sekundy
        console.log('Brak sesji PENDING - sprawdzam ponownie za 2 sekundy...');
        await new Promise(resolve => setTimeout(resolve, 2000));
        return await checkPoolReadiness(sessionId, retryCount + 1);
    } catch (error) {
        console.error('Błąd podczas sprawdzania gotowości puli:', error);
        isCheckingPool = false;
        return false;
    }
}

// Funkcja wywołująca trigger_pool_generation
async function triggerPoolGeneration(sessionId) {
    try {
        console.log('Rozpoczynam generowanie nowej puli...');
        isCheckingPool = true;  // Rozpoczynamy sprawdzanie
        
        const response = await fetchWithAuth(`/api/sessions/${sessionId}/trigger-pool-generation`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`Błąd wywołania trigger_pool_generation: ${response.status}`);
        }
        
        console.log('Pomyślnie wywołano trigger_pool_generation');
        
        // Sprawdź gotowość puli asynchronicznie
        await checkPoolReadiness(sessionId);
        
        // Sprawdzanie powinno być zatrzymane po znalezieniu gotowej puli lub po przekroczeniu limitu czasu
    } catch (error) {
        console.error('Błąd podczas wywoływania trigger_pool_generation:', error);
        alert('Wystąpił błąd podczas generowania puli. Spróbuj ponownie.');
        isCheckingPool = false;  // Zatrzymujemy sprawdzanie przy błędzie
    }
}

// Funkcja wyświetlająca statystyki nowej puli
async function displayPoolStatistics(sessionId) {
    try {
        console.log('Pobieram statystyki nowej puli...');
        const response = await fetchWithAuth(`/api/sessions/${sessionId}/pool-info`);
        const data = await response.json();

        if (data && data.pool_stats) {
            console.log('Wyświetlam statystyki nowej puli');
            
            // Wyświetl statystyki w UI
            const statsContainer = document.createElement('div');
            statsContainer.id = 'pool-stats-container';
            statsContainer.className = 'pool-stats-box';
            
            // Usuń poprzedni container statystyk, jeśli istnieje
            const existingContainer = document.getElementById('pool-stats-container');
            if (existingContainer) {
                existingContainer.remove();
            }
            
            // Używamy danych z pool_stats
            const posStats = data.pool_stats.pos_pool;
            const negStats = data.pool_stats.neg_pool;
            
            const statsHTML = `
                <div class="pool-stats-info">
                    <h3>Statystyki Nowej Puli</h3>
                    <p>Algorytm genetyczny wygenerował nową pulę obrazów</p>
                </div>
                <table class="pool-stats-table">
                    <tr>
                        <th></th>
                        <th>Bodźce pozytywne (${posStats.total})</th>
                        <th>Bodźce negatywne (${negStats.total})</th>
                    </tr>
                    <tr>
                        <th>Kupione</th>
                        <td>${posStats.bought}</td>
                        <td>${negStats.bought}</td>
                    </tr>
                    <tr>
                        <th>Wygenerowane</th>
                        <td>${posStats.children}</td>
                        <td>${negStats.children}</td>
                    </tr>
                    <tr>
                        <th>Losowe</th>
                        <td>${posStats.random}</td>
                        <td>${negStats.random}</td>
                    </tr>
                    <tr>
                        <th>Losowe (fallback)</th>
                        <td>${posStats.random_fallback}</td>
                        <td>${negStats.random_fallback}</td>
                    </tr>
                </table>
            `;
            
            statsContainer.innerHTML = statsHTML;
            document.getElementById('summary-content').appendChild(statsContainer);

            // Aktywacja przycisku "Nowa sesja"
            const newSessionButton = document.getElementById('new-session-button');
            if (newSessionButton) {
                newSessionButton.disabled = false;
                newSessionButton.classList.remove('loading');
                newSessionButton.innerHTML = 'Nowa sesja';
            }
        }
    } catch (error) {
        console.error('Błąd podczas wyświetlania statystyk puli:', error);
    }
}

// Funkcja do ładowania podsumowania sesji
async function fetchSessionDetails(sessionId) {
    try {
        console.log(`Pobieranie szczegółów sesji ${sessionId}...`);
        // Pobierz szczegóły sesji z API
        await loadSessionSummary(sessionId);
        
        // Inicjalizacja przycisków
        const detailsToggleButton = getElement('show-details-button');
        if (detailsToggleButton) {
            detailsToggleButton.addEventListener('click', toggleRoundsDetails);
            console.log('Dodano obsługę przycisku przełączania szczegółów');
        } else {
            console.warn('Nie znaleziono przycisku przełączania szczegółów');
        }
    } catch (error) {
        console.error('Błąd podczas pobierania szczegółów sesji:', error);
    }
}

// Funkcja do pobierania danych rund
async function fetchRoundsData(sessionId) {
    try {
        console.log(`Pobieranie danych rund dla sesji ${sessionId}...`);
        // Ta funkcja może być pusta, jeśli loadSessionSummary już pobiera rundy
        // lub możesz tu dodać własną logikę pobierania danych rund
    } catch (error) {
        console.error('Błąd podczas pobierania danych rund:', error);
    }
}

// Funkcja do pobierania obrazów sesji
async function fetchSessionImages(sessionId) {
    try {
        console.log(`Pobieranie obrazów dla sesji ${sessionId}...`);
        // Ta funkcja może być pusta, jeśli loadSessionSummary już pobiera obrazy
        // lub możesz tu dodać własną logikę pobierania obrazów
    } catch (error) {
        console.error('Błąd podczas pobierania obrazów:', error);
    }
}

// Funkcja inicjalizująca sprawdzanie tokenu
function initializeTokenCheck() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // Aktualizacja nazwy użytkownika w navbar
    const usernameDisplay = getElement('username-display');
    const username = localStorage.getItem('username');
    if (usernameDisplay && username) {
        usernameDisplay.textContent = `Witaj, ${username}`;
    }

    // Obsługa wylogowania
    const logoutButton = getElement('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            localStorage.removeItem('token');
            localStorage.removeItem('username');
            window.location.href = '/';
        });
    }

    // Wywołaj trigger_pool_generation po załadowaniu strony
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    if (sessionId) {
        triggerPoolGeneration(sessionId);
    }
}