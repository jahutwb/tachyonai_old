# Specyfikacja Aplikacji tachyonai – Wersja SQLite + Algorytm Quasi-Genetyczny (Szczegółowa)

**Niniejszy dokument opisuje finalną wersję specyfikacji dla aplikacji tachyonai, uwzględniając przechowywanie danych w SQLite, konieczność zachowania algorytmu quasi-genetycznego w niezmienionej (bądź nawet bardziej rozwiniętej) formie, możliwość pracy w trybie rzeczywistym (monitorowanie ceny BTC z Binance) lub w trybie symulacji, oraz śledzenie genealogii bodźców jedynie w polach JSON (bez `parent_id` w tabeli `images`).**

---

## Spis Treści
1. [Założenia i Cel](#1-założenia-i-cel)  
2. [Architektura i Model Danych (SQLite)](#2-architektura-i-model-danych-sqlite)  
3. [Przebieg Gry (Workflow)](#3-przebieg-gry-workflow)  
4. [Algorytm Quasi-Genetyczny (Kluczowy Element)](#4-algorytm-quasi-genetyczny-kluczowy-element)  
5. [Interfejs Użytkownika (UX)](#5-interfejs-użytkownika-ux)  
6. [Monitorowanie BTC i Tryb Symulacji](#6-monitorowanie-btc-i-tryb-symulacji)  
7. [Wdrażanie i Testy – Środowisko Dev](#7-wdrażanie-i-testy-–-środowisko-dev)  
8. [Logowanie i Genealogia Bodźców](#8-logowanie-i-genealogia-bodźców)  
9. [Podsumowanie](#9-podsumowanie)

---

## 1. Założenia i Cel

1. **Ukryte przewidywanie kursu BTC**  
   - Użytkownik ma do dyspozycji dwie „kurtyny”, nie wiedząc, która oznacza BUY, a która SELL.  
   - Aplikacja w sposób ukryty łączy wybór użytkownika z kupnem bądź sprzedażą, po czym sprawdza rzeczywisty (lub symulowany) ruch ceny.

2. **Pule Obrazów i Sesje**  
   - W każdej sesji użytkownik otrzymuje pulę pozytywnych (pos) i negatywnych (neg) obrazów.  
   - Przy sukcesie (trafienie ruchu BTC) wyświetla się obraz pozytywny i oba obrazy zostają, przy porażce – obraz negatywny i oba obrazy znikają z puli.

3. **Algorytm Quasi-Genetyczny**  
   - Po zakończeniu sesji (wyczerpaniu puli) generujemy nową pulę, uwzględniając sukcesy i embeddingi.  
   - W polach JSON `pos_pool_json` / `neg_pool_json` trzymamy również informacje genealogiczne: `\"parent\": <id>`, `\"origin\": \"child\" | \"bought\" | \"random\"`.

4. **SQLite**  
   - Dla prostoty implementacji MVP – wykorzystujemy bazę SQLite zamiast Postgresa.  
   - Pozwala to łatwiej wdrożyć i testować aplikację, zarówno lokalnie, jak i w chmurze, bez konieczności instalacji serwera DB.

---

## 2. Architektura i Model Danych (SQLite)

### 2.1 Uproszczone Tabele

#### Tabela `users`
- **id** (PK, Integer)  
- **username** (String, unikalny)  
- **password_hash** (String)  
- **created_at**, **updated_at**

#### Tabela `images`
- **id** (PK, Integer)  
- **path** (String)  
- **type** (Enum: `POSITIVE` / `NEGATIVE`)  
- **embedding** (JSON) – wektor cech (np. CLIP)  
- **img_metadata** (JSON, opcjonalnie)  
- **total_successes** (Integer, default=0)  
- **total_failures** (Integer, default=0)  
- **total_profit_factor** (Float, default=1.0)  
- **created_at**, **updated_at**

> Po każdej rundzie, jeżeli obraz brał udział, mnożymy:
> ```
> total_profit_factor *= (1 + profit_fraction)
> ```
> (Tak samo dla pozytywnych i negatywnych bodźców.)

#### Tabela `sessions`
- **id** (PK, Integer)  
- **user_id** (FK -> users.id)  
- **status** (Enum: `ACTIVE`, `COMPLETED`, `ABANDONED`)  
- **pos_pool_json** (JSON) – Struktura zawierająca ID bodźców, ich liczniki sukcesów/porażek, `\"parent\"` (jeśli origin=child), `\"origin\"` = child/bought/random  
- **neg_pool_json** (JSON) – Analogicznie dla neg  
- **session_profit_factor** (Float, default=1.0)  
- **remaining_pairs** (Integer, default=6)  
- **started_at**, **ended_at**

#### Tabela `rounds`
- **id** (PK, Integer)  
- **session_id** (FK -> sessions.id)  
- **round_number** (Integer)  
- **pos_image_id**, **neg_image_id** (FK -> images.id)  
- **user_choice_side** (Enum: `LEFT` / `RIGHT`)  
- **user_action** (Enum: `BUY` / `SELL`)  
- **start_price**, **end_price** (Float)  
- **profit_fraction** (Float)  
- **result** (Enum: `SUCCESS` / `FAILURE`)  
- **response_time** (Float, optional)  
- **created_at**, **completed_at**

> Nie przechowujemy `parent_id` w `images` – genealogia jest wyłącznie w polu JSON w `sessions`.

## 2.2 Dane wejściowe i system etykietowania

### Struktura katalogów danych

W projekcie wykorzystywane są dane obrazowe podzielone na dwie główne klasy:
- **Pozytywne bodźce (`pos`)**: materiały pobudzające, o charakterze erotycznym.
- **Negatywne bodźce (`neg`)**: neutralne, nieseksualne obrazy, używane jako kontrast/bodźce kontrolne.

---

### Katalog `pos`

- Ścieżka: `/home/jahu/PycharmProjects/tachyonai2/data/pos`
- Zawiera dwa podfoldery:
  - `freeones` — każdy podfolder to galeria (nazwa = tytuł), zawiera obrazy oraz plik `metadata.json`.
  - `rule34` — pojedyncze obrazy `.jpg` (bez folderów).

#### Przykład metadanych `freeones/metadata.json`:
```json
{
  "Gallery URL": "https://...",
  "Cast": ["Black Angel"],
  "Categories": ["Anal", "Big Butt"],
  "Tags": ["Pregnant", "Lingerie", "Blue Eyes"],
  "Number of Photos": 12
}
```

#### Wymagania:
- Wszystkie obrazy z `freeones` oraz `rule34` będą klasyfikowane jako pozytywne bodźce.
- Metadane (`Tags`, `Categories`, `Cast`) będą automatycznie wczytywane do pola `img_metadata` w bazie danych (`images`).
- Jeśli obrazy pochodzą z `rule34`, a nie mają metadanych — pole `img_metadata` pozostaje puste lub zawiera tylko automatycznie wykryte tagi (jeśli zostanie dodane tagowanie przez AI).

---

### Katalog `neg`

- Ścieżka: `/home/jahu/PycharmProjects/tachyonai2/data/neg`
- Dane pochodzą z **Open Images V7** i znajdują się m.in. w:
  - `test/data`
  - `validation/data`

Metadane znajdują się w:
- `metadata/classes.csv`
- `metadata/image_ids.csv`
- `labels/classifications.csv`
- `labels/detections.csv`

#### Wymagania:
- Obrazy kwalifikowane jako **negatywne** muszą spełniać warunek: **brak ludzi** na zdjęciu.
  - Identyfikacja ludzi opiera się na danych klasyfikacyjnych (`Person`, `Man`, `Woman`, itp.) w plikach `classes.csv` oraz `detections.csv`.
  - Obrazy zawierające ludzi muszą być **filtrowane i wykluczane** z dalszego użycia.
- Obrazy z odpowiednich kategorii (np. `Plant`, `Object`, `Building`, `Food`) mogą zostać zaakceptowane jako negatywne.
- Tagi/kategorie ze zbioru `Open Images` będą również mapowane do pola `img_metadata` w bazie (`images`), jeśli są dostępne.

---

### Uwagi implementacyjne

- Konieczne będzie stworzenie skryptu importującego dane z katalogów `pos` i `neg` do bazy danych (`images`), wraz z metadanymi.
- Dla każdego obrazu należy zarejestrować:
  - `path`: pełna ścieżka do pliku
  - `type`: `POSITIVE` / `NEGATIVE`
  - `img_metadata`: obiekt JSON z tagami, kategoriami, obsadą (jeśli dotyczy)
  - `embedding`: generowany później w procesie embeddingowania (opcjonalny FAISS)
- Obrazy z niepoprawnymi metadanymi lub niezgodne z kryteriami (np. obecność ludzi w `neg`) powinny być pomijane i logowane.
---

---

## 3. Przebieg Gry (Workflow)

1. **Strona Startowa**:  
   - User klika „Rozpocznij grę”; backend sprawdza, czy jest niedokończona sesja (`ACTIVE`).  
   - Jeśli nie ma – tworzy nową (6 pos, 6 neg) lub stosuje algorytm quasi-genetyczny, jeśli poprzednia sesja jest `COMPLETED`.  
   - `pos_pool_json` i `neg_pool_json` zawierają listę bodźców z polami `{ \"id\": <int>, \"successes\": <int>, \"failures\": <int>, \"origin\": \"child\"|\"bought\"|\"random\", \"parent\": <int> (opcjonalne) }`.

2. **Rundy**:  
   - Przy każdej rundzie losujemy 1 pos i 1 neg (niewyeliminowane). Losowo przypisujemy lewą/prawą kurtynę do BUY/SELL.  
   - User klika kurtynę → rejestrujemy `start_price` i czekamy na zmianę.  
   - Gdy cena się zmieni → `end_price`, `profit_fraction`. Jeżeli `profit_fraction > 0`, success, w przeciwnym razie failure.  
   - Przy success – pokazujemy obraz pozytywny i oba bodźce zostają w puli; przy failure – obraz negatywny i oba usuwamy z puli (`remaining_pairs--`).

3. **Podsumowanie**:  
   - Gdy pula się wyczerpie (`remaining_pairs=0`), `status=COMPLETED`.  
   - Wyświetlamy statystyki sesji, wykres, ranking, itp.  
   - Jednocześnie uruchamia się algorytm quasi-genetyczny, żeby wygenerować nową pulę.  
   - W polu `pos_pool_json` / `neg_pool_json` nowej sesji przechowujemy info genealogiczne o nowych bodźcach.

4. **Wznawianie**:  
   - Jeżeli sesja jest w trakcie (`ACTIVE`), ładujemy JSON z puli i kontynuujemy.

---

## 4. Algorytm Quasi-Genetyczny (Kluczowy Element)


### 4.1 Podstawy

- **Cel**: Na koniec sesji (gdy `status=COMPLETED`) tworzymy nową pulę (np. 6 pos, 6 neg) w oparciu o dotychczasowe wyniki i embeddingi.  
- **Embeddingi**: Każdy obraz ma w polu `embedding` swój wektor (np. z CLIP). Korzystamy z FAISS do najbliższych sąsiadów.  

### 4.2 Sukces Negatywnych (Przetrwanie)

- **Pozytywne**: Sukcesem jest wyświetlenie obrazu przy trafionym wyborze (BTC up -> up, itp.).  
- **Negatywne**: Sukcesem (przetrwaniem) jest bycie w rundzie, w której user trafił, ale się **nie** ujawnił, więc bodziec pozostał w puli.  
- Na koniec mamy liczbę sukcesów dla pos oraz liczbę przetrwań (też nazywamy je sukcesami) dla neg.

### 4.3 Obliczanie Centroidów

1. **Centroid Startowy**: Średnia embeddingów wszystkich bodźców z poprzedniej puli danego typu (np. tych 6 pos wyjściowych).  
2. **Centroid Końcowy**:  
   - **Pozytywne**: Średnia ważona embeddingów obrazów pozytywnych z wagą = liczba sukcesów.  
   - **Negatywne**: Średnia ważona embeddingów obrazów negatywnych z wagą = liczba przetrwań.  
3. **Wektor Różnicy**:  
   - `difference_vector_pos = centroid_end_pos - centroid_start_pos`  
   - `difference_vector_neg = centroid_end_neg - centroid_start_neg`

### 4.4 Ranking Bodźców

1. Dla pozytywnych: sortujemy obrazy malejąco wg liczby sukcesów (>=1).  
2. Dla negatywnych: analogicznie sortujemy wg liczby przetrwań (>=1).  
3. Bodziec z 0 sukcesów/przetrwań nie trafia do rankingu.

### 4.5 Liczba Sukcesów a Rozmiar Puli

Załóżmy `num_pairs = 6`.

- **S** = łączna liczba sukcesów (pos) lub przetrwań (neg).  
- **Przypadek A**: `S > num_pairs`  
  1. `points = S - num_pairs`.  
  2. Idziemy po rankingu: „kupujemy” bodziec, płacąc liczbą jego sukcesów. Nawet jeśli bodziec ma success_count > points, i tak go bierzemy.  
  3. Odejmuje się od `points` wartość success_count tego bodźca. Gdy `points <= 0`, przestajemy kupować.  
  4. Uzyskaliśmy pewną liczbę bodźców – tyle, ile mamy slotów lub mniej. Jeśli nie zapełniliśmy 6, resztę możemy wypełnić dziećmi (patrz generowanie dzieci).  
- **Przypadek B**: `S <= num_pairs`  
  1. Generujemy tyle dzieci, ile wynosi `S`.  
  2. Pozostałe (num_pairs - S) sloty uzupełniamy losowo.

### 4.6 Generowanie Dzieci

1. **Liczba dzieci** jest obliczana zależnie od S i rankingu.  
2. **Rozdzielanie**:  
   - Mamy np. 11 dzieci do stworzenia i 4 rodziców.  
   - Każdy rodzic dostaje `11 // 4 = 2` dzieci, plus 3 najlepszych dostaje jeszcze po 1 dziecku (reszta=3).  
3. **Krok generowania**:  
   1. Dla rodzica (embedding `parent_vec`), obliczamy `child_vec = parent_vec + difference_vector_pos` (lub `_neg`).  
   2. Korzystamy z FAISS do znalezienia najbliższego obrazu w przestrzeni embeddingów.  
   3. Jeśli wylosowany obraz = rodzic lub jest już w puli / poprzedniej puli, powtarzamy (lub dodajemy drobny szum).  
   4. Do `pos_pool_json` (lub `neg_pool_json`) nowej sesji dopisujemy element:  
      ```json
      {
        "id": <child_image_id>,
        "successes": 0,
        "failures": 0,
        "origin": "child",
        "parent": <parent_image_id>
      }
      ```
4. **Mechanizm awaryjny**:  
   - Jeśli FAISS nie zwraca kandydata innego niż rodzic, można wydłużyć wektor różnicy (`child_vec += alpha * difference_vector_pos`) lub dodać losowy offset.

---

## 5. Interfejs Użytkownika (UX)

(Szczegółowo opisany w dokumencie `ui_specification.md`, z krótkim streszczeniem tutaj.)

1. **Zintegrowany front i back** (FastAPI + Jinja2).  
2. **Główne ekrany**: strona startowa, rozgrywka (2 kurtyny), podsumowanie sesji, statystyki globalne.  
3. **Animacje**:  
   - Kurtyny rozszerzające się, overlay ładowania przy generowaniu puli.  
4. **Statystyki genealogiczne**:  
   - Tylko w JSON puli. Możemy wizualizować w panelu statystyk (listy rodzic → dzieci).

---

## 6. Monitorowanie BTC i Tryb Symulacji

1. **Realne Dane (np. Binance)**  
   - Co ~2–3 sek. odpytywanie `GET https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT`.  
   - Jeśli zmiana kursu >= pewien minimalny próg (np. 0.0001%), ustalamy `end_price` i kończymy rundę.  
2. **Tryb Symulacji**  
   - Po kliknięciu kurtyny rejestrujemy `start_price`.  
   - Co 1 sek. losujemy drobną zmianę (np. ±0.001–0.003%). Gdy tylko pojawi się zmiana, ustalamy `end_price` i sprawdzamy success/failure.  
   - Alternatywnie generujemy jednorazowo ±0.1% w ciągu 1–2 sekund, aby szybko zamknąć rundę.

W pliku `.env` możemy mieć `REAL_BTC_PRICE=false`/`true`, wybierając odpowiedni tryb.

---

## 7. Wdrażanie i Testy – Środowisko Dev

1. **Jedno środowisko**:  
   - Plik `.env` z parametrami (np. `DATABASE_URL=sqlite:///tachyonai.db`).  
   - Minimalny deployment (np. na Railway, Heroku, bądź hosting VPS).  
2. **Testy manualne** lub podstawowe testy integracyjne.  
   - E2E i CI można rozbudować w kolejnych iteracjach.

---

## 8. Logowanie i Genealogia Bodźców

1. **Rejestracja / Logowanie**  
   - Endpointy: `/signup`, `/login`.  
   - Bcrypt do hashowania haseł, JWT w localStorage (lub session cookie).  
   - Wymagane do kojarzenia, który użytkownik generuje kolejne sesje i w jaki sposób algorytm ich prowadzi.  
2. **Genealogia**  
   - Nie ma `parent_id` w `images`.  
   - W polach `pos_pool_json`, `neg_pool_json` nowej sesji dopisujemy `\"origin\": \"child\"` i `\"parent\": <id_rodzica>` tylko dla bodźców wygenerowanych przez przesunięcie wektora.  
   - Dla bodźców kupionych i wylosowanych: `\"origin\": \"bought\"` lub `\"origin\": \"random\"`, bez `\"parent\"`.  

---

## 9. Podsumowanie

1. **Baza SQLite** – prosta w użyciu, minimalna konfiguracja.  
2. **Algorytm Quasi-Genetyczny** – w pełni zachowany z poprzednich specyfikacji, łącznie z obliczaniem centroidów i generowaniem dzieci z FAISS.  
3. **Genealogia Tylko w JSON** – brak `parent_id` w `images`, wszelka informacja o pochodzeniu w `pos_pool_json` i `neg_pool_json`.  
4. **Monitorowanie Ceny** – realne z Binance lub symulacja ± niewielki % co sekundę.  
5. **Jedno Środowisko Dev** – brak większego podziału, szybkie wdrożenie w chmurze (np. Railway/Heroku) w formie MVP.  
6. **Logowanie** – aby analizować, jak algorytm prowadzi poszczególnych użytkowników w kolejnych sesjach.  

