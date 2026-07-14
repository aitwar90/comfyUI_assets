ComfyUI-SimpleBake & Artistic Tools
Zestaw narzędzi i workflow przeznaczony do pracy z ComfyUI, zoptymalizowany pod kątem renderowania 3D i wysokiej jakości upscalingu. Projekt wspiera akcelerację GPU na architekturze ROCm (AMD).

🛠 Zawartość
custom_nodes/ComfyUI-SimpleBake: Niestandardowe nody do automatyzacji procesów pieczenia (bake) tekstur i modeli.

workflow/: Gotowe workflowy do generowania modeli 3D i zaawansowanej obróbki grafiki.

models/:

upscale_models/: Modele typu UltraSharp oraz RealESRGAN (zarządzane przez Git LFS).

loras/: Kolekcja wytrenowanych modeli LoRA (zarządzane przez Git LFS).

🚀 Wymagania
Docker z obsługą ROCm (dla kart AMD).

Git LFS (konieczny do pobrania modeli).

📥 Instalacja i pierwsze kroki
Sklonuj repozytorium z obsługą LFS:

Bash
git clone git@github.com:aitwar90/comfyUI_assets.git
cd comfyUI_assets
git lfs pull
Zarządzanie plikami (Uprawnienia):
Jeśli uruchamiasz środowisko w Dockerze, pamiętaj o poprawnych uprawnieniach do plików:

Bash
sudo chown -R $USER:$USER .
Uruchomienie:

Bash
docker compose up --build
⚙️ Uwagi techniczne
Projekt wykorzystuje nvdiffrast z odpowiednimi patchami dla architektury ROCm (gfx1101/gfx1201).

Duże pliki modeli są przechowywane w Git LFS. Jeśli po pobraniu widzisz pliki o rozmiarze kilku bajtów, upewnij się, że masz zainstalowane git-lfs i wykonaj git lfs pull.
