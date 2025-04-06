# Specyfikacja Interfejsu Użytkownika (UI) – tachyonai

**Niniejszy dokument uzupełnia główną specyfikację aplikacji tachyonai, koncentrując się na wyglądzie, interakcjach i architekturze interfejsu użytkownika. Uwzględnia także rozszerzenia statystyk globalnych, w tym genealogię bodźców i dodatkowe wykresy skuteczności.**

---

## Spis Treści
1. [Cele i Założenia Wizualne](#1-cele-i-założenia-wizualne)  
2. [Kolorystyka i Elementy Stylu](#2-kolorystyka-i-elementy-stylu)  
3. [Struktura i Layout Ekranów](#3-struktura-i-layout-ekranów)  
4. [Interakcje i Animacje](#4-interakcje-i-animacje)  
5. [Widoki i Scenariusze](#5-widoki-i-scenariusze)  
   - 5.1 Strona Startowa  
   - 5.2 Logowanie/Rejestracja (Navbar)  
   - 5.3 Rozgrywka (Ekran Główny Sesji)  
   - 5.4 Podsumowanie Sesji  
   - 5.5 Statystyki Globalne  
     - 5.5.1 Wykres całkowitego bogactwa sesji  
     - 5.5.2 Wykresy skuteczności w zależności od pory dnia  
     - 5.5.3 Genealogia Bodźców  
6. [Obsługa Błędów i Timeoutów](#6-obsługa-błędów-i-timeoutów)  
7. [Podsumowanie](#7-podsumowanie)

---

## 1. Cele i Założenia Wizualne

1. **Nazwa Aplikacji**: tachyonai  
2. **Minimalistyczny styl**:  
   - Większość ekranu wypełniają kluczowe elementy (kurtyny w trakcie gry).  
   - Ograniczona ilość tekstu w głównej rozgrywce.  
3. **Ciemna kolorystyka**:  
   - Tło w odcieniach ciemnych (#1A1A1A–#333333) z fioletowymi akcentami (#7D40FE, #AA80FF).  
4. **Przeznaczenie głównie dla przeglądarek desktop**  
   - Brak dedykowanego layoutu mobilnego w tej wersji.  

---

## 2. Kolorystyka i Elementy Stylu

1. **Główne tło**:  
   - Ciemne (np. #1A1A1A).  
   - Tekst kontrastujący (np. #FFFFFF).  
2. **Akcenty fioletowe**:  
   - Przyciski, linki, elementy interaktywne (np. #7D40FE).  
3. **Font**:  
   - Sans-serif (np. „Open Sans”, „Roboto”).  
   - Rozmiary: ~18px dla treści, ~24px dla nagłówków.  
4. **Styl przycisków**:  
   - Zaokrąglone rogi (4–8px).  
   - Ewentualny hover: jaśniejszy fiolet lub cień.

---

## 3. Struktura i Layout Ekranów

1. **Navbar** (u góry):  
   - Lewa strona: logo/nazwa „tachyonai”.  
   - Prawa strona: „Strona Startowa”, „Statystyki Użytkownika”, „Wyloguj” (+ nazwa zalogowanego użytkownika).
2. **Obszar główny**:  
   - Pod navbarem, wypełnia większość ekranu.  
   - W trakcie gry – dwie kurtyny.  
3. **Pasek Dolny** (footer bar):  
   - Zajmuje dolne ~10–15% wysokości.  
   - Zawiera liczbę sukcesów, porażek, skuteczność (%), skumulowany zysk i liczbę pozostałych par.  
   - Tło półprzezroczyste (#1A1A1A z 80% opacity) i fioletowe akcenty w ikonach/tekście.

---

## 4. Interakcje i Animacje

1. **Kliknięcie Kurtyny**:  
   - Natychmiast rozszerza się (transition: width 0.5s ease), druga znika.  
   - Na środku pojawia się spinner ładowania czekający na zmianę ceny.  
   - Po zmianie ceny → wyświetlamy wynik i bodziec (pozytywny/negatywny).
2. **Overlay Ładowania**:  
   - Przy tworzeniu nowej sesji (z ekranu startowego) lub przycisku „Nowa sesja” w podsumowaniu.  
   - Półprzezroczysty ekran + spinner/progress, ewentualnie opis etapów: „Pobieranie obrazów…”, „Generowanie potomków…”.  
3. **Komunikat Sukces/Porażka**:  
   - Nad dolnym paskiem, np. prostokątny box z krótkim tekstem (SUCCESS/FAILURE) i procentową zmianą `(session_profit_factor - 1)*100%`.

---

## 5. Widoki i Scenariusze

### 5.1 Strona Startowa
- **Zawartość**:  
  - Logo/nazwa „tachyonai” w nagłówku (navbar).  
  - Krótki opis (1–2 zdania).  
  - Przycisk „Rozpocznij grę” w centralnej części.  
- **Po kliknięciu**:  
  - Overlay ładowania: „Tworzenie nowej sesji…”.  
  - Po krótkim czasie → przejście do ekranu głównego sesji (dwóch kurtyn).

### 5.2 Logowanie/Rejestracja (Navbar)
- **Formularze**:  
  - Login i hasło (opcjonalnie e-mail).  
  - Proste style: tło ciemne, przyciski fioletowe.  
- **Po zalogowaniu**:  
  - Zamiast linków „Logowanie/Rejestracja” w navbarze mamy „Wyloguj” i „Witaj, NazwaUżytkownika”.

### 5.3 Rozgrywka (Ekran Główny Sesji)
- **Widok**:  
  - Dwie duże kurtyny zajmujące większość ekranu.  
  - Pasek dolny z sukcesami, porażkami, zyskiem i `remaining_pairs`.  
- **Interakcja**:  
  - Klik w kurtynę → animacja rozszerzenia + spinner (oczekiwanie).  
  - Gdy cena się zmieni → wynik (SUCCESS/FAILURE) + obrazek bodźca.  
  - Pod obrazkiem przycisk „Kolejna runda”, o ile `remaining_pairs > 0`.  
  - Jeśli brak par → przycisk „Podsumowanie sesji”.

### 5.4 Podsumowanie Sesji
- **Zawartość**:
  1. Podstawowe statystyki sesji:  
     - Liczba sukcesów, porażek, różnica (sukces - porażki), % trafień, finalny `(session_profit_factor - 1)*100%`.  
  2. Wykres przebiegu bogactwa w czasie rund (oś x – numer rundy, oś y – wealth).  
  3. Ranking pozytywnych bodźców (z >=1 sukcesem), sort wg liczby sukcesów / sumarycznego profitu.  
  4. Przycisk **„Szczegółowy przebieg rund”** – otwiera/wyświetla listę rund z data/time, pos_image_id, neg_image_id, lewo/prawo, profit_fraction, result.  
  5. Przycisk **„Nowa sesja”** – animacja ładowania, generowanie puli (częściowo już w tle). Po zakończeniu – przejście do nowego ekranu sesji.

### 5.5 Statystyki Globalne
- **Dostępne z Navbaru**: link „Statystyki Użytkownika”.  
- **Zawartość**:
  1. **Lista Zakończonych Sesji**:  
     - Każdy wpis: data, finalny zysk, liczba rund.  
     - Kliknięcie → widok szczegółów danej sesji (m.in. wykres, wynik końcowy, lista rund).  
  2. **Ranking Globalny Obrazów** (pos):  
     - Rozszerzony panel z miniaturami, `total_successes`, `(total_profit_factor - 1)*100%`.  
  3. **Wykres Całkowitego Bogactwa w Kolejnych Sesjach**:  
     - Oś x: numer (lub data) sesji,  
     - Oś y: skumulowany zysk (np. `[product of all (1+profit_fraction session-by-session)] - 1`).  
  4. **Wykresy Skuteczności w Zależności od Pory Dnia**:  
     - Przykładowo: histogram skuteczności rano vs. wieczór.  
     - Przydatne do analizy, czy o pewnej godzinie użytkownik ma lepsze wyniki.  
  5. **Genealogia Bodźców (Lista + Graficzne Połączenia)**:  
     - Każdy bodziec: `id`, rodzic, zysk `(total_profit_factor - 1)*100%`, liczba sukcesów.  
     - **Połączenia** z lewej do prawej (rodzic→dziecko) rysowane jako linie łączące kolejne elementy w liście (lub mini diagram).  
     - Tabela lub grid, gdzie dla dziecka widnieje link do rodzica i wizualna kreska łącząca je ze sobą.

---

## 6. Obsługa Błędów i Timeoutów

1. **Błąd generowania puli**:
   - Overlay z komunikatem: „Wystąpił błąd przy tworzeniu nowej sesji. Spróbuj ponownie.” + przycisk powrotu do strony startowej.
2. **Brak zmiany ceny**:
   - Zakładamy, że cena się zawsze zmieni – w razie braku połączenia lub timeoutu: alert „Brak odpowiedzi z serwera” i powrót do stanu sprzed kliknięcia kurtyny.
3. **Kolejna runda przedwcześnie**:
   - Przycisk „Kolejna runda” pojawia się dopiero po wyświetleniu bodźca, więc nie da się kliknąć zbyt wcześnie.

---

## 7. Podsumowanie

W tym dokumencie:
- **Określono** wygląd i interakcje UI, bazujące na ciemnym motywie, fioletowych akcentach i minimalistycznym stylu.  
- **Sprecyzowano** layout – navbar na górze, dolny pasek statystyk, główny obszar z kurtynami, overlay ładowania.  
- **Rozpisano** szczegółowo ekrany:
  - Ekran Startowy (przycisk „Rozpocznij grę”),  
  - Logowanie/Rejestracja (pole do hasła, nazwy użytkownika),  
  - Rozgrywka (kurtyny + animacja spinnera),  
  - Podsumowanie Sesji (wykres rund, ranking bodźców, szczegóły rund),  
  - Statystyki Globalne (lista sesji, wykresy skuteczności i bogactwa, genealogia bodźców).  
- **Uwzględniono** mechanizm obsługi błędów i braku reakcji ceny.  

Dzięki temu dokumentowi interfejs tachyonai powinien zostać zaprojektowany w sposób spójny z logiką rozgrywki i atrakcyjny dla użytkowników, oferując dodatkowe narzędzia analizy (wykresy, genealogia) dla pogłębionego doświadczenia i zabawy.

