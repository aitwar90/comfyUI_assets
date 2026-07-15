from .stable_audio_3_advanced import StableAudio3AdvancedGenerator

NODE_CLASS_MAPPINGS = {
    "StableAudio3AdvancedGenerator": StableAudio3AdvancedGenerator
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "StableAudio3AdvancedGenerator": "Stable Audio 3 Advanced Generator (Audio-to-Audio/Continuation)"
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]