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
    
    const positivePool = SummaryState.sessionData.positive_stimuli || [];
    
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
        stimulusElement.className = 'stimulus-rank-item';
        
        stimulusElement.innerHTML = `
            <div class="stimulus-rank-number">${index + 1}</div>
            <div class="stimulus-rank-image">
                <img src="/api/images/${stimulus.id}/thumbnail" alt="Bodziec #${stimulus.id}">
            </div>
            <div class="stimulus-rank-details">
                <div class="stimulus-id">ID: ${stimulus.id}</div>
                <div class="stimulus-success-count">Sukcesów: ${stimulus.successes}</div>
                <div class="stimulus-origin">Pochodzenie: ${translateOrigin(stimulus.origin)}</div>
            </div>
        `;
        
        if (stimulus.origin === 'child' && stimulus.parent) {
            const parentLink = document.createElement('div');
            parentLink.className = 'stimulus-parent-link';
            parentLink.innerHTML = `Rodzic: #${stimulus.parent}`;
            parentLink.addEventListener('click', () => {
                // Tutaj można by dodać akcję pokazującą obrazek rodzica
                alert(`Obrazek rodzica #${stimulus.parent}`);
            });
            
            stimulusElement.querySelector('.stimulus-rank-details').appendChild(parentLink);
        }
        
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
    const tableBody = document.getElementById('rounds-details-body');
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
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Inicjalizacja strony podsumowania...');
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

    // Pobierz ID sesji z URL
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');

    if (!sessionId) {
        alert('Brak identyfikatora sesji. Przekierowanie do strony głównej.');
        window.location.href = '/';
        return;
    }

    // Inicjalizacja podsumowania
    await loadSessionSummary(sessionId);

    // Obsługa przycisków
    const detailsToggleButton = getElement('show-details-button');
    if (detailsToggleButton) {
        detailsToggleButton.addEventListener('click', toggleRoundsDetails);
        console.log('Dodano obsługę przycisku przełączania szczegółów');
    } else {
        console.warn('Nie znaleziono przycisku przełączania szczegółów');
    }
    
    const newSessionButton = getElement('new-session-button');
    console.log('Znaleziony przycisk nowej sesji:', newSessionButton);
    if (newSessionButton) {
        newSessionButton.addEventListener('click', startNewSession);
        console.log('Dodano obsługę przycisku nowej sesji');
    } else {
        console.warn('Nie znaleziono przycisku nowej sesji');
    }
});

// Funkcja ładująca podsumowanie sesji
async function loadSessionSummary(sessionId) {
    try {
        showLoading('Ładowanie podsumowania sesji...');
        
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
    // Funkcja obsługuje tylko bodźce pozytywne
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
    
    // Filtruj tylko bodźce z successes > 0 (zgodnie z wymaganiami)
    const successfulStimuli = ranking.filter(stimulus => stimulus.successes > 0);
    
    if (successfulStimuli.length === 0) {
        container.innerHTML = '<p>Brak bodźców z sukcesami w tej sesji</p>';
        return;
    }
    
    // Sortuj najpierw po liczbie sukcesów (malejąco), potem po zysku (cumulative_factor - 1) malejąco
    const sortedStimuli = [...successfulStimuli].sort((a, b) => {
        if (a.successes !== b.successes) {
            return b.successes - a.successes; // Najpierw po liczbie sukcesów malejąco
        } else {
            // Przy remisie po (cumulative_factor - 1) malejąco
            return (b.cumulative_factor - 1) - (a.cumulative_factor - 1);
        }
    });
    
    // Przygotowanie HTML
    let html = '';
    
    sortedStimuli.forEach((stimulus, index) => {
        const profit = ((stimulus.cumulative_factor - 1) * 100).toFixed(2);
        
        html += `
            <div class="stimulus-card">
                <div class="stimulus-image">
                    <img src="/api/images/${stimulus.id}/thumbnail" alt="Bodziec #${stimulus.id}">
                </div>
                <div class="stimulus-details">
                    <div class="stimulus-id">ID: ${stimulus.id}</div>
                    <div class="stimulus-success">Sukcesy w sesji: ${stimulus.successes || 0}</div>
                    <div class="stimulus-failure">Porażki w sesji: ${stimulus.failures || 0}</div>
                    <div>Pochodzenie: ${
                        stimulus.origin === 'child' ? 'Dziecko' : 
                        stimulus.origin === 'bought' ? 'Kupiony' : 'Losowy'
                    }</div>
                    <div class="stimulus-profit">Zysk: ${profit}%</div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    console.log(`Wyrenderowano ranking bodźców pozytywnych z ${sortedStimuli.length} elementami`);
}

// Funkcja renderująca szczegóły rund
function renderRoundsDetails(rounds) {
    const roundsTableBody = getElement('rounds-details-body');
    
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
    const detailsContainer = getElement('rounds-details');
    const button = getElement('show-details-button');
    
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
        // Pokaż stan ładowania na przycisku
        const newSessionButton = document.getElementById('new-session-button');
        if (newSessionButton) {
            newSessionButton.disabled = true;
            newSessionButton.classList.add('loading');
            newSessionButton.innerHTML = '<div class="spinner"></div> Generowanie puli...';
        }
        
        showLoading('Tworzenie nowej sesji...');
        
        // Sprawdzenie tokenu i dodanie logów diagnostycznych
        const token = localStorage.getItem('token');
        if (!token) {
            console.error('Brak tokenu autoryzacji. Przekierowanie do logowania.');
            window.location.href = '/';
            return;
        }
        console.log('Token autoryzacji znaleziony, długość:', token.length);
        
        // Sprawdzenie czy najpierw trzeba wygenerować nową pulę
        console.log('Sprawdzam czy mamy aktualną sesję do wykorzystania...');
        try {
            // Pobranie aktualnej sesji z URL
            const urlParams = new URLSearchParams(window.location.search);
            const sessionId = urlParams.get('session_id');
            
            if (sessionId) {
                console.log(`Znaleziono ID sesji w URL: ${sessionId}, sprawdzam dostępność nowej puli...`);
                
                // Sprawdź czy istnieje już wygenerowana pula dla następnej sesji
                const poolStatsResponse = await fetch(`/api/sessions/${sessionId}/next-pool-stats`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (poolStatsResponse.ok) {
                    const poolStats = await poolStatsResponse.json();
                    console.log('Statystyki puli:', poolStats);
                    
                    if (!poolStats.is_ready) {
                        console.log('Brak gotowej puli, inicjuję generowanie...');
                        // Wygeneruj nową pulę
                        const generateResponse = await fetch('/api/sessions/generate-new-pool', {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${token}`,
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ previous_session_id: sessionId })
                        });
                        
                        if (generateResponse.ok) {
                            console.log('Żądanie generowania nowej puli zostało wysłane');
                            // Pokaż informację o generowaniu
                            updateLoadingMessage('Generowanie nowej puli danych (może potrwać do 1 minuty)...');
                            
                            // Sprawdzaj status generowania co 2 sekundy
                            let poolReady = false;
                            let attempts = 0;
                            const maxAttempts = 30; // Maksymalnie 60 sekund
                            
                            while (!poolReady && attempts < maxAttempts) {
                                await new Promise(resolve => setTimeout(resolve, 2000)); // Poczekaj 2 sekundy
                                attempts++;
                                
                                const checkResponse = await fetch(`/api/sessions/${sessionId}/next-pool-stats`, {
                                    headers: {
                                        'Authorization': `Bearer ${token}`
                                    }
                                });
                                
                                if (checkResponse.ok) {
                                    const checkData = await checkResponse.json();
                                    console.log(`Sprawdzenie #${attempts}: `, checkData);
                                    
                                    if (checkData.is_ready) {
                                        console.log('Nowa pula jest gotowa!');
                                        poolReady = true;
                                        break;
                                    }
                                }
                                
                                updateLoadingMessage(`Generowanie nowej puli danych (${attempts*2}s)...`);
                            }
                            
                            if (!poolReady) {
                                console.log('Upłynął czas oczekiwania na nową pulę, próbuję utworzyć sesję bezpośrednio...');
                            }
                        } else {
                            console.error('Błąd podczas żądania generowania nowej puli:', await generateResponse.text());
                        }
                    } else {
                        console.log('Nowa pula jest już gotowa do użycia');
                    }
                }
            }
        } catch (poolError) {
            console.error('Błąd podczas sprawdzania/generowania puli:', poolError);
            // Kontynuuj z tworzeniem sesji nawet jeśli wystąpił błąd
        }
        
        // Wywołanie API do utworzenia nowej sesji
        console.log('Wysyłanie żądania do API o utworzenie nowej sesji...');
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        console.log('Odpowiedź otrzymana, status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Błąd odpowiedzi serwera:', errorText);
            throw new Error(`Błąd podczas tworzenia nowej sesji (${response.status}): ${errorText}`);
        }
        
        const sessionData = await response.json();
        console.log('Utworzono nową sesję:', sessionData);
        
        // Przekierowanie do ekranu gry z nowym ID sesji
        console.log('Przekierowanie do ekranu gry...');
        window.location.href = `/game?session_id=${sessionData.id}`;
    } catch (error) {
        console.error('Błąd rozpoczynania nowej sesji:', error);
        hideLoading();
        alert('Wystąpił błąd podczas tworzenia nowej sesji. Spróbuj ponownie.');
    }
}

// Pomocnicza funkcja do aktualizacji komunikatu ładowania
function updateLoadingMessage(message) {
    const loadingMessage = getElement('loading-message');
    if (loadingMessage) {
        loadingMessage.textContent = message;
    }
}

// Funkcja sprawdzająca czy nowa pula jest gotowa
async function checkPoolReadiness(sessionId, retryCount = 0) {
    try {
        const response = await fetch(`/api/sessions/${sessionId}/next-pool-stats`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error('Błąd pobierania statystyk nowej puli');
        }
        
        const data = await response.json();
        
        if (data.is_ready) {
            // Pula jest gotowa - aktywuj przycisk i wyświetl statystyki
            const newSessionButton = document.getElementById('new-session-button');
            if (newSessionButton) {
                newSessionButton.disabled = false;
                newSessionButton.classList.remove('loading');
                newSessionButton.innerHTML = 'Nowa sesja';
                
                // Ustaw ID sesji dla przycisku
                newSessionButton.setAttribute('data-session-id', data.session_id);
            }
            
            // Wyświetl statystyki nowej puli
            displayPoolStatistics(data);
        } else if (retryCount < 150) { // Ograniczenie do 150 prób (5 minut przy 2s interwale)
            // Jeszcze nie gotowa - sprawdź ponownie za 2 sekundy
            setTimeout(() => checkPoolReadiness(sessionId, retryCount + 1), 2000);
        } else {
            // Przekroczono limit prób - wyświetl komunikat
            console.error('Nie udało się wygenerować puli w oczekiwanym czasie');
            const newSessionButton = document.getElementById('new-session-button');
            if (newSessionButton) {
                newSessionButton.disabled = false;
                newSessionButton.classList.remove('loading');
                newSessionButton.innerHTML = 'Nowa sesja';
            }
        }
    } catch (error) {
        console.error('Błąd sprawdzania gotowości puli:', error);
        // W przypadku błędu, spróbuj ponownie za chwilę (jeśli nie przekroczono limitu prób)
        if (retryCount < 150) {
            setTimeout(() => checkPoolReadiness(sessionId, retryCount + 1), 2000);
        } else {
            // Przekroczono limit prób - aktywuj przycisk
            const newSessionButton = document.getElementById('new-session-button');
            if (newSessionButton) {
                newSessionButton.disabled = false;
                newSessionButton.classList.remove('loading');
                newSessionButton.innerHTML = 'Nowa sesja';
            }
        }
    }
}

// Funkcja wyświetlająca statystyki nowej puli
function displayPoolStatistics(data) {
    console.log("Wyświetlam statystyki nowej puli:", data);
    
    // Znajdź lub utwórz kontener na statystyki
    let statsContainer = document.getElementById('pool-stats-container');
    if (!statsContainer) {
        statsContainer = document.createElement('div');
        statsContainer.id = 'pool-stats-container';
        statsContainer.className = 'pool-stats-box';
        
        // Dodaj kontener po przycisku nowej sesji
        const newSessionButton = document.getElementById('new-session-button');
        if (newSessionButton && newSessionButton.parentNode) {
            newSessionButton.parentNode.insertAdjacentElement('afterend', statsContainer);
        } else {
            document.querySelector('.session-summary-container').appendChild(statsContainer);
        }
    }
    
    // Przygotuj statystyki do wyświetlenia
    const totalCount = data.total_count || 0;
    const boughtCount = data.bought_count || 0;
    const generatedCount = data.child_count || 0;
    const randomCount = data.random_count || 0;
    
    // Przygotuj statystyki z podziałem na pozytywne i negatywne
    const posCount = data.pos_total || Math.floor(totalCount / 2) || 0;
    const negCount = data.neg_total || Math.floor(totalCount / 2) || 0;
    
    const posBoughtCount = data.pos_bought || Math.floor(boughtCount / 2) || 0;
    const negBoughtCount = data.neg_bought || Math.floor(boughtCount / 2) || 0;
    
    const posGenCount = data.pos_child || Math.floor(generatedCount / 2) || 0;
    const negGenCount = data.neg_child || Math.floor(generatedCount / 2) || 0;
    
    const posRandomCount = data.pos_random || Math.floor(randomCount / 2) || 0;
    const negRandomCount = data.neg_random || Math.floor(randomCount / 2) || 0;
    
    const statsHTML = `
        <h4>Statystyki nowej puli:</h4>
        <div class="pool-stats-grid">
            <div class="pool-stats-column">
                <h5>Bodźce pozytywne (${posCount}):</h5>
                <ul>
                    <li>Kupione: ${posBoughtCount}</li>
                    <li>Wygenerowane: ${posGenCount}</li>
                    <li>Losowe: ${posRandomCount}</li>
                </ul>
            </div>
            <div class="pool-stats-column">
                <h5>Bodźce negatywne (${negCount}):</h5>
                <ul>
                    <li>Kupione: ${negBoughtCount}</li>
                    <li>Wygenerowane: ${negGenCount}</li>
                    <li>Losowe: ${negRandomCount}</li>
                </ul>
            </div>
        </div>
    `;
    
    statsContainer.innerHTML = statsHTML;
}