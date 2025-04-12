// Stan aplikacji dla strony statystyk
const StatsState = {
    sessions: [],
    totalWealthChart: null,
    timeSuccessChart: null,
    genealogyType: 'positive' // positive | negative
};

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

// Inicjalizacja strony statystyk
async function initStats() {
    showLoadingOverlay('Ładowanie statystyk użytkownika...');
    
    try {
        // Pobierz sesje użytkownika
        await loadUserSessions();
        
        // Pobierz ranking globalny obrazów
        await loadGlobalStimuliRanking();
        
        // Pobierz dane genealogii
        await loadGenealogyData('positive');
        
        // Generuj wykres bogactwa
        generateTotalWealthChart();
        
        // Aktualizuj globalne statystyki
        updateGlobalStats();
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania statystyk:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Ładowanie sesji użytkownika
async function loadUserSessions() {
    const response = await fetchWithAuth('/api/user/sessions');
    
    if (!response.ok) {
        throw new Error('Nie można załadować sesji użytkownika');
    }
    
    StatsState.sessions = await response.json();
}

// Aktualizacja listy sesji
function updateSessionsList() {
    const tableBody = document.getElementById('sessions-list');
    tableBody.innerHTML = '';
    
    const sessions = StatsState.sessions;
    
    if (!sessions || sessions.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5">Brak zakończonych sesji.</td></tr>';
        return;
    }
    
    // Sortuj według daty (najnowsze pierwsze)
    const sortedSessions = [...sessions].sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
    
    sortedSessions.forEach(session => {
        const row = document.createElement('tr');
        
        // Formatowanie daty
        const date = new Date(session.started_at);
        const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
        
        // Formatowanie zysku
        const profit = ((session.session_profit_factor - 1) * 100).toFixed(2);
        const profitClass = parseFloat(profit) >= 0 ? 'positive' : 'negative';
        
        row.innerHTML = `
            <td>${session.id}</td>
            <td>${formattedDate}</td>
            <td class="${profitClass}">${profit}%</td>
            <td>${session.round_count}</td>
            <td>
                <button class="button small-button view-session-details" data-session-id="${session.id}">Szczegóły</button>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Dodaj obsługę zdarzeń dla przycisków szczegółów
    document.querySelectorAll('.view-session-details').forEach(button => {
        button.addEventListener('click', () => {
            openSessionDetails(button.getAttribute('data-session-id'));
        });
    });
}

// Otwórz szczegóły sesji w modalu
async function openSessionDetails(sessionId) {
    showLoadingOverlay('Ładowanie szczegółów sesji...');
    
    try {
        // Pobierz dane sesji
        const sessionResponse = await fetchWithAuth(`/api/sessions/${sessionId}/summary`);
        if (!sessionResponse.ok) {
            throw new Error('Nie można załadować szczegółów sesji');
        }
        const sessionData = await sessionResponse.json();
        
        // Pobierz dane rund
        const roundsResponse = await fetchWithAuth(`/api/sessions/${sessionId}/rounds`);
        if (!roundsResponse.ok) {
            throw new Error('Nie można załadować rund sesji');
        }
        const roundsData = await roundsResponse.json();
        
        // Wypełnij modal
        const modal = document.getElementById('session-details-modal');
        const content = modal.querySelector('.session-details-content');
        document.getElementById('session-details-id').textContent = sessionId;
        
        // Statystyki sesji
        const profit = ((sessionData.session_profit_factor - 1) * 100).toFixed(2);
        const successRate = sessionData.round_count > 0 
            ? Math.round((sessionData.success_count / sessionData.round_count) * 100) 
            : 0;
        
        content.innerHTML = `
            <div class="session-details-stats">
                <div class="stat-group">
                    <div class="stat-label">Sukcesów</div>
                    <div class="stat-value">${sessionData.success_count}</div>
                </div>
                <div class="stat-group">
                    <div class="stat-label">Porażek</div>
                    <div class="stat-value">${sessionData.failure_count}</div>
                </div>
                <div class="stat-group">
                    <div class="stat-label">Skuteczność</div>
                    <div class="stat-value">${successRate}%</div>
                </div>
                <div class="stat-group">
                    <div class="stat-label">Zysk</div>
                    <div class="stat-value ${parseFloat(profit) >= 0 ? 'positive' : 'negative'}">${profit}%</div>
                </div>
            </div>
            
            <h3>Przebieg rundy</h3>
            <div class="session-chart-container">
                <canvas id="session-wealth-chart"></canvas>
            </div>
            
            <h3>Przebieg rund</h3>
            <div class="rounds-table-container">
                <table class="details-table">
                    <thead>
                        <tr>
                            <th>Nr</th>
                            <th>Data/Czas</th>
                            <th>Wybór</th>
                            <th>Zmiana %</th>
                            <th>Wynik</th>
                        </tr>
                    </thead>
                    <tbody id="modal-rounds-details">
                    </tbody>
                </table>
            </div>
        `;
        
        // Wypełnij tabelę rund
        const tableBody = document.getElementById('modal-rounds-details');
        if (roundsData && roundsData.length > 0) {
            roundsData.forEach((round, index) => {
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
                    <td>${round.user_choice_side === 'LEFT' ? 'Lewa' : 'Prawa'}</td>
                    <td class="${round.profit_fraction >= 0 ? 'positive' : 'negative'}">${profitSign}${profitPercent}%</td>
                    <td class="${round.result.toLowerCase()}">${round.result === 'SUCCESS' ? 'SUKCES' : 'PORAŻKA'}</td>
                `;
                
                tableBody.appendChild(row);
            });
            
            // Stwórz wykres
            generateSessionWealthChart(roundsData);
        } else {
            tableBody.innerHTML = '<tr><td colspan="5">Brak danych o rundach.</td></tr>';
        }
        
        // Pokaż modal
        modal.style.display = 'block';
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania szczegółów sesji:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Generowanie wykresu bogactwa dla pojedynczej sesji (w modalu)
function generateSessionWealthChart(rounds) {
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
    const ctx = document.getElementById('session-wealth-chart').getContext('2d');
    
    if (window.sessionChart) {
        window.sessionChart.destroy();
    }
    
    window.sessionChart = new Chart(ctx, {
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
            }
        }
    });
}

// Generowanie wykresu całkowitego bogactwa
function generateTotalWealthChart() {
    const sessions = StatsState.sessions;
    
    if (!sessions || sessions.length === 0) {
        return;
    }
    
    // Sortuj według daty (najstarsze pierwsze)
    const sortedSessions = [...sessions].sort((a, b) => new Date(a.started_at) - new Date(b.started_at));
    
    // Przygotuj dane dla wykresu
    const labels = sortedSessions.map((session, index) => `Sesja ${index + 1}`);
    const wealthData = [];
    
    let cumulativeWealth = 1.0;
    for (const session of sortedSessions) {
        cumulativeWealth *= session.session_profit_factor;
        wealthData.push(cumulativeWealth);
    }
    
    // Przekształć na procentowy zysk
    const percentWealthData = wealthData.map(value => ((value - 1) * 100).toFixed(2));
    
    // Stwórz wykres
    const ctx = document.getElementById('total-wealth-chart').getContext('2d');
    
    StatsState.totalWealthChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Skumulowany zysk (%)',
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
                        text: 'Skumulowany zysk (%)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Sesja'
                    }
                }
            }
        }
    });
}

// Generowanie wykresu skuteczności w czasie
function generateTimeSuccessChart() {
    const sessions = StatsState.sessions;
    
    if (!sessions || sessions.length === 0) {
        return;
    }
    
    // Przygotuj dane - podziel na przedziały godzinowe
    const hourData = Array(24).fill(0).map(() => ({ successes: 0, failures: 0 }));
    
    // Przeanalizuj wszystkie rundy ze wszystkich sesji
    sessions.forEach(session => {
        if (session.rounds && session.rounds.length > 0) {
            session.rounds.forEach(round => {
                const date = new Date(round.created_at);
                const hour = date.getHours();
                
                if (round.result === 'SUCCESS') {
                    hourData[hour].successes++;
                } else {
                    hourData[hour].failures++;
                }
            });
        }
    });
    
    // Oblicz skuteczność dla każdej godziny
    const successRates = hourData.map(data => {
        const total = data.successes + data.failures;
        return total > 0 ? (data.successes / total * 100).toFixed(2) : 0;
    });
    
    // Przygotuj etykiety godzin
    const hourLabels = Array(24).fill(0).map((_, i) => `${i}:00`);
    
    // Stwórz wykres
    const ctx = document.getElementById('time-success-chart').getContext('2d');
    
    StatsState.timeSuccessChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hourLabels,
            datasets: [{
                label: 'Skuteczność (%)',
                data: successRates,
                backgroundColor: 'rgba(125, 64, 254, 0.7)',
                borderColor: 'rgba(125, 64, 254, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Skuteczność (%)'
                    },
                    max: 100
                },
                x: {
                    title: {
                        display: true,
                        text: 'Godzina dnia'
                    }
                }
            }
        }
    });
}

// Funkcja aktualizująca wyświetlanie statystyk
function updateStatsDisplay(totalSessions, totalRounds, totalSuccesses, totalFailures, leftClicks, rightClicks, totalWealth) {
    // Podstawowe wartości
    document.getElementById('total-sessions').textContent = totalSessions;
    document.getElementById('total-rounds').textContent = totalRounds;
    
    // Obliczenia z obsługą przypadków brzegowych
    const totalAttempts = totalSuccesses + totalFailures;
    const successPercentage = totalAttempts > 0 ? ((totalSuccesses / totalAttempts) * 100).toFixed(1) : "0";
    const failurePercentage = totalAttempts > 0 ? ((totalFailures / totalAttempts) * 100).toFixed(1) : "0";
    
    const totalClicks = leftClicks + rightClicks;
    const leftPercentage = totalClicks > 0 ? ((leftClicks / totalClicks) * 100).toFixed(1) : "0";
    const rightPercentage = totalClicks > 0 ? ((rightClicks / totalClicks) * 100).toFixed(1) : "0";
    
    // Sukcesy
    document.getElementById('success-count').textContent = totalSuccesses;
    document.getElementById('success-percentage').textContent = `${successPercentage}%`;
    
    // Porażki
    document.getElementById('failure-count').textContent = totalFailures;
    document.getElementById('failure-percentage').textContent = `${failurePercentage}%`;
    
    // Różnica
    const difference = totalSuccesses - totalFailures;
    const differenceElement = document.getElementById('difference');
    differenceElement.textContent = difference;
    differenceElement.className = 'stat-value difference-value ' + (difference >= 0 ? 'positive' : 'negative');
    
    // Kliknięcia
    document.getElementById('left-clicks').textContent = leftClicks;
    document.getElementById('left-clicks-percentage').textContent = `${leftPercentage}%`;
    
    document.getElementById('right-clicks').textContent = rightClicks;
    document.getElementById('right-clicks-percentage').textContent = `${rightPercentage}%`;
    
    // Skumulowane bogactwo
    document.getElementById('total-wealth').textContent = `${((totalWealth - 1) * 100).toFixed(1)}%`;
}

// Funkcja aktualizująca globalne statystyki
async function updateGlobalStats() {
    const totalSessions = StatsState.sessions.length;
    let totalRounds = 0;
    let totalSuccesses = 0;
    let totalFailures = 0;
    let leftClicks = 0;
    let rightClicks = 0;
    let totalWealth = 1; // Startujemy od 1 (100%)

    // Najpierw obliczamy sumę rund i wyników
    StatsState.sessions.forEach(session => {
        totalRounds += session.round_count;
        totalSuccesses += session.success_count;
        totalFailures += session.failure_count;
        totalWealth *= (1 + session.session_profit_factor);
    });

    // Teraz pobieramy rundy dla każdej sesji
    const roundPromises = StatsState.sessions.map(session => 
        fetchWithAuth(`/api/sessions/${session.id}/rounds`).then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Błąd pobierania rund');
        })
    );

    try {
        const allRounds = await Promise.all(roundPromises);
        allRounds.forEach(rounds => {
            rounds.forEach(round => {
                if (round.user_choice_side === 'LEFT') {
                    leftClicks++;
                } else if (round.user_choice_side === 'RIGHT') {
                    rightClicks++;
                }
            });
        });

        // Aktualizujemy wszystkie statystyki
        updateStatsDisplay(totalSessions, totalRounds, totalSuccesses, totalFailures, leftClicks, rightClicks, totalWealth);
    } catch (error) {
        console.error('Błąd podczas pobierania rund:', error);
        // W przypadku błędu nadal wyświetlamy podstawowe statystyki
        updateStatsDisplay(totalSessions, totalRounds, totalSuccesses, totalFailures, leftClicks, rightClicks, totalWealth);
    }
}

// Ładowanie rankingu globalnego obrazów
async function loadGlobalStimuliRanking() {
    // Pobierz ranking pozytywnych bodźców
    const positiveResponse = await fetchWithAuth('/api/images/ranking?type=POSITIVE');
    if (!positiveResponse.ok) {
        throw new Error('Nie można załadować rankingu pozytywnych obrazów');
    }
    const positiveRanking = await positiveResponse.json();
    
    // Pobierz ranking negatywnych bodźców
    const negativeResponse = await fetchWithAuth('/api/images/ranking?type=NEGATIVE');
    if (!negativeResponse.ok) {
        throw new Error('Nie można załadować rankingu negatywnych obrazów');
    }
    const negativeRanking = await negativeResponse.json();
    
    // Zaktualizuj oba rankingi
    updateGlobalStimuliRanking(positiveRanking, 'positive');
    updateGlobalStimuliRanking(negativeRanking, 'negative');
}

// Aktualizacja rankingu globalnego obrazów
function updateGlobalStimuliRanking(ranking, type) {
    // Wybierz odpowiedni kontener na podstawie typu
    const containerId = type === 'positive' ? 'positive-stimulus-ranking' : 'negative-stimulus-ranking';
    const rankingContainer = document.getElementById(containerId);
    rankingContainer.innerHTML = '';
    
    if (!ranking || ranking.length === 0) {
        rankingContainer.innerHTML = '<p>Brak danych rankingowych.</p>';
        return;
    }
    
    // Ogranicz do 10 najlepszych
    const topRanking = ranking.slice(0, 10);
    
    // Stwórz elementy rankingu
    topRanking.forEach((item, index) => {
        const stimulusElement = document.createElement('div');
        stimulusElement.className = 'stimulus-rank-item';
        
        const profit = ((item.total_profit_factor - 1) * 100).toFixed(2);
        const profitClass = parseFloat(profit) >= 0 ? 'positive' : 'negative';
        
        stimulusElement.innerHTML = `
            <div class="stimulus-rank-number">${index + 1}</div>
            <div class="stimulus-rank-image">
                <img src="/api/images/${item.id}/thumbnail" alt="Bodziec #${item.id}">
            </div>
            <div class="stimulus-rank-details">
                <div class="stimulus-id">ID: ${item.id}</div>
                <div class="stimulus-success-count">Sukcesów: ${item.total_successes}</div>
                <div class="stimulus-profit ${profitClass}">Zysk: ${profit}%</div>
            </div>
        `;
        
        rankingContainer.appendChild(stimulusElement);
    });
}

// Ładowanie danych genealogii
async function loadGenealogyData(type) {
    StatsState.genealogyType = type;
    showLoadingOverlay('Ładowanie genealogii bodźców...');
    
    try {
        // Pobierz sesje użytkownika, jeśli jeszcze nie pobrano
        if (!StatsState.sessions || StatsState.sessions.length === 0) {
            await loadUserSessions();
        }
        
        // Pobierz dane genealogii
        const response = await fetchWithAuth(`/api/genealogy/${type}`);
        
        if (!response.ok) {
            throw new Error('Nie można załadować danych genealogii');
        }
        
        const genealogyData = await response.json();
        
        // Zaktualizuj widok z nowymi danymi
        updateGenealogyView(genealogyData, type);
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania genealogii:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Aktualizacja widoku genealogii - nowa implementacja
function updateGenealogyView(genealogyData, type) {
    const genealogyContainer = document.getElementById('genealogy-container');
    genealogyContainer.innerHTML = '';
    
    if (!genealogyData || genealogyData.length === 0) {
        genealogyContainer.innerHTML = '<p>Brak danych genealogicznych.</p>';
        return;
    }
    
    // Pobierz sesje użytkownika posortowane od najnowszej do najstarszej
    const sessions = [...StatsState.sessions].sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
    
    if (!sessions || sessions.length === 0) {
        genealogyContainer.innerHTML = '<p>Brak sesji do wyświetlenia.</p>';
        return;
    }
    
    // Utwórz mapę wszystkich bodźców z genealogii dla szybkiego dostępu
    const genealogyMap = new Map();
    genealogyData.forEach(node => {
        genealogyMap.set(node.id, node);
    });
    
    // Utwórz kontener dla całego widoku genealogii
    const genealogyView = document.createElement('div');
    genealogyView.className = 'genealogy-view';
    
    // Dodaj nagłówek z informacją o typie bodźców
    const headerRow = document.createElement('div');
    headerRow.className = 'genealogy-header';
    headerRow.innerHTML = `
        <div class="genealogy-title">Genealogia bodźców ${type === 'positive' ? 'pozytywnych' : 'negatywnych'}</div>
        <div class="genealogy-info">
            <p>Kliknij bodziec, aby zobaczyć jego przodków i potomków</p>
            <p><span class="color-guide random">■</span> random <span class="color-guide bought">■</span> bought <span class="color-guide child">■</span> child</p>
        </div>
    `;
    genealogyView.appendChild(headerRow);
    
    // Stwórz kontener dla sesji
    const sessionsContainer = document.createElement('div');
    sessionsContainer.className = 'genealogy-sessions-container';
    
    // Licznik załadowanych sesji
    let loadedSessions = 0;
    const sessionsToLoad = Math.min(20, sessions.length);
    
    // Iteruj przez sesje
    sessions.slice(0, sessionsToLoad).forEach((session, index) => {
        if (!session || !session.id) return; // Pomijamy nieprawidłowe sesje
        
        // Pobierz datę sesji
        const sessionDate = new Date(session.started_at || new Date());
        const formattedDate = `${sessionDate.toLocaleDateString()} ${sessionDate.toLocaleTimeString()}`;
        
        // Stwórz wiersz sesji
        const sessionRow = document.createElement('div');
        sessionRow.className = 'genealogy-session-row';
        sessionRow.dataset.sessionId = session.id;
        
        // Dodaj header sesji
        const sessionHeader = document.createElement('div');
        sessionHeader.className = 'genealogy-session-header';
        
        // Formatowanie zysku
        const profit = ((session.session_profit_factor - 1) * 100).toFixed(2);
        const profitClass = parseFloat(profit) >= 0 ? 'positive' : 'negative';
        
        sessionHeader.innerHTML = `
            <div class="session-info">
                <span class="session-number">Sesja ${sessions.length - index}</span>
                <span class="session-date">${formattedDate}</span>
                <span class="session-id">ID: ${session.id}</span>
            </div>
            <div class="session-stats">
                <span class="session-rounds">Rund: ${session.round_count}</span>
                <span class="session-profit ${profitClass}">Zysk: ${profit}%</span>
                <button class="button small-button view-session-details" data-session-id="${session.id}">Szczegóły</button>
            </div>
        `;
        sessionRow.appendChild(sessionHeader);
        
        // Stwórz kontener dla pul bodźców
        const poolsContainer = document.createElement('div');
        poolsContainer.className = 'genealogy-pools-container';
        
        // Dodaj pule bodźców (pozytywne i negatywne)
        const typesToShow = type === 'all' ? ['positive', 'negative'] : [type];
        
        typesToShow.forEach(poolType => {
            // Stwórz kontener dla puli
            const poolContainer = document.createElement('div');
            poolContainer.className = `genealogy-pool ${poolType}-pool`;
            
            // Stwórz nagłówek puli
            const poolHeader = document.createElement('div');
            poolHeader.className = 'pool-header';
            poolHeader.innerHTML = `<h4>${poolType === 'positive' ? 'Bodźce pozytywne' : 'Bodźce negatywne'}</h4>`;
            
            // Dodaj nagłówek i kontener puli do kontenera pul
            const poolSection = document.createElement('div');
            poolSection.className = `pool-section ${poolType}-section`;
            poolSection.appendChild(poolHeader);
            poolSection.appendChild(poolContainer);
            poolsContainer.appendChild(poolSection);
            
            // Pobierz pulę z API
            fetchWithAuth(`/api/sessions/${session.id}/pools?type=${poolType}`)
                .then(response => {
                    if (response.ok) {
                        return response.json();
                    }
                    throw new Error(`Błąd pobierania puli typu ${poolType} dla sesji ${session.id}`);
                })
                .then(poolData => {
                    if (poolData && Array.isArray(poolData) && poolData.length > 0) {
                        poolData.forEach(item => {
                            if (item && typeof item === 'object') {
                                // Stwórz element bodźca
                                const stimulusCard = createStimulusCard(item, genealogyMap);
                                poolContainer.appendChild(stimulusCard);
                            }
                        });
                    } else {
                        poolContainer.innerHTML = '<p class="no-data">Brak bodźców</p>';
                    }
                })
                .catch(error => {
                    console.error(`Błąd pobierania puli ${poolType} dla sesji ${session.id}:`, error);
                    poolContainer.innerHTML = '<p class="error">Błąd pobierania danych</p>';
                });
        });
        
        // Dodaj kontener pul do wiersza sesji
        sessionRow.appendChild(poolsContainer);
        
        // Dodaj wiersz sesji do kontenera sesji
        sessionsContainer.appendChild(sessionRow);
        
        loadedSessions++;
    });
    
    // Dodaj przycisk "Załaduj więcej" jeśli są jeszcze sesje do załadowania
    if (loadedSessions < sessions.length) {
        const loadMoreButton = document.createElement('button');
        loadMoreButton.className = 'button secondary-button load-more-button';
        loadMoreButton.textContent = 'Załaduj więcej sesji';
        loadMoreButton.addEventListener('click', () => {
            // Implementacja ładowania kolejnych sesji
            const startIndex = loadedSessions;
            const nextSessionsToLoad = Math.min(10, sessions.length - loadedSessions);
            
            if (nextSessionsToLoad <= 0) {
                loadMoreButton.disabled = true;
                loadMoreButton.textContent = 'Nie ma więcej sesji do załadowania';
                return;
            }
            
            showLoadingOverlay('Ładowanie dodatkowych sesji...');
            
            // Dodajemy timeout, aby UI mogło się odświeżyć
            setTimeout(() => {
                // Dodaj kolejne sesje
                sessions.slice(startIndex, startIndex + nextSessionsToLoad).forEach((session, index) => {
                    if (!session || !session.id) return; // Pomijamy nieprawidłowe sesje
                    
                    // Tutaj powtórz kod tworzenia wiersza sesji podobny do powyższego
                    // ...
                    
                    // Aktualizuj licznik
                    loadedSessions++;
                });
                
                // Jeśli załadowaliśmy wszystkie sesje, ukryj przycisk
                if (loadedSessions >= sessions.length) {
                    loadMoreButton.style.display = 'none';
                }
                
                hideLoadingOverlay();
            }, 100);
        });
        sessionsContainer.appendChild(loadMoreButton);
    }
    
    // Dodaj kontener sesji do widoku genealogii
    genealogyView.appendChild(sessionsContainer);
    
    // Dodaj widok genealogii do kontenera
    genealogyContainer.appendChild(genealogyView);
    
    // Dodaj obsługę przycisków szczegółów
    document.querySelectorAll('.genealogy-view .view-session-details').forEach(button => {
        button.addEventListener('click', (event) => {
            event.stopPropagation(); // Zapobiegaj propagacji kliknięcia do karty
            openSessionDetails(button.getAttribute('data-session-id'));
        });
    });
}

// Funkcja tworząca kartę bodźca
function createStimulusCard(item, genealogyMap) {
    const card = document.createElement('div');
    card.className = 'stimulus-card';
    card.dataset.id = item.id;
    card.dataset.origin = item.origin || 'unknown';
    
    // Określ klasę na podstawie pochodzenia
    const originClass = getOriginClass(item.origin);
    card.classList.add(originClass);
    
    // Dodaj klasę dla bodźców z dodatnią liczbą sukcesów
    const successes = item.successes || 0;
    if (successes > 0) {
        card.classList.add('has-successes');
    }
    
    // Pobierz dane genealogiczne, jeśli dostępne
    const genealogyNode = genealogyMap.get(item.id);
    
    // Ustal klasę dla liczby sukcesów
    const successClass = successes > 0 ? 'success-count positive' : 'success-count negative';
    
    // Przygotuj HTML dla części z informacją o pochodzeniu
    let originHtml = '';
    if (item.origin && item.origin.startsWith('child_of_')) {
        // Pobierz ID rodziców
        const parentIds = getParentIdsFromOrigin(item.origin);
        originHtml = '<div class="origin-parents">';
        
        // Dodaj kafelki dla każdego rodzica
        parentIds.forEach(parentId => {
            originHtml += `<span class="parent-badge">${parentId}</span>`;
        });
        
        // Dodaj informację o szumie, jeśli istnieje
        if (item.origin.includes('noise')) {
            const noiseMatch = item.origin.match(/noise_(\d+)/);
            if (noiseMatch && noiseMatch[1]) {
                originHtml += `<span class="noise-badge">Szum ${noiseMatch[1]}</span>`;
            }
        }
        
        originHtml += '</div>';
    } else {
        originHtml = `<div class="origin-label ${originClass.replace('origin-', '')}">${translateOrigin(item.origin || 'unknown')}</div>`;
    }
    
    // Ustaw zawartość karty
    card.innerHTML = `
        <div class="stimulus-image">
            <img src="/api/images/${item.id}/thumbnail" alt="Bodziec #${item.id}" loading="lazy">
        </div>
        <div class="stimulus-details">
            <div class="stimulus-id">ID: ${item.id}</div>
            <div class="stimulus-stats">
                <span class="${successClass}">${successes}</span>
            </div>
            <div class="stimulus-origin-container">
                ${originHtml}
            </div>
        </div>
    `;
    
    // Dodaj obsługę kliknięcia
    card.addEventListener('click', () => {
        // Usuń podświetlenie ze wszystkich kart
        document.querySelectorAll('.stimulus-card').forEach(c => {
            c.classList.remove('highlighted', 'ancestor-random', 'ancestor-bought', 'ancestor-child', 'descendant-random', 'descendant-bought', 'descendant-child');
        });
        
        // Podświetl tę kartę
        card.classList.add('highlighted');
        
        // Podświetl przodków i potomków
        highlightAncestors(card);
        highlightDescendants(card);
    });
    
    return card;
}

// Funkcja określająca klasę CSS na podstawie pochodzenia
function getOriginClass(origin) {
    if (!origin) return 'origin-unknown';
    if (origin === 'random') return 'origin-random';
    if (origin === 'bought') return 'origin-bought';
    if (origin.startsWith('child_of_')) return 'origin-child';
    return 'origin-unknown';
}

// Pobranie ID rodziców z origin typu child_of_X_Y
function getParentIdsFromOrigin(origin) {
    if (!origin || !origin.startsWith('child_of_')) return [];
    
    // Spróbuj dopasować obie wersje: child_of_X_Y lub child_of_X
    const match = origin.match(/child_of_(\d+)(?:_(\d+))?/);
    if (!match) return [];
    
    const parentIds = [];
    if (match[1]) parentIds.push(parseInt(match[1]));
    if (match[2]) parentIds.push(parseInt(match[2]));
    
    return parentIds;
}

// Funkcja podświetlająca przodków
function highlightAncestors(cardElement) {
    const clickedId = parseInt(cardElement.dataset.id);
    const origin = cardElement.dataset.origin;
    
    // Znajdź wszystkie sesje (od najnowszej do najstarszej)
    const sessionRows = document.querySelectorAll('.genealogy-session-row');
    const clickedSessionRow = cardElement.closest('.genealogy-session-row');
    
    // Indeks klikniętej sesji w kolekcji wszystkich sesji
    let clickedIndex = -1;
    sessionRows.forEach((row, index) => {
        if (row === clickedSessionRow) {
            clickedIndex = index;
        }
    });
    
    // Jeśli to bodziec typu child_of_, znajdź jego rodziców
    let parentIds = [];
    if (origin && origin.startsWith('child_of_')) {
        parentIds = getParentIdsFromOrigin(origin);
    } 
    // Jeśli to bodziec typu bought, znajdź oryginał
    else if (origin === 'bought') {
        parentIds = [clickedId]; // Szukamy tego samego ID ale innego origin
    }
    
    // Jeśli znaleźliśmy rodziców lub to bodziec bought, podświetl ich w starszych sesjach
    if (parentIds.length > 0 && clickedIndex >= 0) {
        // Przeszukuj starsze sesje (mają wyższy indeks)
        for (let i = clickedIndex + 1; i < sessionRows.length; i++) {
            const session = sessionRows[i];
            const stimulusCards = session.querySelectorAll('.stimulus-card');
            
            stimulusCards.forEach(card => {
                const cardId = parseInt(card.dataset.id);
                const cardOrigin = card.dataset.origin;
                
                // Sprawdź czy to rodzic
                if (parentIds.includes(cardId)) {
                    // Dla bodźców bought szukamy oryginału (tego samego ID ale innego origin)
                    if (origin === 'bought') {
                        if (cardId === clickedId && cardOrigin !== 'bought') {
                            card.classList.add('ancestor-' + getOriginClass(cardOrigin).replace('origin-', ''));
                            
                            // Rekurencyjnie podświetl przodków tego rodzica, jeśli on też był dzieckiem
                            if (cardOrigin && cardOrigin.startsWith('child_of_')) {
                                highlightAncestors(card);
                            }
                        }
                    } else {
                        // Dla pozostałych typów szukamy po ID
                        card.classList.add('ancestor-' + getOriginClass(cardOrigin).replace('origin-', ''));
                        
                        // Rekurencyjnie podświetl przodków tego rodzica, jeśli on też był dzieckiem
                        if (cardOrigin && cardOrigin.startsWith('child_of_')) {
                            highlightAncestors(card);
                        }
                    }
                }
            });
        }
    }
}

// Funkcja podświetlająca potomków
function highlightDescendants(cardElement) {
    const clickedId = parseInt(cardElement.dataset.id);
    
    // Znajdź wszystkie sesje (od najnowszej do najstarszej)
    const sessionRows = document.querySelectorAll('.genealogy-session-row');
    const clickedSessionRow = cardElement.closest('.genealogy-session-row');
    
    // Indeks klikniętej sesji w kolekcji wszystkich sesji
    let clickedIndex = -1;
    sessionRows.forEach((row, index) => {
        if (row === clickedSessionRow) {
            clickedIndex = index;
        }
    });
    
    // Przeszukuj nowsze sesje (mają niższy indeks)
    if (clickedIndex > 0) {
        for (let i = clickedIndex - 1; i >= 0; i--) {
            const session = sessionRows[i];
            const stimulusCards = session.querySelectorAll('.stimulus-card');
            
            stimulusCards.forEach(card => {
                const cardOrigin = card.dataset.origin;
                
                // Sprawdź czy to potomek (origin zawiera ID klikniętego bodźca)
                if (cardOrigin && cardOrigin.startsWith('child_of_')) {
                    const parentIds = getParentIdsFromOrigin(cardOrigin);
                    
                    if (parentIds.includes(clickedId)) {
                        card.classList.add('descendant-' + getOriginClass(cardOrigin).replace('origin-', ''));
                        
                        // Rekurencyjnie podświetl potomków tego potomka
                        highlightDescendants(card);
                    }
                }
            });
        }
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

// Obsługa zdarzeń
document.addEventListener('DOMContentLoaded', () => {
    // Inicjalizacja strony statystyk
    initStats();
    
    // Obsługa przycisków przełączania genealogii
    document.getElementById('show-positive-genealogy').addEventListener('click', () => {
        document.getElementById('show-positive-genealogy').classList.add('active');
        document.getElementById('show-negative-genealogy').classList.remove('active');
        loadGenealogyData('positive');
    });
    
    document.getElementById('show-negative-genealogy').addEventListener('click', () => {
        document.getElementById('show-positive-genealogy').classList.remove('active');
        document.getElementById('show-negative-genealogy').classList.add('active');
        loadGenealogyData('negative');
    });
    
    // Zamykanie modala
    const modal = document.getElementById('session-details-modal');
    const closeButton = modal.querySelector('.close');
    
    closeButton.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    
    // Zamykanie modala po kliknięciu poza jego obszarem
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
}); 