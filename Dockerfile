# Nowa, czysta baza deweloperska ROCm 7.2.4 - dla AMD 7800XT
FROM rocm/dev-ubuntu-24.04:7.2.4

ARG DEBIAN_FRONTEND=noninteractive

# --- GLOBALNA KONFIGURACJA ŚRODOWISKA I ROCm ---
ENV Python_EXECUTABLE=/usr/bin/python3 \
    PYTHONUNBUFFERED=1 \
    HSA_OVERRIDE_GFX_VERSION=11.0.1 \
    PYTORCH_ROCM_ARCH=gfx1101 \
    AMDGPU_TARGETS=gfx1101 \
    TORCH_CUDA_ARCH_LIST=gfx1101 \
    FORCE_CUDA=1 \
    ATTN_BACKEND=sdpa \
    SPARSE_ATTN_BACKEND=sdpa \
    MIOPEN_FIND_MODE=2 \
    CUMM_USE_HIP=1 \
    CCIMPORT_USE_HIP=1 \
    CUMM_HIP_ARCH_LIST=gfx1101 \
    ROCM_PATH=/opt/rocm-7.2.4

ENV C_INCLUDE_PATH=${ROCM_PATH}/include:$C_INCLUDE_PATH \
    CPLUS_INCLUDE_PATH=${ROCM_PATH}/include:$CPLUS_INCLUDE_PATH \
    LD_LIBRARY_PATH=${ROCM_PATH}/lib:$LD_LIBRARY_PATH \
    LIBRARY_PATH=${ROCM_PATH}/lib:$LIBRARY_PATH \
    CUDA_PATH=$ROCM_PATH

# Linkowanie struktury libdrm (kluczowe dla wykrywania GPU przez ROCm)
RUN mkdir -p /opt/amdgpu/share/libdrm/ && ln -sf /usr/share/libdrm/amdgpu.ids /opt/amdgpu/share/libdrm/amdgpu.ids

# --- INSTALACJA PAKIETÓW SYSTEMOWYCH SYSTEMU ---
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
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# --- TWORZENIE I KONFIGURACJA VENV ---
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

RUN pip install --upgrade pip setuptools wheel && \
    mkdir -p /etc/pip && echo "[global]\nbreak-system-packages = true" > /etc/pip.conf && \
    ln -sf /usr/bin/python3 /usr/bin/python && ln -sf /usr/bin/pip3 /usr/bin/pip

# --- INSTALACJA PYTORCH ROCm 7.2 ---
RUN pip3 install --no-cache-dir \
    --default-timeout=1000 \
    --retries 10 \
    torch torchvision torchaudio pytorch-triton-rocm xformers \
    --index-url https://download.pytorch.org/whl/rocm7.2

RUN pip3 install --no-cache-dir torch-scatter-rocm torch-sparse-rocm torch-cluster-rocm torch-spline-conv-rocm

# --- KOMPILACJA NERFACC I NVDIFFRAST ZE ŹRÓDEŁ ---
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

RUN git clone https://github.com/Lamothe/nvdiffrast_rocm.git /tmp/nvdiffrast && \
    cd /tmp/nvdiffrast && \
    # 1. Flagi zapobiegające błędom kompilacji typów half
    export CXXFLAGS="-D__HIP_NO_HALF_OPERATORS__=1 -D__HIP_NO_HALF_CONVERSIONS__=1" && \
    export LDFLAGS="-L/opt/rocm-7.2.4/lib" && \
    # 2. Patchowanie (skoro używasz forka, on może mieć już część rzeczy, 
    # ale Wave64 trzeba wymusić w kodzie)
    find . -type f \( -name "*.cu" -o -name "*.cuh" -o -name "*.cpp" \) -exec sed -i 's/0xffffffffu/0xffffffffffffffffull/g' {} + && \
    # 3. Instalacja
    pip install . --no-cache-dir --no-build-isolation && \
    rm -rf /tmp/nvdiffrast

# --- INSTALACJA GLOBALNYCH BIBLIOTEK PYTHON (PyPI + GITHUB) ---
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

RUN pip install --no-cache-dir \
    torchtyping tqdm jaxtyping packaging OmegaConf pyhocon iopath easydict \
    nibabel accelerate \
    trimesh fast-simplification plyfile pygltflib xatlas \
    pymeshlab gpytoolbox PyMCubes libigl pyvista pymeshfix igraph \
    PyOpenGL PyOpenGL_accelerate \
    mmgp open3d av \
    git+https://github.com/shader-slang/slang-torch.git \
    git+https://github.com/EasternJournalist/utils3d.git \
    git+https://github.com/ashawkey/kiuikit.git

RUN pip install --no-cache-dir pccm cumm && \
    pip install --no-cache-dir --no-deps git+https://github.com/traveller59/spconv.git && \
    pip install --no-cache-dir --no-build-isolation git+https://github.com/SarahWeiii/diso.git#egg=diso

# --- INSTALACJA I KONFIGURACJA COMFYUI ---
WORKDIR /app/ComfyUI

RUN git clone https://github.com/comfyanonymous/ComfyUI.git . && \
    pip3 install --no-cache-dir -r requirements.txt

# Zależności dodatkowe dla nodów (usunięto zduplikowane trimesh oraz opencv-python na rzecz headless)
RUN pip3 install --no-cache-dir timm controlnet-aux mediapipe gguf && \
    pip install --no-cache-dir torch-scatter-rocm

# Kompilacja i konfiguracja Slang
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

# --- REFORMOWANA SEKCJA AUDIO (Z BEZPIECZNYM INSTALATOREM) ---
# 1. Atrapy i oszustwa środowiska dla starych instalatorów
RUN echo "from packaging.version import parse as parse_version" > /opt/venv/lib/python3.12/site-packages/pkg_resources.py && \
    mkdir -p /opt/venv/lib/python3.12/site-packages/pypesq && \
    echo 'def pypesq(fs, ref, deg, mode): return 0.0' > /opt/venv/lib/python3.12/site-packages/pypesq/__init__.py && \
    mkdir -p /opt/venv/lib/python3.12/site-packages/pypesq-1.2.4.dist-info && \
    printf "Metadata-Version: 2.1\nName: pypesq\nVersion: 1.2.4\n" > /opt/venv/lib/python3.12/site-packages/pypesq-1.2.4.dist-info/METADATA

# 2. Poprawna instalacja matematyki oraz izolacja bibliotek audio bez zepsucia pandas
RUN pip install --no-cache-dir "pywavelets>=1.6.0" "pandas>=2.1.0" && \
    pip install --no-cache-dir --no-deps aeiou stable-audio-tools && \
    pip install --no-cache-dir \
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
    demucs openai-whisper hydra-core pyttsx3 pyloudnorm \
    fastcore bokeh holoviews wandb webdataset pedalboard umap-learn \
    alias-free-torch==0.0.6 auraloss==0.4.0 descript-audio-codec==1.0.0 \
    einops-exts ema-pytorch==0.2.3 encodec==0.1.1 gradio k-diffusion laion-clap local-attention \
    packaging seconohe

# --- INTEGRACJA NODÓW I ŁATANIE TYPOWANIA PYTHON 3.12 ---
RUN git clone https://github.com/807502278/ComfyUI-3D-MeshTool.git /app/ComfyUI/custom_nodes/ComfyUI-3D-MeshTool && \
    if [ -f /app/ComfyUI/custom_nodes/ComfyUI-3D-MeshTool/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/ComfyUI-3D-MeshTool/requirements.txt; \
    fi

RUN if [ -f /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements.txt; \
    fi && \
    if [ -f /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements_extras.txt ]; then \
        pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/ComfyUI-Hunyuan3DWrapper/requirements_extras.txt; \
    fi

RUN for dir in "/opt/venv/lib/python3.12/site-packages/kiui" \
               "/app/ComfyUI/custom_nodes/ComfyUI-3D-MeshTool" \
               "/app/ComfyUI/custom_nodes/ComfyUI-3D-Pack"; do \
        if [ -d "$dir" ]; then \
            echo "Aplikowanie poprawek typowania w katalogu: $dir" && \
            find "$dir" -type f -name "*.py" | while read -r file; do \
                if ! grep -q "from __future__ import annotations" "$file"; then \
                    echo "Patchowanie: $file" && \
                    printf "from __future__ import annotations\nimport torch\nfrom torch import Tensor\nfrom typing import Optional, Union, List, Dict, Any\n" > /tmp/header_temp && \
                    cat "$file" >> /tmp/header_temp && \
                    mv /tmp/header_temp "$file"; \
                fi \
            done; \
        fi \
    done

RUN if [ -f /app/ComfyUI/custom_nodes/ComfyUI-StableAudioSampler/requirements.txt ]; then \
        sed -i '/flash_attn/d' /app/ComfyUI/custom_nodes/ComfyUI-StableAudioSampler/requirements.txt; \
    fi

# --- URUCHOMIENIE ---
ENV PYTHONPATH="${PYTHONPATH}:/app/ComfyUI:/app/ComfyUI/custom_nodes"

EXPOSE 8188
