// Funkcje pomocnicze do obsługi localStorage
function saveToken(token) {
    localStorage.setItem('token', token);
}

function getToken() {
    return localStorage.getItem('token');
}

function removeToken() {
    localStorage.removeItem('token');
}

function saveUsername(username) {
    localStorage.setItem('username', username);
}

function getUsername() {
    return localStorage.getItem('username');
}

function removeUsername() {
    localStorage.removeItem('username');
}

// Sprawdzenie, czy użytkownik jest zalogowany
function isLoggedIn() {
    return !!getToken();
}

// Funkcja do wyświetlania komunikatów o błędach w formularzu
function showError(formId, message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    // Usuń wcześniejsze komunikaty o błędach
    const existingErrors = document.querySelectorAll(`#${formId} .error-message`);
    existingErrors.forEach(el => el.remove());
    
    // Dodaj nowy komunikat o błędzie
    const form = document.getElementById(formId);
    form.prepend(errorDiv);
    
    // Dodatkowo pokaż alert dla użytkownika
    alert(message);
}

// Aktualizacja widoku na podstawie stanu zalogowania
function updateAuthView() {
    const loginButton = document.getElementById('login-button');
    const registerButton = document.getElementById('register-button');
    const logoutButton = document.getElementById('logout-button');
    const usernameDisplay = document.getElementById('username-display');

    if (isLoggedIn()) {
        loginButton.style.display = 'none';
        registerButton.style.display = 'none';
        logoutButton.style.display = 'inline-block';
        usernameDisplay.textContent = `Witaj, ${getUsername()}!`;
    } else {
        loginButton.style.display = 'inline-block';
        registerButton.style.display = 'inline-block';
        logoutButton.style.display = 'none';
        usernameDisplay.textContent = '';
    }
}

// Obsługa formularza logowania
async function login(username, password) {
    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch('/token', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            const errorMessage = errorData.detail || 'Błąd logowania';
            showError('login-form', errorMessage);
            return false;
        }

        const data = await response.json();
        saveToken(data.access_token);
        saveUsername(username);
        updateAuthView();
        
        // Zamknij modal logowania
        const loginModal = document.getElementById('login-modal');
        loginModal.style.display = 'none';
        
        return true;
    } catch (error) {
        console.error('Błąd logowania:', error);
        showError('login-form', `Błąd logowania: ${error.message}`);
        return false;
    }
}

// Obsługa formularza rejestracji
async function register(username, password) {
    try {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                password
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            const errorMessage = errorData.detail || 'Błąd rejestracji';
            showError('register-form', errorMessage);
            return false;
        }

        const data = await response.json();
        showError('register-form', 'Rejestracja zakończona pomyślnie. Możesz się teraz zalogować.');
        
        // Zamknij modal rejestracji
        const registerModal = document.getElementById('register-modal');
        registerModal.style.display = 'none';
        
        // Otwórz modal logowania
        const loginModal = document.getElementById('login-modal');
        loginModal.style.display = 'block';
        
        return true;
    } catch (error) {
        console.error('Błąd rejestracji:', error);
        showError('register-form', `Błąd rejestracji: ${error.message}`);
        return false;
    }
}

// Wylogowanie
function logout() {
    removeToken();
    removeUsername();
    updateAuthView();
    window.location.href = '/';
}

// Inicjalizacja po załadowaniu strony
document.addEventListener('DOMContentLoaded', () => {
    // Aktualizacja widoku na podstawie stanu zalogowania
    updateAuthView();

    // Obsługa modala logowania
    const loginButton = document.getElementById('login-button');
    const loginModal = document.getElementById('login-modal');
    const loginForm = document.getElementById('login-form');
    const loginCloseButton = loginModal.querySelector('.close');

    loginButton.addEventListener('click', () => {
        loginModal.style.display = 'block';
    });

    loginCloseButton.addEventListener('click', () => {
        loginModal.style.display = 'none';
    });

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        await login(username, password);
    });

    // Obsługa modala rejestracji
    const registerButton = document.getElementById('register-button');
    const registerModal = document.getElementById('register-modal');
    const registerForm = document.getElementById('register-form');
    const registerCloseButton = registerModal.querySelector('.close');

    registerButton.addEventListener('click', () => {
        registerModal.style.display = 'block';
    });

    registerCloseButton.addEventListener('click', () => {
        registerModal.style.display = 'none';
    });

    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('register-username').value;
        const password = document.getElementById('register-password').value;
        const confirmPassword = document.getElementById('register-confirm-password').value;

        if (password !== confirmPassword) {
            showError('register-form', 'Hasła nie są zgodne!');
            return;
        }

        await register(username, password);
    });

    // Obsługa przycisku wylogowania
    const logoutButton = document.getElementById('logout-button');
    logoutButton.addEventListener('click', logout);

    // Zamykanie modali po kliknięciu poza ich zawartością
    window.addEventListener('click', (e) => {
        if (e.target === loginModal) {
            loginModal.style.display = 'none';
        }
        if (e.target === registerModal) {
            registerModal.style.display = 'none';
        }
    });
}); 