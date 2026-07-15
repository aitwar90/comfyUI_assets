import sys
import os

# Wymuszamy dodanie ścieżki, jeśli instalacja pip nie wystarczy
sys.path.append("/app/ComfyUI/custom-extensions/stable-audio-tools")

import torch
import torchaudio

try:
    from stable_audio_tools import get_pretrained_model
    from stable_audio_tools.inference.generation import generate_diffusion_cond
except ImportError:
    raise ImportError("Nie znaleziono 'stable_audio_tools'! Upewnij sie, ze rozszerzenie ComfyUI-StableAudioSampler jest zaladowane.")

class StableAudio3AdvancedGenerator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": ("STRING", {"default": "stabilityai/stable-audio-3-medium"}),
                "prompt": ("STRING", {"multiline": True, "default": "A beautiful cinematic melody, 120 BPM"}),
                "steps": ("INT", {"default": 100, "min": 1, "max": 500}),
                "cfg_scale": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 25.0}),
                "duration": ("INT", {"default": 30, "min": 1, "max": 600}),
                "seed": ("INT", {"default": -1}),
            },
            "optional": {
                "guide_audio": ("AUDIO",), 
                "init_noise_level": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "generate_audio"
    CATEGORY = "audio/StableAudio3"

    def generate_audio(self, model_name, prompt, steps, cfg_scale, duration, seed, 
                       guide_audio=None, init_noise_level=0.5):
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print(f"[SA3 Advanced] Ladowanie modelu: {model_name} przez natywne API stable-audio-tools...")
        
        # Wczytywanie modelu przez oficjalne narzędzie
        model, model_config = get_pretrained_model(model_name)
        model = model.to(device)

        sample_rate = model_config.get("sample_rate", 44100)
        
        if seed != -1:
            torch.manual_seed(seed)

        # Natywny słownik conditioning dla Stable Audio
        conditioning = [{
            "prompt": prompt,
            "seconds_start": 0,
            "seconds_total": duration
        }]

        init_audio_tensor = None

        if guide_audio is not None:
            print("[SA3 Advanced] Wykryto guide_audio. Wstrzykiwanie bazy tonacji...")
            waveform = guide_audio["waveform"]
            sr = guide_audio["sample_rate"]
            
            if waveform.dim() == 2:
                waveform = waveform.unsqueeze(0)

            if sr != sample_rate:
                waveform = torchaudio.functional.resample(waveform, sr, sample_rate)
                
            init_audio_tensor = waveform.to(device)

        print(f"[SA3 Advanced] Rozpoczynam generowanie. Steps: {steps}, CFG: {cfg_scale}")
        
        with torch.no_grad():
            output_audio = generate_diffusion_cond(
                model,
                steps=steps,
                cfg_scale=cfg_scale,
                conditioning=conditioning,
                sample_size=sample_rate * duration,
                sigma_min=0.3,
                sigma_max=500,
                sampler_type="dpmpp-3m-sde",
                device=device,
                init_audio=init_audio_tensor,
                init_noise_level=init_noise_level if init_audio_tensor is not None else None
            )

        audio_out = {
            "waveform": output_audio.cpu(),
            "sample_rate": sample_rate
        }

        return (audio_out,)