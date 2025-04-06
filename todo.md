# TODO: Lista Zadań dla Projektu tachyonai

Poniższa lista to **inkrementalny plan** rozwoju projektu tachyonai (repo: [https://github.com/jahutwb/tachyonai](https://github.com/jahutwb/tachyonai)) w oparciu o pliki **specification.md** oraz **ui_specification.md**. Każdy punkt można realizować i testować osobno, aby kolejne commity w repo utrzymywały stabilność kodu.

---

## 1. Przygotowanie Środowiska

- [x] **1.1. Stworzenie wirtualnego środowiska (venv)**
  - `python -m venv venv`
  - Dopisać `venv/` do `.gitignore`.
- [x] **1.2. Instalacja zależności**
  - W pliku `requirements.txt`:  
    - `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`
    - `bcrypt` (hasła), `faiss` (embeddingi), ewentualnie `clip` lub inny pakiet
    - Narzędzia testowe (`pytest`, `pytest-asyncio`, itp.)
- [x] **1.3. Plik `.env` i konfiguracja**
  - `DATABASE_URL=sqlite:///tachyonai.db`
  - `REAL_BTC_PRICE=true/false` (wybór trybu)
  - Inne zmienne (np. JWT_SECRET)

---

## 2. Struktura Kodu i Modele (SQLite)

- [x] **2.1. Utworzenie głównej struktury katalogów**
  - `/backend` – pliki Pythona (np. `main.py`, modele, routery endpointów)
  - `/frontend` – pliki statyczne bądź integracja z Jinja2
  - `/data` – istniejąca struktura obrazów pos/neg
  - `/docs` – `specification.md`, `ui_specification.md`
- [x] **2.2. Modele bazy SQLite**  
  - `users`, `images`, `sessions`, `rounds` (zgodnie z specification.md), bez `parent_id` w `images`
  - Zdefiniować w stylu SQLAlchemy + migracja bądź skrypt do tworzenia tabel
- [x] **2.3. Inicjalizacja DB**  
  - Skrypt `init_db.py` lub funkcja startowa w `main.py`, tworząca `tachyonai.db`

---

## 3. Import Danych (pos/neg)

- [x] **3.1. Skrypt wczytujący obrazy pozytywne**  
  - Z katalogów `/data/pos/freeones` i `/data/pos/rule34`
  - Zapis w tabeli `images`, `type=POSITIVE`, metadane do `img_metadata`
- [x] **3.2. Skrypt wczytujący obrazy negatywne**  
  - Z `/data/neg/...`, filtrowanie metadanych (presence of Person)
  - `type=NEGATIVE` w bazie
- [x] **3.3. Generowanie embeddingów (CLIP)**  
  - Tworzenie `embedding` w formacie JSON
  - Można użyć offline lub w locie
- [x] **3.4. Indeks FAISS** (opcjonalnie na tym etapie)  
  - Utworzyć indeks, w którym będą embeddingi wszystkich `images`

---

## 4. Logika Rozgrywki (Backend)

- [x] **4.1. Endpointy logowania**  
  - `/signup`, `/login` (hashowanie haseł – `bcrypt`, zwracanie JWT lub cookie)
- [x] **4.2. Tworzenie / Wznawianie Sesji**  
  - `POST /api/sessions` (tworzy nową sesję lub wznawia `ACTIVE`)
  - Ustawia `pos_pool_json` i `neg_pool_json` (6 pos, 6 neg, lub więcej)
- [x] **4.3. Rundy**  
  - `GET /api/rounds/next` – pobranie pary (pos, neg)
  - `POST /api/rounds/choice` – user klika kurtynę → rejestr `start_price`, czekanie na zmianę, `end_price`, success/failure → update bazy
- [x] **4.4. Podsumowanie**  
  - `GET /api/sessions/{id}/summary` – liczba sukcesów, porażek, final profit, wykres, itp.
  - Przycisk „Nowa sesja" → wywołanie algorytmu quasi-genetycznego

---

## 5. Algorytm Quasi-Genetyczny (Kluczowy Element)

*(Przepisany zgodnie z specification.md, z zachowaniem szczegółowości)*

- [x] **5.1. Obliczanie sukcesów (pos) i przetrwań (neg)**  
  - Po zakończeniu sesji – liczymy success_count i 'przetrwanie' (neg.)
- [x] **5.2. Obliczanie centroidów**  
  - `centroid_start_pos`, `centroid_end_pos` (ważone wagą successów)
  - `difference_vector_pos = centroid_end_pos - centroid_start_pos`
  - Analogicznie dla neg
- [x] **5.3. Ranking**  
  - Sort malejąco wg success_count >=1 (pos) / przetrwań >=1 (neg)
- [x] **5.4. Dobór puli**  
  - **Przypadek A**: `S > num_pairs` – `points = S - num_pairs`, kupowanie bodźców, reszta dzieci  
  - **Przypadek B**: `S <= num_pairs` – generacja S dzieci, reszta losowa
- [x] **5.5. Generowanie dzieci (FAISS)**  
  - `child_vec = parent_vec + difference_vector_pos` (lub neg)
  - `faiss` → nearest neighbor
  - Odrzucamy duplikaty / dodajemy szum
  - Zapis w JSON: `"origin": "child", "parent": <rodzic_id>`

---

## 6. Testy Jednostkowe i Integracyjne

- [x] **6.1. Testy Jednostkowe (pytest)**  
  - Sprawdzić modele, funkcje obliczające centroidy, difference_vector
  - Test rankingu i generowania dzieci w trybie offline (bez API)
- [ ] **6.2. Testy Integracyjne**  
  - Endpointy `/api/sessions`, `/api/rounds`, `/api/users` (rejestracja, logowanie)
  - Sprawdzić poprawne tworzenie nowej sesji, rund, finalne statystyki
- [x] **6.3. Testy FAISS**  
  - Upewnić się, że nearest neighbor faktycznie znajduje poprawnych kandydatów
  - Przykładowe embeddingi + test na duplikaty

---

## 7. Interfejs Użytkownika (Zintegrowany)

*(Zgodnie z ui_specification.md)*

- [ ] **7.1. Główne widoki**  
  - Strona startowa, ekran rozgrywki (2 kurtyny), podsumowanie sesji, statystyki globalne
- [ ] **7.2. Animacje**  
  - Rozszerzanie kurtyny, overlay przy ładowaniu, spinner w trakcie oczekiwania
- [ ] **7.3. Pasek statystyk** (dolny)  
  - Sukcesy, porażki, `(session_profit_factor - 1)*100%`, `remaining_pairs`
- [ ] **7.4. Panel genealogii**  
  - Lista parent→child dla pos/neg, bazując na JSON (`origin`, `parent`)

---

## 8. Monitorowanie BTC i Tryb Symulacji

- [x] **8.1. Realne dane (Binance)**  
  - Co 2–3 sek. odpytywać endpoint (np. `/api/rounds/price`?), wewnątrz backendu → binance.com
  - Przy minimalnej zmianie kończymy rundę
- [x] **8.2. Symulacja**  
  - Co 1 sek. ±(0.001–0.003)%. Po wykryciu pierwszej zmiany → ustalamy end_price
  - Ewentualnie jednorazowy jump ±0.1% w ~2s

---

## 9. Wdrażanie i Praca w Trybie Dev

- [x] **9.1. requirements.txt**  
  - Wrzucić zależności
- [x] **9.2. Uruchamianie**  
  - `uvicorn backend.main:app --reload` z `DATABASE_URL=sqlite:///tachyonai.db`
- [ ] **9.3. Testy i Commity**  
  - Po każdym kroku sprawdzić testy jednostkowe/integracyjne
  - Commit z krótkim opisem
- [ ] **9.4. Ewentualny Deploy** (Heroku/Railway)  
  - Jeden plik `.env`, brak rozbudowanych środowisk

---

## 10. Logowanie Użytkowników i Śledzenie Bodźców

- [x] **10.1. Logowanie/Rejestracja**  
  - `/signup`, `/login` → sprawdzenie unikalności username, bcrypt hasło
  - Przechowywanie JWT w localStorage lub session cookie
- [x] **10.2. Powiązanie sesji z userem**  
  - `sessions.user_id` → który user tworzy sesję
- [x] **10.3. Genealogia**  
  - Tylko w `pos_pool_json` i `neg_pool_json`, `"origin": "child", "parent": <id>"` jeśli wektor przesunięcia
  - `"origin": "bought"` i `"random"` dla reszty
  - Ewentualne wyświetlanie w globalnym panelu statystyk

---

## Podsumowanie aktualnego stanu

1. **Zakończone prace:**
   - Środowisko deweloperskie jest w pełni skonfigurowane (venv, wymagane pakiety)
   - Struktura bazy danych i inicjalizacja
   - Import danych i generowanie embeddingów
   - Algorytm quasi-genetyczny dla puli obrazów
   - Logika sesji i rund
   - Monitorowanie BTC (tryb rzeczywisty i symulacja)
   - Logowanie użytkowników i śledzenie bodźców

2. **W trakcie realizacji:**
   - Testy integracyjne (6.2)
   - Pełny interfejs użytkownika (punkty 7.1-7.4)

3. **Następne kroki:**
   - Dokończenie testów integracyjnych
   - Implementacja interfejsu użytkownika
   - Przygotowanie do ewentualnego deploy

Aktualne postępy stanowią około 80% całego projektu. Głównym brakującym elementem jest pełny interfejs użytkownika oraz dodatkowe testy integracyjne.

