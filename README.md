# TachyonAI - legacy prototype

## Portfolio overview

An experimental Python/FastAPI application exploring adaptive user sessions, persistent state and feedback-driven selection logic. This repository is an older public development snapshot; the active version is maintained separately.

The code is intentionally preserved as a prototype rather than presented as a polished production package.

**Core stack:** Python, FastAPI, pytest, HTML/JavaScript frontend.

---

Aplikacja do ukrytego przewidywania kursu BTC z wykorzystaniem algorytmu quasi-genetycznego.

## Opis

TachyonAI to aplikacja, która w sposób ukryty łączy wybory użytkownika z operacjami kupna lub sprzedaży BTC, a następnie sprawdza rzeczywisty (lub symulowany) ruch ceny. Aplikacja wykorzystuje algorytm quasi-genetyczny do generowania i ewolucji bodźców wizualnych.

## Instalacja

1. Sklonuj repozytorium:
```bash
git clone git@github.com:jahutwb/tachyonai.git
cd tachyonai
```

2. Utwórz i aktywuj wirtualne środowisko Python:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# lub
venv\Scripts\activate  # Windows
```

3. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

4. Skopiuj plik `.env.example` do `.env` i dostosuj ustawienia:
```bash
cp .env.example .env
```

## Uruchomienie

```bash
uvicorn backend.main:app --reload
```

Aplikacja będzie dostępna pod adresem `http://localhost:8000`.

## Testy

```bash
pytest
```

## Struktura projektu

- `/backend` - pliki Pythona (modele, routery endpointów)
- `/frontend` - pliki statyczne, szablony Jinja2
- `/data` - dane obrazów (nie dołączone do repozytorium)
- `/docs` - dokumentacja
- `/tests` - testy

## Licencja

Ten projekt jest własnością prywatną i nie podlega redystrybucji bez zgody autora. 