#!/bin/bash
set -e # Przerwij w razie nagłego błędu

CD_DIR="/home/aitwarcl/.AI/comfyUI_Artistic"
cd "$CD_DIR"

# 1. Czyszczenie starych pamięci podręcznych kompilatora ROCm/Triton
echo "=== 1. Czyszczenie pamięci podręcznej kompilatorów ==="
rm -rf ~/.cache/triton
rm -rf ~/.cache/torch/hip_kernel_cache

# Funkcja sprzątająca wywoływana przy zamknięciu skryptu (Ctrl+C)
cleanup() {
    echo -e "\n=== Zamykanie silnika ComfyUI... ==="
    docker compose down
    exit 0
}
# Przechwycenie Ctrl+C i innych sygnałów zamknięcia
trap cleanup SIGINT SIGTERM

# 2. Uruchomienie kontenera w tle (-d)
echo "=== 2. Uruchamianie kontenerów Docker (w tle) ==="
docker compose up -d

# 3. Oczekiwanie na port i otwarcie przeglądarki
echo "=== 3. Oczekiwanie na uruchomienie interfejsu... ==="
(
    # Sprawdzamy co sekundę (maksymalnie przez 30 sekund), czy port 8188 reaguje
    for i in {1..30}; do
        if nc -z localhost 8188 2>/dev/null; then
            echo "-> ComfyUI jest aktywne na porcie 8188!"
            break
        fi
        sleep 1
    done
    xdg-open "http://localhost:8188" &>/dev/null &
) &

# 4. Podpięcie pod logi na żywo (blokuje terminal i czeka na Ctrl+C)
echo "=== 4. Wyświetlanie logów silnika (Ctrl+C wyłączy kontener i zwolni VRAM) ==="
docker logs -f comfy_3d_engine

# Na wypadek gdyby docker logs sam się wyłączył bez Ctrl+C
cleanup
