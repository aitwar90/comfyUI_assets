# Nowa, czysta baza deweloperska ROCm 7.2.4
FROM rocm/dev-ubuntu-24.04:7.2.4

ARG DEBIAN_FRONTEND=noninteractive
ENV Python_EXECUTABLE=/usr/bin/python3
ENV PYTHONUNBUFFERED=1

# Ścisłe zmienne środowiskowe kompilacji i uruchomienia dla RX 7800 XT (gfx1101)
ENV HSA_OVERRIDE_GFX_VERSION=11.0.1
ENV PYTORCH_ROCM_ARCH=gfx1101
ENV FORCE_CUDA=1
ENV ATTN_BACKEND=sdpa
ENV SPARSE_ATTN_BACKEND=sdpa
ENV MIOPEN_FIND_MODE=2
ENV CUMM_USE_HIP=1
ENV CCIMPORT_USE_HIP=1
ENV CUMM_HIP_ARCH_LIST=gfx1101

# Linkowanie struktury libdrm (kluczowe, aby ROCm widział poprawnie pliki urządzeń z jądra)
RUN mkdir -p /opt/amdgpu/share/libdrm/ && ln -sf /usr/share/libdrm/amdgpu.ids /opt/amdgpu/share/libdrm/amdgpu.ids

# 1. Zbiorcza instalacja narzędzi i kompletnego SDK ROCm
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ninja-build \
    build-essential \
    cmake \
    ffmpeg \
    wget \
    python3-pip \
    python3-dev \
    python3-venv \
    libgl1-mesa-dev \
    libglib2.0-0 \
    libdrm-dev \
    libegl1 \
    libgles2 \
    libxrender1 \
    libxext6 \
    libsm6 \
    libopenblas-dev \
    libsndfile1 \
    fluidsynth \
    fluid-soundfont-gm \
    gfortran \
    libatlas-base-dev \
    libblas-dev \
    liblapack-dev \
    assimp-utils \
    rocm-dev rocthrust-dev rocprim-dev hipcub-dev hipblas-dev rocblas-dev hipsparse-dev rocsparse-dev \
    hipsolver-dev rocsolver-dev \
    hipblaslt-dev \
    hiprand-dev \
    rocrand-dev \
    && rm -rf /var/lib/apt/lists/*

# Konfiguracja zmiennych linkera i kompilatora HIP
ENV ROCM_PATH=/opt/rocm-7.2.4
ENV C_INCLUDE_PATH=${ROCM_PATH}/include:$C_INCLUDE_PATH
ENV CPLUS_INCLUDE_PATH=${ROCM_PATH}/include:$CPLUS_INCLUDE_PATH
ENV LD_LIBRARY_PATH=${ROCM_PATH}/lib:$LD_LIBRARY_PATH
ENV LIBRARY_PATH=${ROCM_PATH}/lib:$LIBRARY_PATH
ENV CUDA_PATH=$ROCM_PATH

# Precyzyjne i globalne wymuszenie architektury GPU (gfx1101)
ENV PYTORCH_ROCM_ARCH=gfx1101
ENV AMDGPU_TARGETS=gfx1101
ENV TORCH_CUDA_ARCH_LIST=gfx1101

# --- TWORZENIE I AKTYWACJA ŚRODOWISKA WIRTUALNEGO (VENV) ---
# Rozwiązuje to błędy z "externally managed environment" dla uv i pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

# Konfiguracja pip globalnie wewnątrz venv
RUN pip install --upgrade pip setuptools wheel

# Konfiguracja pip globalnie
RUN mkdir -p /etc/pip && echo "[global]\nbreak-system-packages = true" > /etc/pip.conf
RUN ln -sf /usr/bin/python3 /usr/bin/python && ln -sf /usr/bin/pip3 /usr/bin/pip

# 2. Instalacja dedykowanego PyTorcha pod ROCm 7.2
RUN pip3 install --no-cache-dir \
    --default-timeout=1000 \
    --retries 10 \
    torch torchvision torchaudio pytorch-triton-rocm xformers \
    --index-url https://download.pytorch.org/whl/rocm7.2

# 3. Kompilacja nerfacc
RUN git clone https://github.com/ROCm/nerfacc.git /tmp/nerfacc && \
    cd /tmp/nerfacc && \
    find . -type f \( -name "*.cu" -o -name "*.cuh" -o -name "*.hip" -o -name "*.hpp" -o -name "*.cpp" \) \
        -exec sed -i 's/\blerp\b/safe_lerp/g' {} + && \
    sed -i 's/--offload-arch=gfx942/--offload-arch=gfx1101/g' setup.py && \
    export PYTORCH_ROCM_ARCH=gfx1101 && \
    export AMDGPU_TARGETS=gfx1101 && \
    export GPU_TARGETS=gfx1101 && \
    export CPLUS_INCLUDE_PATH=/opt/rocm-7.2.4/include:$CPLUS_INCLUDE_PATH && \
    pip install --no-cache-dir --no-build-isolation . && \
    rm -rf /tmp/nerfacc

# 4. Instalacja standardowych pakietów PyPI oraz sam2
RUN pip3 install --no-cache-dir \
    toml piexif torchsde uv GitPython segment-anything-py \
    imageio-ffmpeg transformers huggingface-hub \
    scikit-image scipy matplotlib dill \
    PyGithub requests \
    numpy einops kornia opencv-python-headless pillow \
    diffusers safetensors open_clip_torch \
    torchmetrics pytorch_msssim pytorch-lightning peft \
    rembg onnxruntime imageio \
    git+https://github.com/facebookresearch/sam2

# Slang-torch
RUN pip install --no-cache-dir git+https://github.com/shader-slang/slang-torch.git 

# Narzędzia matematyczne i graficzne 3D
RUN pip install --no-cache-dir \
    torchtyping tqdm jaxtyping packaging OmegaConf pyhocon iopath easydict \
    nibabel accelerate \
    trimesh fast-simplification plyfile pygltflib xatlas \
    pymeshlab gpytoolbox PyMCubes libigl pyvista pymeshfix igraph \
    PyOpenGL PyOpenGL_accelerate

# Kluczowe biblioteki graficzne ze źródeł
RUN pip install --no-cache-dir git+https://github.com/EasternJournalist/utils3d.git
RUN pip install --no-cache-dir git+https://github.com/ashawkey/kiuikit.git

# --- POPRAWKA DLA KLIUI (NameError: name 'Union' is not defined) ---
# Naprawiamy plik op.py bezpośrednio po instalacji kiuikit
RUN KIUI_OP_PATH=$(python -c "import kiui.op; print(kiui.op.__file__)") && \
    sed -i '1s/^/from typing import Union\n/' "$KIUI_OP_PATH"

# Budowa spconv i cumm pod AMD
RUN pip install --no-cache-dir pccm cumm && \
    pip install --no-cache-dir --no-deps git+https://github.com/traveller59/spconv.git

# Dodatkowe zależności 3D
RUN pip install --no-cache-dir mmgp opencv-python open3d av
RUN pip install --no-cache-dir --no-build-isolation git+https://github.com/SarahWeiii/diso.git#egg=diso

# USTALENIE KATALOGU ROBOCZEGO (naprawione pod strukturę /app/ComfyUI)
WORKDIR /app/ComfyUI

# Klonowanie ComfyUI bezpośrednio do tej ścieżki
RUN git clone https://github.com/comfyanonymous/ComfyUI.git . && \
    pip3 install --no-cache-dir -r requirements.txt

# Zależności dla nodów i torch-scatter-rocm
RUN pip3 install --no-cache-dir opencv-python trimesh timm controlnet-aux mediapipe gguf
RUN pip install --no-cache-dir torch-scatter-rocm

# Instalacja binariów Slang
RUN SLANG_BIN_DIR="/opt/venv/lib/python3.12/site-packages/slangtorch/bin" && \
    mkdir -p $SLANG_BIN_DIR && \
    wget https://github.com/shader-slang/slang/releases/download/v2024.10/slang-2024.10-linux-x86_64.tar.gz -O /tmp/slang.tar.gz && \
    mkdir -p /tmp/slang_dist && \
    tar -xzf /tmp/slang.tar.gz -C /tmp/slang_dist && \
    cp $(find /tmp/slang_dist -name slangc) $SLANG_BIN_DIR/ && \
    cp $(find /tmp/slang_dist -name "*.so*") /usr/local/lib/ && \
    chmod +x $SLANG_BIN_DIR/slangc && \
    ldconfig && \
    rm -rf /tmp/slang*

# Pozostałe pakiety PyPI (zoptymalizowane pod ROCm + Audio)
RUN pip install --no-cache-dir \
    pyfqmr \
    meshlib \
    eigency \
    loguru \
    ninja \
    flatbuffers \
    scikit-learn \
    pyrender \
    cupy-rocm-7-0 \
    librosa soundfile scipy pydub pretty_midi pyfluidsynth \
    cozy-comfyui

# Klonowanie i instalacja ComfyUI-3D-MeshTool (ścieżki poprawione na /app/ComfyUI)
RUN git clone https://github.com/807502278/ComfyUI-3D-MeshTool.git /app/ComfyUI/custom_nodes/ComfyUI-3D-MeshTool && \
    if [ -f /app/ComfyUI/custom_nodes/ComfyUI-3D-MeshTool/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/ComfyUI-3D-MeshTool/requirements.txt; \
    fi

# Obsługa ComfyUI-Hunyuan3DWrapper (naprawione brakujące slashe w warunkach if)
RUN if [ -f /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements.txt; \
    fi
RUN if [ -f /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements_extras.txt ]; then \
        pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements_extras.txt; \
    fi

# Ustawienie ścieżek Pythona (skierowane na właściwy folder główny)
ENV PYTHONPATH="${PYTHONPATH}:/app/ComfyUI:/app/ComfyUI/custom_nodes"
ENV ATTN_BACKEND=sdpa

EXPOSE 8188
