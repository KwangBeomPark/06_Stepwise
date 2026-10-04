# 📘 Podręcznik Użytkownika Stepwise (Instrukcja Obsługi)

*Przeczytaj w innych językach: [English](USER_MANUAL.md) | [Polski (Polska)](USER_MANUAL.pl.md) | [한국어](USER_MANUAL.ko.md)*

---

## 💡 1. Czym jest Stepwise? (Podsumowanie w 30 sekund)

**Stepwise** to niezawodny asystent automatyzacji procesów biurowych i produkcyjnych dla systemu Windows. Zastępuje człowieka w żmudnym, powtarzalnym wprowadzaniu danych z arkuszy Excel/CSV do systemów korporacyjnych (takich jak **SAP GUI, systemy ERP, programy księgowe czy wewnętrzne portale webowe**), precyzyjnie symulując ruchy myszy i naciśnięcia klawiatury.

### ❓ Czym różni się od zwykłych makr i ciężkich systemów RPA?

| Cecha | Zwykłe makra klawiatury/myszy | Automatyzacja Stepwise |
| :--- | :--- | :--- |
| **Opóźnienia sieci/systemu** | Klika na oślep bez sprawdzania, powodując **błędy, klikanie w złe pola lub awarie** | Sprawdza stan ekranu za pomocą analizy obrazu (`Guard`) i czeka na pojawienie się okna |
| **W razie niespodziewanego błędu** | Kontynuuje działanie, prowadząc do **utraty danych lub duplikatów** | Natychmiast zatrzymuje pracę (`Fail-Fast`) i wskazuje dokładną przyczynę problemu |
| **Oryginalny plik Excel** | Ryzyko uszkodzenia lub nadpisania pliku źródłowego | **Nigdy nie modyfikuje pliku źródłowego**; wyniki zapisuje w osobnym pliku CSV |
| **Zatrzymanie awaryjne** | Trudne do przerwania w trakcie pętli | Błyskawiczne zatrzymanie w 0,01 sekundy klawiszem **F12** |
| **Uprawnienia instalacji** | Wymaga uprawnień administratora IT (Admin) | Działa od razu ze **standardowymi uprawnieniami użytkownika (Non-Admin)** |

---

## 🚀 2. Szybki start w 5 minut (Twoja pierwsza automatyzacja)

Uruchamiasz Stepwise po raz pierwszy? Wykonaj te proste kroki, aby połączyć plik Excel i w 5 minut stworzyć pierwsze działające makro!

```
[ Schemat postępowania ]
1. Wybierz plik Excel  ➡️  2. Poznaj 3 sekcje  ➡️  3. Dodaj kliknięcie i tekst  ➡️  4. Uruchom i sprawdź
```

### Krok 1: Wczytanie pliku danych Excel
1. W górnym pasku narzędzi lub w prawej zakładce **[Data Preview]** kliknij przycisk **[Choose Data File...]**.
2. Wybierz swój plik `.xlsx` lub `.csv` (np. zawierający kolumny: `KodDostawcy`, `NumerArtykulu`, `Ilosc`, `Cena`).
3. Dane pojawią się w tabeli poniżej, a u góry wyświetlą się niebieskie przyciski zmiennych, np. `[+ {KodDostawcy}]`, `[+ {Ilosc}]`.

---

### Krok 2: Zrozumienie 3 sekcji przepływu (Pipeline)
W głównym oknie drzewa akcji znajdują się 3 kluczowe sekcje:

1. **📁 SETUP (Wykonywane raz na początku)**:
   - Działania przygotowawcze (np. aktywacja okna ERP, wpisanie kodu transakcji T-Code lub przejście do ekranu wprowadzania).
2. **📁 PER ROW (Powtarzane dla każdego wiersza Excela)**:
   - **Główny silnik automatyzacji.** Krok po kroku wykonuje operacje dla wiersza 1, wiersza 2, wiersza 3 itd. Tutaj umieszczasz kliknięcia i wprowadzanie danych.
3. **📁 CLEANUP (Wykonywane raz na zakończenie)**:
   - Działania końcowe po przetworzeniu wszystkich wierszy (np. zamknięcie okna transakcji, zapis podsumowania lub powiadomienie o sukcesie).

---

### Krok 3: Dodawanie kliknięć myszą i wpisywania tekstu

#### ① Kliknięcie w pole wprowadzania
1. Kliknij przycisk **[+ Click]** w lewym dolnym rogu drzewa akcji.
2. W sekcji `PER ROW` pojawi się nowa akcja kliknięcia.
3. W panelu właściwości **[Properties]** po prawej stronie kliknij przycisk **[Pick (F8)]**.
4. Kursor zmieni się w celownik. **Kliknij wybrane pole w programie ERP na ekranie**. Współrzędne X i Y zostaną pobrane automatycznie!

#### ② Wpisywanie danych z kolumny Excela
1. Kliknij przycisk **[+ Type]** w lewym dolnym rogu.
2. W prawym panelu właściwości kliknij pole `Text to type:`.
3. Kliknij niebieski przycisk zmiennej `[+ {KodDostawcy}]`. Wartość `{KodDostawcy}` zostanie od razu wstawiona.
4. *Wskazówka*: Możesz łączyć zmienne ze stałym tekstem, np. `{KodDostawcy} - Zamówienie`.

#### ③ Klawisze Enter i Tab
1. Aby przejść do kolejnego pola, kliknij **[+ Key]** i wybierz klawisz `Tab` lub `Enter`.

---

### Krok 4: Uruchomienie i zatrzymanie awaryjne

1. Kliknij zielony przycisk **[▶ Run]** w górnym pasku (lub naciśnij **F5**).
2. Stepwise zacznie pobierać dane od pierwszego wiersza i automatycznie wprowadzać je do systemu.
3. **🚨 Zatrzymanie awaryjne (F12)**:
   - Jeśli cokolwiek pójdzie nie tak lub zechcesz natychmiast zatrzymać proces, naciśnij klawisz **`F12`** na klawiaturze.
   - Program zatrzyma się w ułamku sekundy (0,01 s) w bezpieczny sposób.

---

## 🛡️ 3. Wbudowane zabezpieczenia wizualne (Guard & Verify)

W systemach korporacyjnych zdarzają się opóźnienia sieciowe, kręcące się wskaźniki ładowania lub nagłe okna dialogowe. Zabezpieczenia wizualne Stepwise gwarantują 100% pewności:

### 1) Guard (Kontrola wstępna): „Sprawdź, czy okno jest otwarte przed kliknięciem!”
- We właściwościach akcji zaznacz opcję **`[✓] Enable Guard`**.
- Kliknij przycisk **[Capture (F9)]** — ekran zostanie zamrożony.
- **Zaznacz myszą charakterystyczny fragment (np. nagłówek okna lub ikonę)**, który potwierdza gotowość ekranu.
- **Działanie**: Stepwise upewni się, że wskazany element jest widoczny, zanim kliknie. Jeśli system się ładuje, program poczeka. Jeśli upłynie limit czasu, bezpiecznie zatrzyma proces.

### 2) Verify (Weryfikacja końcowa): „Potwierdź zapis przed przejściem do kolejnego wiersza!”
- Na akcji kliknięcia przycisku „Zapisz” zaznacz **`[✓] Enable Verify`**.
- Użyj **[Capture (F9)]** i zaznacz komunikat potwierdzający zapis (np. *"Dokument został pomyślnie zaksięgowany"*).
- **Działanie**: Program przejdzie do kolejnego wiersza Excela dopiero wtedy, gdy na własne oczy upewni się, że dane zostały poprawnie zapisane w bazie.

---

## 📊 4. Masowe przetwarzanie i bezpieczeństwo danych

Możesz bezpiecznie uruchomić przetwarzanie setek rekordów.

1. **Pełna ochrona pliku źródłowego**:
   - Stepwise nigdy nie modyfikuje ani nie nadpisuje Twojego oryginalnego pliku Excel.
2. **Raport wyników CSV w czasie rzeczywistym**:
   - Podczas pracy tworzony jest plik `wyniki_<nazwa>_<data>.csv`, w którym na bieżąco rejestrowany jest status każdego wiersza (`SUCCESS`, `FAILED`, czas trwania, przyczyna zatrzymania).
3. **Wznawianie od miejsca zatrzymania (Resume)**:
   - Jeśli przy 45. wierszu wystąpił błąd systemowy, zamknij komunikat w ERP, kliknij prawym przyciskiem myszy na wiersz 45 w tabeli i wybierz **[Retry this row]** lub **[Run from this row]**. Nie musisz zaczynać wszystkiego od nowa.

---

## ⚡ 5. Regulacja prędkości i porady praktyczne

### 1) Praca przy wolnym łączu sieciowym
- Skorzystaj z przełącznika prędkości w prawym górnym rogu paska narzędzi:
  - **Normal**: Standardowa prędkość optymalna (Zalecana).
  - **Slow (+0.5s)**: Dodatkowe 0,5 sekundy odstępu między każdym krokiem.
  - **Very slow (+1.0s)**: Dodatkowa 1 sekunda odstępu przy dużych opóźnieniach serwera.

### 2) Rozdzielczość ekranu i stała pozycja okien
- Zadbaj o to, aby okno programu docelowego (np. SAP) znajdowało się zawsze w tej samej pozycji i rozmiarze (np. zmaksymalizowane).
- Na dolnym pasku stanu Stepwise automatycznie sprawdza, czy bieżąca rozdzielczość i skala DPI odpowiadają stanowi z momentu nagrywania makra (np. `1920x1080 @100% ✅`).

---

## ❓ Najczęściej zadawane pytania (FAQ)

**P1. Czy mogę wpisać hasło do kroków makra?**  
> ⚠️ **Zdecydowanie odradzamy.** Ze względów bezpieczeństwa korporacyjnego nie należy zapisywać haseł otwartym tekstem w makrach. Zaloguj się ręcznie do systemu przed uruchomieniem Stepwise.

**P2. Polskie znaki diakrytyczne (ą, ę, ś, ć, ż, ź) wpisują się niepoprawnie.**  
> W panelu właściwości kroku `+ Type` zmień tryb wpisywania (Typing mode) na **`Paste (Clipboard)`**. Stepwise użyje schowka Windows, co gwarantuje 100% poprawne wklejenie znaków Unicode we wszystkich językach.

**P3. Czy mogę pracować na komputerze w trakcie działania Stepwise?**  
> Ponieważ Stepwise bezpośrednio steruje fizycznym kursorem myszy i klawiaturą, poruszanie myszką może zmienić punkt kliknięcia. Na czas działania automatyzacji zalecamy zrobienie krótkiej przerwy na kawę lub korzystanie z drugiego monitora/laptopa!
