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
        await updateSessionsList();
        
        // Pobierz ranking globalny obrazów
        await loadGlobalStimuliRanking();
        
        // Pobierz dane genealogii
        await loadGenealogyData('positive');
        
        // Generuj wykresy
        generateTotalWealthChart();
        generateTimeSuccessChart();
        
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
    
    // Sukcesy
    document.getElementById('success-count').textContent = totalSuccesses;
    document.getElementById('success-percentage').textContent = `${((totalSuccesses / (totalSuccesses + totalFailures)) * 100).toFixed(1)}%`;
    
    // Porażki
    document.getElementById('failure-count').textContent = totalFailures;
    document.getElementById('failure-percentage').textContent = `${((totalFailures / (totalSuccesses + totalFailures)) * 100).toFixed(1)}%`;
    
    // Różnica
    const difference = totalSuccesses - totalFailures;
    const differenceElement = document.getElementById('difference');
    differenceElement.textContent = difference;
    differenceElement.className = 'stat-value difference-value ' + (difference >= 0 ? 'positive' : 'negative');
    
    // Kliknięcia
    document.getElementById('left-clicks').textContent = leftClicks;
    document.getElementById('left-clicks-percentage').textContent = `${((leftClicks / (leftClicks + rightClicks)) * 100).toFixed(1)}%`;
    
    document.getElementById('right-clicks').textContent = rightClicks;
    document.getElementById('right-clicks-percentage').textContent = `${((rightClicks / (leftClicks + rightClicks)) * 100).toFixed(1)}%`;
    
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
    const response = await fetchWithAuth('/api/images/ranking');
    
    if (!response.ok) {
        throw new Error('Nie można załadować rankingu obrazów');
    }
    
    const ranking = await response.json();
    updateGlobalStimuliRanking(ranking);
}

// Aktualizacja rankingu globalnego obrazów
function updateGlobalStimuliRanking(ranking) {
    const rankingContainer = document.getElementById('global-stimulus-ranking');
    rankingContainer.innerHTML = '';
    
    if (!ranking || ranking.length === 0) {
        rankingContainer.innerHTML = '<p>Brak danych rankingowych.</p>';
        return;
    }
    
    // Ogranicz do 20 najlepszych
    const topRanking = ranking.slice(0, 20);
    
    // Stwórz elementy rankingu
    topRanking.forEach((item, index) => {
        const stimulusElement = document.createElement('div');
        stimulusElement.className = 'stimulus-rank-item';
        
        const profit = ((item.total_profit_factor - 1) * 100).toFixed(2);
        
        stimulusElement.innerHTML = `
            <div class="stimulus-rank-number">${index + 1}</div>
            <div class="stimulus-rank-image">
                <img src="/api/images/${item.id}/thumbnail" alt="Bodziec #${item.id}">
            </div>
            <div class="stimulus-rank-details">
                <div class="stimulus-id">ID: ${item.id}</div>
                <div class="stimulus-success-count">Sukcesów: ${item.total_successes}</div>
                <div class="stimulus-profit">Zysk: ${profit}%</div>
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
        const response = await fetchWithAuth(`/api/genealogy/${type}`);
        
        if (!response.ok) {
            throw new Error('Nie można załadować danych genealogii');
        }
        
        const genealogyData = await response.json();
        updateGenealogyView(genealogyData);
        
        hideLoadingOverlay();
    } catch (error) {
        console.error('Błąd ładowania genealogii:', error);
        alert(`Błąd: ${error.message}`);
        hideLoadingOverlay();
    }
}

// Aktualizacja widoku genealogii
function updateGenealogyView(genealogyData) {
    const genealogyContainer = document.getElementById('genealogy-container');
    genealogyContainer.innerHTML = '';
    
    if (!genealogyData || genealogyData.length === 0) {
        genealogyContainer.innerHTML = '<p>Brak danych genealogicznych.</p>';
        return;
    }
    
    // Stwórz strukturę drzewa genealogicznego
    const treeContainer = document.createElement('div');
    treeContainer.className = 'genealogy-tree';
    
    // Wyszukaj wszystkie korzenie (obrazy bez rodziców)
    const rootNodes = genealogyData.filter(item => !item.parent);
    
    // Buduj drzewo
    rootNodes.forEach(root => {
        const rootElement = createGenealogyNode(root, genealogyData);
        treeContainer.appendChild(rootElement);
    });
    
    genealogyContainer.appendChild(treeContainer);
}

// Tworzenie węzła drzewa genealogicznego
function createGenealogyNode(node, allNodes) {
    const nodeElement = document.createElement('div');
    nodeElement.className = 'genealogy-node';
    
    // Stwórz zawartość węzła
    const profit = ((node.profit_factor - 1) * 100).toFixed(2);
    
    nodeElement.innerHTML = `
        <div class="genealogy-node-content">
            <div class="node-image">
                <img src="/api/images/${node.id}/thumbnail" alt="Bodziec #${node.id}">
            </div>
            <div class="node-details">
                <div>ID: ${node.id}</div>
                <div>Sukcesów: ${node.successes}</div>
                <div>Zysk: ${profit}%</div>
                <div>Pochodzenie: ${translateOrigin(node.origin)}</div>
            </div>
        </div>
    `;
    
    // Znajdź wszystkie dzieci tego węzła
    const children = allNodes.filter(item => item.parent === node.id);
    
    if (children.length > 0) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'genealogy-children';
        
        children.forEach(child => {
            const childElement = createGenealogyNode(child, allNodes);
            childrenContainer.appendChild(childElement);
        });
        
        nodeElement.appendChild(childrenContainer);
    }
    
    return nodeElement;
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