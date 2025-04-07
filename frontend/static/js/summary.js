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

// Elementy DOM - aktualizacja identyfikatorów zgodnie z HTML
// ważne - dodanie sprawdzenia w funkcji inicjalizującej czy elementy istnieją
const sessionSuccessesElement = document.getElementById('session-successes');
const sessionFailuresElement = document.getElementById('session-failures');
const sessionDifferenceElement = document.getElementById('session-difference');
const sessionSuccessRateElement = document.getElementById('session-success-rate');
const sessionProfitElement = document.getElementById('session-profit');
const sessionWealthChartContainer = document.getElementById('wealth-chart');
const posRankingContainer = document.getElementById('positive-stimulus-ranking');
const roundsDetailsContainer = document.getElementById('rounds-details');
const roundsTable = document.getElementById('rounds-details-body');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingMessage = document.getElementById('loading-message');
const detailsToggleButton = document.getElementById('show-details-button');
const newSessionButton = document.getElementById('new-session-button');

// Pomocnicze funkcje
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
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // Aktualizacja nazwy użytkownika w navbar
    const usernameDisplay = document.getElementById('username-display');
    const username = localStorage.getItem('username');
    if (username && usernameDisplay) {
        usernameDisplay.textContent = `Witaj, ${username}`;
    }

    // Obsługa wylogowania
    const logoutButton = document.getElementById('logout-button');
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

    // Pobierz referencje do elementów po załadowaniu strony
    const detailsToggleButton = document.getElementById('show-details-button');
    const newSessionButton = document.getElementById('new-session-button');

    // Obsługa przycisków - sprawdź czy istnieją przed dodaniem event listenerów
    if (detailsToggleButton) {
        detailsToggleButton.addEventListener('click', toggleRoundsDetails);
    } else {
        console.error('Element detailsToggleButton nie istnieje');
    }
    
    if (newSessionButton) {
        newSessionButton.addEventListener('click', startNewSession);
    } else {
        console.error('Element newSessionButton nie istnieje');
    }
});

// Funkcja ładująca podsumowanie sesji
async function loadSessionSummary(sessionId) {
    try {
        showLoadingOverlay('Ładowanie podsumowania sesji...');
        
        // Pobieranie danych sesji
        const sessionResponse = await fetch(`/api/sessions/${sessionId}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!sessionResponse.ok) {
            console.error(`Błąd pobierania sesji: ${sessionResponse.status} - ${sessionResponse.statusText}`);
            throw new Error('Błąd podczas pobierania danych sesji');
        }
        
        currentSession = await sessionResponse.json();
        console.log('Pobrano dane sesji:', currentSession);
        
        // Pobieranie rund sesji
        const roundsResponse = await fetch(`/api/sessions/${sessionId}/rounds`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        
        if (!roundsResponse.ok) {
            console.error(`Błąd pobierania rund: ${roundsResponse.status} - ${roundsResponse.statusText}`);
            throw new Error('Błąd podczas pobierania danych rund');
        }
        
        sessionRounds = await roundsResponse.json();
        console.log('Pobrano dane rund:', sessionRounds);
        
        try {
            // Pobieranie podsumowania sesji
            const summaryResponse = await fetch(`/api/sessions/${sessionId}/summary`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            
            let sessionSummary;
            
            if (!summaryResponse.ok) {
                console.warn(`Błąd pobierania podsumowania sesji: ${summaryResponse.status} - ${summaryResponse.statusText}`);
                console.warn('Tworzenie zastępczego podsumowania z dostępnych danych');
                
                // Tworzymy zastępcze podsumowanie z danych, które udało się pobrać
                sessionSummary = {
                    id: currentSession.id,
                    status: currentSession.status,
                    started_at: currentSession.started_at,
                    session_profit_factor: currentSession.session_profit_factor || 1.0,
                    remaining_pairs: currentSession.remaining_pairs || 0,
                    success_count: sessionRounds.filter(round => round.result === 'SUCCESS').length,
                    failure_count: sessionRounds.filter(round => round.result === 'FAILURE').length,
                    round_count: sessionRounds.length,
                    pos_stimuli: [],
                    neg_stimuli: [],
                    pos_ranking: [],
                    neg_ranking: []
                };
            } else {
                sessionSummary = await summaryResponse.json();
                console.log('Pobrano podsumowanie sesji:', sessionSummary);
            }
            
            // Renderowanie danych - sprawdzamy czy elementy istnieją przed renderowaniem
            if (sessionSuccessesElement) {
                sessionSuccessesElement.textContent = sessionSummary.success_count;
            } else {
                console.error('Element sessionSuccessesElement nie istnieje - nie można renderować statystyk sesji');
            }
            
            if (sessionFailuresElement) {
                sessionFailuresElement.textContent = sessionSummary.failure_count;
            } else {
                console.error('Element sessionFailuresElement nie istnieje - nie można renderować statystyk sesji');
            }
            
            if (sessionDifferenceElement) {
                sessionDifferenceElement.textContent = sessionSummary.success_count - sessionSummary.failure_count;
            } else {
                console.error('Element sessionDifferenceElement nie istnieje - nie można renderować statystyk sesji');
            }
            
            if (sessionSuccessRateElement) {
                sessionSuccessRateElement.textContent = `${Math.round((sessionSummary.success_count / (sessionSummary.success_count + sessionSummary.failure_count)) * 100)}%`;
            } else {
                console.error('Element sessionSuccessRateElement nie istnieje - nie można renderować statystyk sesji');
            }
            
            if (sessionProfitElement) {
                sessionProfitElement.textContent = `${((sessionSummary.session_profit_factor - 1) * 100).toFixed(2)}%`;
            } else {
                console.error('Element sessionProfitElement nie istnieje - nie można renderować statystyk sesji');
            }
            
            if (document.getElementById('wealth-chart')) {
                renderWealthChart(sessionRounds);
            } else {
                console.error('Element wealth-chart nie istnieje - nie można renderować wykresu bogactwa');
            }
            
            // Bezpieczne renderowanie rankingów, jeśli są dostępne
            const posRankingElement = document.getElementById('positive-stimulus-ranking');
            if (posRankingElement) {
                if (sessionSummary.pos_ranking && sessionSummary.pos_ranking.length > 0) {
                    renderStimuliRanking(sessionSummary.pos_ranking, 'pos');
                } else {
                    console.log('Brak danych rankingowych dla bodźców pozytywnych');
                    posRankingElement.innerHTML = '<p>Brak danych dla rankingu bodźców pozytywnych</p>';
                }
            } else {
                console.error('Element positive-stimulus-ranking nie istnieje w dokumencie');
            }
            
            if (roundsTable) {
                renderRoundsDetails(sessionRounds);
            } else {
                console.error('Element roundsTable nie istnieje - nie można renderować szczegółów rund');
            }
            
        } catch (summaryError) {
            console.error('Błąd przetwarzania podsumowania:', summaryError);
            
            // Renderuj dostępne dane nawet bez podsumowania
            const fallbackSummary = {
                id: currentSession.id,
                status: currentSession.status || 'UNKNOWN',
                started_at: currentSession.started_at || new Date(),
                session_profit_factor: currentSession.session_profit_factor || 1.0,
                remaining_pairs: currentSession.remaining_pairs || 0,
                success_count: sessionRounds.filter(round => round.result === 'SUCCESS').length,
                failure_count: sessionRounds.filter(round => round.result === 'FAILURE').length,
                round_count: sessionRounds.length
            };
            
            // Sprawdzamy czy elementy istnieją przed renderowaniem
            if (sessionSuccessesElement) {
                sessionSuccessesElement.textContent = fallbackSummary.success_count;
            }
            
            if (sessionFailuresElement) {
                sessionFailuresElement.textContent = fallbackSummary.failure_count;
            }
            
            if (sessionDifferenceElement) {
                sessionDifferenceElement.textContent = fallbackSummary.success_count - fallbackSummary.failure_count;
            }
            
            if (sessionSuccessRateElement) {
                sessionSuccessRateElement.textContent = `${Math.round((fallbackSummary.success_count / (fallbackSummary.success_count + fallbackSummary.failure_count)) * 100)}%`;
            }
            
            if (sessionProfitElement) {
                sessionProfitElement.textContent = `${((fallbackSummary.session_profit_factor - 1) * 100).toFixed(2)}%`;
            }
            
            if (document.getElementById('wealth-chart')) {
                renderWealthChart(sessionRounds);
            }
            
            if (roundsTable) {
                renderRoundsDetails(sessionRounds);
            }
            
            // Próba renderowania pustych rankingów
            const posRankingElement = document.getElementById('positive-stimulus-ranking');
            if (posRankingElement) {
                posRankingElement.innerHTML = '<p>Nie udało się załadować rankingu bodźców pozytywnych</p>';
            }
        }
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania podsumowania sesji:', error);
        hideLoadingOverlay();
        
        // Wyświetl bardziej szczegółowy komunikat błędu
        alert(`Wystąpił błąd podczas ładowania podsumowania sesji: ${error.message}`);
        
        // Sprawdź, czy udało się załadować jakieś dane i spróbuj je wyświetlić
        if (currentSession && sessionRounds) {
            const fallbackSummary = {
                id: currentSession.id,
                status: currentSession.status || 'UNKNOWN',
                started_at: currentSession.started_at || new Date(),
                session_profit_factor: currentSession.session_profit_factor || 1.0,
                remaining_pairs: currentSession.remaining_pairs || 0,
                success_count: sessionRounds.filter(round => round.result === 'SUCCESS').length,
                failure_count: sessionRounds.filter(round => round.result === 'FAILURE').length,
                round_count: sessionRounds.length
            };
            
            // Sprawdzamy czy elementy istnieją przed renderowaniem
            if (sessionSuccessesElement) {
                sessionSuccessesElement.textContent = fallbackSummary.success_count;
            }
            
            if (sessionFailuresElement) {
                sessionFailuresElement.textContent = fallbackSummary.failure_count;
            }
            
            if (sessionDifferenceElement) {
                sessionDifferenceElement.textContent = fallbackSummary.success_count - fallbackSummary.failure_count;
            }
            
            if (sessionSuccessRateElement) {
                sessionSuccessRateElement.textContent = `${Math.round((fallbackSummary.success_count / (fallbackSummary.success_count + fallbackSummary.failure_count)) * 100)}%`;
            }
            
            if (sessionProfitElement) {
                sessionProfitElement.textContent = `${((fallbackSummary.session_profit_factor - 1) * 100).toFixed(2)}%`;
            }
            
            if (document.getElementById('wealth-chart')) {
                renderWealthChart(sessionRounds);
            }
            
            if (roundsTable) {
                renderRoundsDetails(sessionRounds);
            }
        }
    }
}

// Funkcja renderująca wykres bogactwa
function renderWealthChart(rounds) {
    // Przygotowanie danych
    const labels = rounds.map((_, index) => `Runda ${index + 1}`);
    const wealthData = [];
    let cumulativeWealth = 1.0; // Zaczynamy od 1.0 (100%)
    
    for (const round of rounds) {
        cumulativeWealth *= (1 + round.profit_fraction);
        wealthData.push((cumulativeWealth - 1) * 100); // Konwersja na procenty
    }
    
    // Tworzenie wykresu za pomocą Chart.js
    const ctx = document.getElementById('wealth-chart').getContext('2d');
    
    if (sessionWealthChart) {
        sessionWealthChart.destroy();
    }
    
    sessionWealthChart = new Chart(ctx, {
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
}

// Funkcja renderująca ranking bodźców
function renderStimuliRanking(ranking, type) {
    // Dla tego HTML obslugujemy tylko ranking pozytywny (type === 'pos')
    const container = document.getElementById('positive-stimulus-ranking');
    
    if (!container) {
        console.error(`Nie znaleziono kontenera dla rankingu bodźców`);
        return;
    }
    
    const title = 'Ranking bodźców pozytywnych';
    
    if (!ranking || ranking.length === 0) {
        container.innerHTML = `<p>Brak danych dla ${title}</p>`;
        return;
    }
    
    // Przygotowanie HTML
    let html = `<div class="ranking-container">`;
    
    ranking.forEach((stimulus, index) => {
        html += `
            <div class="stimulus-rank-item">
                <div class="stimulus-rank-number">#${index + 1}</div>
                <div class="stimulus-rank-image">
                    <img src="/api/images/${stimulus.id}/thumbnail" alt="Bodziec #${stimulus.id}">
                </div>
                <div class="stimulus-rank-details">
                    <div class="stimulus-id">ID: ${stimulus.id}</div>
                    <div class="stimulus-success-count">Sukcesy: ${stimulus.total_successes}</div>
                    <div class="stimulus-origin">
                        Pochodzenie: ${
                            stimulus.origin === 'child' ? 'Dziecko' : 
                            stimulus.origin === 'bought' ? 'Kupiony' : 'Losowy'
                        }
                        ${stimulus.parent ? `<span class="stimulus-parent-link">(Rodzic: ${stimulus.parent})</span>` : ''}
                    </div>
                    <div class="stimulus-profit">Zysk: ${((stimulus.total_profit_factor - 1) * 100).toFixed(2)}%</div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Funkcja renderująca szczegóły rund
function renderRoundsDetails(rounds) {
    if (!rounds || rounds.length === 0) {
        roundsTable.innerHTML = '<tr><td colspan="7">Brak danych o rundach</td></tr>';
        return;
    }
    
    // Przygotowanie HTML
    let html = `
        <tr>
            <th>Nr</th>
            <th>Data/Czas</th>
            <th>Wybór</th>
            <th>Akcja</th>
            <th>Zmiana kursu</th>
            <th>Zysk</th>
            <th>Wynik</th>
        </tr>
    `;
    
    rounds.forEach((round, index) => {
        const dateTime = new Date(round.created_at).toLocaleString();
        const priceChange = (((round.end_price / round.start_price) - 1) * 100).toFixed(2);
        const profit = (round.profit_fraction * 100).toFixed(2);
        
        html += `
            <tr>
                <td>${index + 1}</td>
                <td>${dateTime}</td>
                <td>${round.user_choice_side === 'LEFT' ? 'Lewa' : 'Prawa'}</td>
                <td>${round.user_action === 'BUY' ? 'Kupno' : 'Sprzedaż'}</td>
                <td>${priceChange > 0 ? '+' : ''}${priceChange}%</td>
                <td>${profit > 0 ? '+' : ''}${profit}%</td>
                <td class="${round.result === 'SUCCESS' ? 'success' : 'failure'}">${round.result === 'SUCCESS' ? 'SUKCES' : 'PORAŻKA'}</td>
            </tr>
        `;
    });
    
    roundsTable.innerHTML = html;
}

// Funkcja przełączająca widoczność szczegółów rund
function toggleRoundsDetails() {
    if (roundsDetailsContainer.style.display === 'none' || !roundsDetailsContainer.style.display) {
        roundsDetailsContainer.style.display = 'block';
        detailsToggleButton.textContent = 'Ukryj szczegółowy przebieg rund';
    } else {
        roundsDetailsContainer.style.display = 'none';
        detailsToggleButton.textContent = 'Pokaż szczegółowy przebieg rund';
    }
}

// Funkcja rozpoczynająca nową sesję
async function startNewSession() {
    try {
        showLoadingOverlay('Tworzenie nowej sesji...');
        
        // Wywołanie API do utworzenia nowej sesji
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error('Błąd podczas tworzenia nowej sesji');
        }
        
        // Przekierowanie do ekranu gry
        window.location.href = '/game';
    } catch (error) {
        console.error('Błąd rozpoczynania nowej sesji:', error);
        hideLoadingOverlay();
        alert('Wystąpił błąd podczas tworzenia nowej sesji. Spróbuj ponownie.');
    }
}

// Funkcje pomocnicze do pokazywania/ukrywania overlay ładowania
function showLoading(message = 'Ładowanie...') {
    loadingMessage.textContent = message;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
} 