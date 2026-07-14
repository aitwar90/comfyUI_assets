Dokumentacja: ComfyUI-SimpleBake & Artistic (Wtyczka jest ustawiona pod AMD Radeon 7800 XT)
Tools

1. Funkcjonalność Wtyczki
ComfyUI-SimpleBake to zaawansowany zestaw narzędzi zaprojektowany do automatyzacji
procesów 3D i artystycznych wewnątrz ekosystemu ComfyUI. Główne moduły obejmują:
Automatyzacja Bake'owania: Umożliwia przenoszenie tekstur i parametrów materiałowych
pomiędzy modelami bez ręcznej edycji.
Generowanie Modeli 3D: Zintegrowane workflowy pozwalające na tworzenie geometrii na
podstawie promptów tekstowych.
Upscaling Artystyczny: Dedykowane nody do inteligentnego upscalingu przy zachowaniu
spójności tekstur (UltraSharp/RealESRGAN).
2. Rozszerzona Obsługa Dockera

Zarządzanie kontenerem
Projekt jest w pełni konteneryzowany dla zapewnienia powtarzalności środowiska (ROCm
AMD). Najważniejsze operacje:

# Budowanie od zera
''docker compose build --no-cache''
# Uruchomienie w tle
''docker compose up -d''
# Zatrzymanie
''docker compose down''

Diagnostyka i czyszczenie
W przypadku błędów kompilacji lub konfliktów warstw (cache):
# Pełne czyszczenie systemu Docker (obrazy, volume, sieci)
''docker system prune -a --volumes -f''


# Naprawa uprawnień plików po zamknięciu kontenera
''sudo chown -R $USER:$USER .''

3. Uwagi techniczne
Wtyczka korzysta z nvdiffrast . Wymagana jest zgodność z architekturą ROCm (gfx1101/
gfx1201). Modele o dużych rozmiarach są synchronizowane przez system Git LFS. W razie
problemów z brakującymi wagami, należy wykonać git lfs pull .
