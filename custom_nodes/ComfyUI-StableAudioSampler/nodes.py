import os, sys, json, gc
import glob
import typing as tp
import numpy as np
import torch
import torchaudio
from einops import rearrange
from safetensors.torch import load_file
from torchaudio import transforms as T
from aeiou.viz import audio_spectrogram_image

from .util_dependencies import PackageDependencyChecker
from .util_config import get_model_config

# Add local stable-audio-tools to path i bezpieczne wstrzyknięcie atrapy pkg_resources
def add_stable_audio_tools_path():
    import sys, os, types
    current_path = os.path.dirname(os.path.abspath(__file__))
    stable_audio_path = os.path.abspath(os.path.join(current_path, '../../custom-extensions/stable-audio-tools'))
    
    # Lokalne oszustwo - aplikowane tylko w locie w pamięci RAM
    if 'pkg_resources' not in sys.modules:
        pkg_resources_mock = types.ModuleType('pkg_resources')
        import packaging
        pkg_resources_mock.packaging = packaging
        pkg_resources_mock.Requirement = lambda: None
        pkg_resources_mock.Requirement.parse = lambda x: type('AtrapaReq', (object,), {'name': x.split("==")[0].split(">=")[0].split("<=")[0].strip(), 'specifier': ''})
        sys.modules['pkg_resources'] = pkg_resources_mock
        print("[comfyui-stable-audio-sampler] Bezpiecznie wstrzyknięto atrapę pkg_resources do RAMu!")

    if stable_audio_path not in sys.path:
        sys.path.insert(0, stable_audio_path)
        print(f"[comfyui-stable-audio-sampler] Added stable-audio-tools path: {stable_audio_path}")

add_stable_audio_tools_path()
# Bezpieczny fallback dla copy_state_dict bezpośrednio w kodzie, 
# eliminujący wadliwy import z zewnętrznej biblioteki
def copy_state_dict(target_state_dict, source_state_dict):
    for name, param in source_state_dict.items():
        if name in target_state_dict:
            try:
                target_state_dict[name].copy_(param)
            except Exception as e:
                print(f"[StableAudioSampler] Pomijanie kopiowania parametru {name} z powodu błędu: {e}")
        else:
            print(f"[StableAudioSampler] Parametr {name} nie istnieje w modelu docelowym.")
# Import stable-audio-tools after path modification
from stable_audio_tools import get_pretrained_model, create_model_from_config
from stable_audio_tools.inference.generation import generate_diffusion_cond, generate_diffusion_uncond
from stable_audio_tools.inference.utils import prepare_audio
from stable_audio_tools.models.utils import load_ckpt_state_dict

# Comfy libs
def add_comfy_path():
    current_path = os.path.dirname(os.path.abspath(__file__))
    comfy_path = os.path.abspath(os.path.join(current_path, '../../../comfy'))
    if comfy_path not in sys.path:
        sys.path.insert(0, comfy_path)

add_comfy_path()

from comfy.utils import ProgressBar # type: ignore
import folder_paths # type: ignore

MAX_FP32 = np.iinfo(np.int32).max
SCHEDULERS = ["dpmpp-3m-sde", "dpmpp-2m-sde", "k-heun", "k-lms", "k-dpmpp-2s-ancestral", "k-dpm-2", "k-dpm-fast"]
ACKPT_FOLDER = "models/audio_checkpoints/"
TEMP_FOLDER = "temp/"

class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

base_path = os.path.dirname(os.path.realpath(__file__))
os.makedirs(ACKPT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

any = AnyType("*")

def get_models_path(ckpt_name):
    if not ckpt_name:
        return None
    return f"{ACKPT_FOLDER}{ckpt_name}"

model_files = [os.path.basename(file) for file in glob.glob(f"{ACKPT_FOLDER}*.safetensors")] + [os.path.basename(file) for file in glob.glob("models/audio_checkpoints/*.ckpt")]
config_files = [os.path.basename(file) for file in glob.glob(f"{ACKPT_FOLDER}*.json")]
if len(model_files) == 0:
    model_files.append(f"Put models in {ACKPT_FOLDER}")

def repo_path(repo, filename):
    path = os.path.join(repo, filename)
    instance_path = os.path.normpath(path)
    if sys.platform == 'win32':
        instance_path = instance_path.replace('\\', "/")
    return instance_path

import re
def replace_variables(template, values_dict):
    """Replace variables from a template where {} encloses a variable key from values_dict."""
    pattern = r'\{(\w+)\}'

    def replacer(match):
        variable_name = match.group(1)
        value = values_dict.get(variable_name, match.group(0))
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return match.group(0)

    result = re.sub(pattern, replacer, template)
    return result

import io

def wav_bytes_to_tensor(wav_bytes: tp.Union[bytes, dict], model, sample_rate, sample_size: int) -> tp.Tuple[int, torch.Tensor]:
    if isinstance(wav_bytes, dict):
        if 'waveform' in wav_bytes:
            audio_tensor = wav_bytes['waveform']
            in_sr = wav_bytes.get('sample_rate', sample_rate)
        elif 'path' in wav_bytes:
            audio_tensor, in_sr = torchaudio.load(wav_bytes['path'])
        elif 'tensor' in wav_bytes:
            audio_tensor = wav_bytes['tensor']
            in_sr = wav_bytes.get('sample_rate', sample_rate)
        elif 'filename' in wav_bytes:
            audio_tensor, in_sr = torchaudio.load(wav_bytes['filename'])
        else:
            print("Audio dictionary contents:", wav_bytes.keys())
            raise ValueError("Invalid audio dictionary format - must contain 'waveform', 'path', 'tensor', or 'filename' key")
    else:
        audio_tensor, in_sr = torchaudio.load(io.BytesIO(wav_bytes))

    if audio_tensor.dim() == 3:
        audio_tensor = audio_tensor.squeeze(0)
    elif audio_tensor.dim() == 1:
        audio_tensor = audio_tensor.unsqueeze(0)
    
    if audio_tensor.shape[0] > audio_tensor.shape[-1]:
        audio_tensor = audio_tensor.transpose(0, -1)
    
    if in_sr != sample_rate:
        resample_tf = T.Resample(in_sr, sample_rate).to(audio_tensor.device)
        audio_tensor = resample_tf(audio_tensor)

    num_channels, num_samples = audio_tensor.shape
    if num_samples > sample_size:
        audio_tensor = audio_tensor[:, :sample_size]
    elif num_samples < sample_size:
        padding = torch.zeros((num_channels, sample_size - num_samples), dtype=audio_tensor.dtype, device=audio_tensor.device)
        audio_tensor = torch.cat((audio_tensor, padding), dim=1)

    dtype = next(model.parameters()).dtype
    audio_tensor = audio_tensor.to(dtype)
    
    return sample_rate, audio_tensor


def generate_audio(cond_batch, steps, cfg_scale, sigma_min, sigma_max, sampler_type, device, save, save_prefix, modelinfo, batch_size=1, seed=-1, after_generate="randomize", counter=0, init_noise_level=1.0, init_audio=None, quantum=True):
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

    model, sample_rate, sample_size, _device = modelinfo
    b_pos, b_neg = cond_batch
    p_conditioning, p_batch_size = b_pos
    n_conditioning, n_batch_size = b_neg
    sample_size = p_conditioning[0]['seconds_total'] * sample_rate

    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Positive Conditioning:", p_conditioning)
    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Negative Conditioning:", n_conditioning)
    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Sample Size:", sample_size)
    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Sample Rate:", sample_rate)
    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Seconds:", sample_size / sample_rate)

    wt = None if init_audio is None else wav_bytes_to_tensor(init_audio, model, sample_rate, sample_size)
    output = generate_diffusion_cond(
        model,
        steps=steps,
        cfg_scale=cfg_scale,
        conditioning=p_conditioning,
        negative_conditioning=n_conditioning,
        sample_size=sample_size,
        sigma_min=sigma_min,
        sigma_max=sigma_max,
        sampler_type=sampler_type,
        device=_device,
        seed=seed,
        batch_size=p_batch_size,
        init_noise_level=init_noise_level, 
        init_audio=wt,
        quantum=quantum
    )
    
    gendata = locals()
    gendata['prompt'] = p_conditioning[0]['prompt']
    gendata['negative_prompt'] = n_conditioning[0]['prompt']

    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Raw Output:", output)

    output = rearrange(output, "b d n -> d (b n)")
    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Rearranged Output:", output)

    output = output.to(torch.float32).div(torch.max(torch.abs(output))).clamp(-1, 1).mul(32767).to(torch.int16).cpu()
    print("[comfyui-stable-audio-sampler, nodes.py, generate_audio] Transformed Output:", output)
    
    filepaths = None
    if save:
        filepaths = save_audio_files(output, sample_rate, save_prefix, counter, data=gendata)

    spectrogram = audio_spectrogram_image(output, sample_rate=sample_rate)
    audio_bytes = output.numpy().tobytes()

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
    
    return audio_bytes, sample_rate, spectrogram, filepaths


def get_model(model_filename=None, config=None, repo=None, half_precision=False, device_override=None):
    if model_filename:
        model_path = get_models_path(model_filename)
        if model_filename.endswith(".safetensors") or model_filename.endswith(".ckpt"):
            if not config:
                model_config = get_model_config()
            else:
                with open(config, 'r') as f:
                    model_config = json.load(f)
            model = create_model_from_config(model_config)
            print(f"[comfyui-stable-audio-sampler, nodes.py, get_model] Model path: {model_path}")
            model.load_state_dict(load_ckpt_state_dict(model_path))
        else:
            repo_id = "stabilityai/stable-audio-open-1.0" if not repo else repo
            print(f"[comfyui-stable-audio-sampler, nodes.py, get_model] Loading pretrained model {repo_id}")
            model, model_config = get_pretrained_model(repo_id)
        sample_rate = model_config["sample_rate"]
        sample_size = model_config["sample_size"]
    elif repo:
        if repo == "stabilityai/stable-audio-open-1.0":
            print(f"[comfyui-stable-audio-sampler, nodes.py, get_model] Loading pretrained model {repo}")
            model, model_config = get_pretrained_model(repo)
        else:
            json_path = config or repo_path(repo, "model_config.json")
            model_path = repo_path(repo, "model.safetensors")
            with open(json_path) as f:
                model_config = json.load(f)
            model = create_model_from_config(model_config)
            model.load_state_dict(load_ckpt_state_dict(model_path), strict=False)
        sample_rate = model_config["sample_rate"]
        sample_size = model_config["sample_size"]
    else:
        raise ValueError("You must specify an Audio Checkpoint or a Repo to load from.")
    
    # Rozwiązanie problemu dynamicznego wykrywania urządzenia i bezpiecznej alokacji bfloat16
    _device = device_override if device_override else ("cuda" if torch.cuda.is_available() else "cpu")
    
    if _device != "cpu":
        model = model.to(torch.bfloat16)
        print("[comfyui-stable-audio-sampler] Casted weights to bfloat16 in Host RAM")
        
    model = model.to(_device).requires_grad_(False)
    
    return (model, sample_rate, sample_size, _device)

def load_model(model_config=None, model_ckpt_path=None, pretrained_name=None, pretransform_ckpt_path=None, device="cuda", model_half=False):
    global model, sample_rate, sample_size
    
    if pretrained_name is not None:
        print(f"[comfyui-stable-audio-sampler, nodes.py, load_model] Loading pretrained model {pretrained_name}")
        model, model_config = get_pretrained_model(pretrained_name)

    elif model_config is not None and model_ckpt_path is not None:
        print(f"[comfyui-stable-audio-sampler, nodes.py, load_model] Creating model from config")
        model = create_model_from_config(model_config)

        print(f"[comfyui-stable-audio-sampler, nodes.py, load_model] Loading model checkpoint from {model_ckpt_path}")
        copy_state_dict(model, load_ckpt_state_dict(model_ckpt_path))

    sample_rate = model_config["sample_rate"]
    sample_size = model_config["sample_size"]

    if pretransform_ckpt_path is not None:
        print(f"[comfyui-stable-audio-sampler, nodes.py, load_model] Loading pretransform checkpoint from {pretransform_ckpt_path}")
        model.pretransform.load_state_dict(load_ckpt_state_dict(pretransform_ckpt_path), strict=False)
        print(f"[comfyui-stable-audio-sampler, nodes.py, load_model] Done loading pretransform")

    # Obsługa bfloat16 dla ładowania bezpośredniego
    if device != "cpu":
        model = model.to(torch.bfloat16)
        print("[comfyui-stable-audio-sampler] Casted model weights to bfloat16 in Host RAM")

    model.to(device).eval().requires_grad_(False)
        
    print(f"[comfyui-stable-audio-sampler, nodes.py, load_model] Done loading model")

    return model, model_config

import shutil
from urllib.parse import quote
def save_audio_files(output, sample_rate, filename_prefix, counter, data=None, save_temp=True):
    from datetime import datetime
    
    filename_prefix += ""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    wavname = f"{current_time}_{filename_prefix}" if not data else f"{current_time}_{replace_variables(filename_prefix, data)}"
    
    filepaths = []
    for i, audio in enumerate(output):
        if i > 0: 
            break
        fpath = f"{quote(wavname)}_{counter:04}.wav"
        file_path = os.path.join(output_dir, fpath)
        print(f"[comfyui-stable-audio-sampler, nodes.py, save_audio_files] Saving audio to {file_path}")
        torchaudio.save(file_path, audio.unsqueeze(0), sample_rate)
        filepaths.append(fpath)
        if save_temp:
            tpath = os.path.join(TEMP_FOLDER, "stableaudiosampler.wav")
            print(f"[comfyui-stable-audio-sampler, nodes.py, save_audio_files] Saving temp audio to: {tpath}")
            shutil.copyfile(file_path, tpath)
        counter += 1
    return filepaths

from aeiou.viz import spectrogram_image

def create_image_batch(spectrograms, batch_size):
    images = []
    for spec in spectrograms:
        im = spec.convert("RGB")
        im_tensor = torch.tensor(np.array(im))
        images.append(im_tensor)
    batch_tensor = torch.stack(images)
    return batch_tensor

class StableAudioSampler:
    def __init__(self):
        self.counter = 0
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "audio_model": ("SAOMODEL", {"forceInput": True}),
                "positive": ("CONDITIONING", {"forceInput": True}),
                "negative": ("CONDITIONING", {"forceInput": True}),
                "seed": ("INT", {"default": -1, "min": -1, "max": MAX_FP32}),
                "steps": ("INT", {"default": 100, "min": 1, "max": 10000}),
                "cfg_scale": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sigma_min": ("FLOAT", {"default": 0.3, "min": 0.01, "max": 1000.0, "step": 0.01}),
                "sigma_max": ("FLOAT", {"default": 500.0, "min": 0.0, "max": 1000.0, "step": 0.01}),
                "sampler_type": (SCHEDULERS, {"default": "dpmpp-3m-sde"}),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 20.0, "step": 0.01}),
                "save": ("BOOLEAN", {"default": True}),
                "save_prefix": ("STRING", {"default": "{prompt}-{seed}-{cfg_scale}-{steps}-{sigma_min}"}),
                "quantum": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "audio": (any, )
            }
        }

    RETURN_TYPES = (any, "INT", "IMAGE")
    RETURN_NAMES = ("audio", "sample_rate", "image")
    FUNCTION = "sample"
    OUTPUT_NODE = True

    CATEGORY = "audio/samplers"

    def sample(self, audio_model, positive, negative, seed, steps, cfg_scale, sigma_min, sigma_max, sampler_type, denoise, save, save_prefix, quantum=True, audio=None):
        _device = audio_model[3] if (isinstance(audio_model, tuple) and len(audio_model) > 3) else ("cuda" if torch.cuda.is_available() else "cpu")
        audio_bytes, sample_rate, spectrogram, filepaths = generate_audio(
            (positive, negative), 
            steps, 
            cfg_scale, 
            sigma_min, 
            sigma_max, 
            sampler_type, 
            _device, 
            save, 
            save_prefix, 
            audio_model, 
            seed=seed, 
            counter=self.counter, 
            init_noise_level=denoise, 
            init_audio=audio,
            quantum=quantum
        )
        spectrograms = create_image_batch([spectrogram], 1)
        return {"ui": {"paths": filepaths}, "result": (audio_bytes, sample_rate, spectrograms)}

class StableLoadAudioModel:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model_filename": (model_files, ),
            },
            "optional": {
                "model_config": (config_files, ),
                "repo": ("STRING", {"default": "stabilityai/stable-audio-open-1.0"}),
                "half_precision": ("BOOLEAN", {"default": False}),
                "force_cpu": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("SAOMODEL", )
    RETURN_NAMES = ("audio_model", )
    FUNCTION = "load"

    CATEGORY = "audio/loaders"

    def load(self, model_filename, model_config=None, repo=None, half_precision=None, force_cpu=None):
        mpath = get_models_path(model_config)
        modelinfo = get_model(model_filename=model_filename, config=mpath, repo=repo, half_precision=half_precision, device_override=None if not force_cpu else "cpu")
        return (modelinfo,)
    
class StableAudioPrompt:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning": ("CONDITIONING", {"forceInput": True}),
                "prompt": ("STRING", {"multiline": True}),
            }
        }
 
    RETURN_TYPES = ("CONDITIONING", )
    RETURN_NAMES = ("conditioning", )
    FUNCTION = "go"

    CATEGORY = "audio/conditioning"

    def go(self, conditioning, prompt):
        print("[comfyui-stable-audio-sampler, nodes.py, go] PROMPT", prompt)
        cond, batch_size = conditioning
        print("[comfyui-stable-audio-sampler, nodes.py, go]  cond, batch_size", cond, batch_size)
        o = []
        for v in cond:
            v['prompt'] = prompt
            o.append(v.copy())
        print("[comfyui-stable-audio-sampler, nodes.py, go] o, batch_size", o, batch_size)
        return ((o, batch_size), )

import time

class StableAudioConditioning:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "seconds_start": ("INT", {"default": 0, "min": 0, "max": 60, "step": 1, "display": "number"}),
                "seconds_total": ("INT", {"default": 30, "min": 0, "max": 60, "step": 1, "display": "number"}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 50, "step": 1, "display": "number"}),
            }
        }
 
    RETURN_TYPES = ("CONDITIONING", )
    RETURN_NAMES = ("conditioning", )
    FUNCTION = "go"

    CATEGORY = "audio/conditioning"

    def go(self, seconds_start, seconds_total, batch_size):
        conditioning = [{
            "prompt": None,
            "seconds_start": seconds_start,
            "seconds_total": seconds_total
        }]
        return ((conditioning, batch_size), )

    @classmethod
    def IS_CHANGED(s, image, string_field, int_field, float_field, print_to_screen):
        return time.time()

NODE_CLASS_MAPPINGS = {
    "StableAudioSampler": StableAudioSampler,
    "StableAudioLoadModel": StableLoadAudioModel,
    "StableAudioPrompt": StableAudioPrompt,
    "StableAudioConditioning": StableAudioConditioning,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "StableAudioSampler": "Stable Audio Sampler",
    "StableAudioLoadModel": "Load Stable Audio Model",
    "StableAudioPrompt": "Stable Audio Prompt",
    "StableAudioConditioning": "Stable Audio Pre-Conditioning"
}