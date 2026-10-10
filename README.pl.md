*Przeczytaj w innych językach: [English](README.md), [한국어](README.ko.md), [Polski](README.pl.md) | 📖 **Instrukcja użytkownika**: [Instrukcja Polski](docs/manual/USER_MANUAL.pl.md) • [English Manual](docs/manual/USER_MANUAL.md) • [한국어 설명서](docs/manual/USER_MANUAL.ko.md)*

# 🛡️ Stepwise: Automatyzacja powtarzalnych zadań księgowo-operacyjnych w oparciu o tabele danych

<p align="center">
  <img src="assets/images/stepwise-hero.png" width="950" alt="Stepwise - Narzędzie automatyzacji procesów desktopowych oparte na danych dla systemu Windows">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?logo=windows&logoColor=white" alt="Platforma Windows">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/GUI-PySide6%20Qt-41CD52?logo=qt&logoColor=white" alt="PySide6">
  <img src="https://img.shields.io/badge/Vision-OpenCV-5C3EE8?logo=opencv&logoColor=white" alt="OpenCV">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="Licencja MIT">
  <img src="https://img.shields.io/badge/Admin%20Rights-Not%20Required-brightgreen" alt="Brak wymogu uprawnień administratora">
</p>

> **Niezawodna, sterowana danymi automatyzacja dla starszych systemów ERP (SAP GUI) i wewnętrznych portali webowych.**  
> Bezpiecznie przetwarzaj wiersze tabel Excel/CSV, weryfikuj stan ekranu za pomocą widzenia komputerowego i wykonuj operacje bez pisania kodu oraz bez uprawnień administratora.

---

## 💡 Dlaczego Stepwise?

W środowiskach korporacyjnych zespoły operacyjne codziennie wprowadzają ręcznie setki dokumentów, faktur i pozycji księgowych do starszych systemów ERP lub zablokowanych portali firmowych.

- **Brak interfejsów API i wysokie koszty wdrożeń**: Tworzenie dedykowanych interfejsów wsadowych dla starszych systemów ERP często wiąże się z ogromnymi budżetami integracyjnymi.
- **Zagrożenia ze strony tradycyjnych klikaczy**: Zwykłe makra działają „na ślepo” bez weryfikacji ekranu, powodując duplikaty wpisów lub błędy przy opóźnieniach sieci.
- **Bariera uprawnień**: Ciężkie korporacyjne narzędzia RPA są drogie i wymagają uprawnień administratora IT, których pracownicy biurowi zazwyczaj nie posiadają.

**Stepwise** powstał z myślą o praktykach biznesowych. Wiążąc kolumny Excela ze zmiennymi (`{VendorCode}`, `{Amount}`), sprawdzając warunki wizualne za pomocą OpenCV oraz stosując bezkompromisową **zasadę natychmiastowego zatrzymania w razie błędu (Fail-Fast)**, Stepwise zapewnia bezpieczną i niezawodną automatyzację.

---

## 🛡️ 4 Filary bezpieczeństwa Stepwise

<p align="center">
  <img src="assets/images/stepwise-features.png" width="950" alt="Architektura Stepwise: 4 Filary">
</p>

### 1. 3-sekcyjny potok działań (Setup / Per Row / Cleanup)
Przepływ pracy podzielony jest na przejrzystą, 3-etapową strukturę:
- **Setup (Inicjalizacja 1x)**: Uruchomienie ERP, wpisanie kodu transakcji (T-Code), otwarcie właściwego menu.
- **Per Row (Pętla dla każdego wiersza)**: Odczytywanie kolejnych wierszy pliku Excel/CSV i podstawianie zmiennych do formularzy.
- **Cleanup (Zakończenie 1x)**: Zapis podsumowania i bezpieczne zamknięcie sesji.

### 2. Bezpieczeństwo wizualne (Guard & Verify)
- **Guard (Weryfikacja przed akcją)**: Sprawdza za pomocą dopasowywania wzorca (OpenCV), czy wymagane pole lub okno jest aktywne.
- **Verify (Weryfikacja po akcji)**: Potwierdza, czy po kliknięciu pojawił się komunikat o sukcesie lub oczekiwany stan.
- **Wygodne narzędzia pomocnicze**: Klawisz `F8` do natychmiastowego pobrania współrzędnych lub `F9` do zamrożenia ekranu i zaznaczenia wzorca obrazu.

### 3. Fail-Fast i ochrona danych źródłowych
- W przypadku wystąpienia nieoczekiwanego okna lub przekroczenia limitu czasu Stepwise **zatrzymuje się natychmiast**.
- Pliki źródłowe (`.xlsx`, `.csv`) **nigdy nie są modyfikowane**.
- Status każdego wiersza i diagnostyczne zrzuty ekranu błędów są rejestrowane w osobnym pliku Results CSV, co umożliwia natychmiastowe **wznowienie od nieprzetworzonego wiersza (Resume)**.

### 4. Kontrola prędkości i awaryjne zatrzymanie F12
- Dopasuj opóźnienia do pracy na pulpitach zdalnych: **Normal / Slow (+0.5s) / Very Slow (+1.0s)**.
- Naciśnij **F12** w dowolnym momencie, aby natychmiast i bezwarunkowo zatrzymać działanie programu.

---

## 🚀 Pobieranie i instalacja

1. Przejdź do zakładki **[Releases](https://github.com/KwangBeomPark/06_Stepwise/releases)**.
2. Pobierz instalator: **`App06_Stepwise_Setup_vX.Y.Z.exe`** (oraz towarzyszące pliki manifestu i sum kontrolnych).
3. Zainstaluj program (instalacja do profilu użytkownika, nie wymaga uprawnień administratora).

---

## 📄 Licencja

Projekt jest objęty licencją MIT. Szczegóły w pliku [LICENSE](LICENSE).
