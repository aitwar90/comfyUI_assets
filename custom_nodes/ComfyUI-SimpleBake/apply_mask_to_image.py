import torch
import numpy as np
from PIL import Image, ImageDraw

class ApplyMaskToImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
                "background_color": (["black", "white", "transparent"], {"default": "black"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_mask"
    CATEGORY = "MeshTools"

    def apply_mask(self, image, mask, background_color):
        # image: [batch, height, width, 3]
        # mask: [batch, height, width]
        
        img = image.clone()
        m = mask.clone()

        # 1. Dopasowanie wymiarów maski do obrazu
        if img.shape[1:3] != m.shape[1:3]:
            m = torch.nn.functional.interpolate(
                m.unsqueeze(1), 
                size=(img.shape[1], img.shape[2]), 
                mode="bilinear"
            ).squeeze(1)

        # 2. Logika wyboru tła
        if background_color == "black":
            m_rgb = m.unsqueeze(-1).repeat(1, 1, 1, 3)
            result = img * m_rgb
            return (result,)

        elif background_color == "white":
            m_rgb = m.unsqueeze(-1).repeat(1, 1, 1, 3)
            result = img * m_rgb + (1.0 - m_rgb)
            return (result,)

        else: # Opcja "transparent"
            # Sprawdzamy, czy obraz wejściowy ma już 3 kanały (RGB)
            # Wycinamy tylko RGB na wszelki wypadek
            rgb_part = img[:, :, :, :3]
            
            # Przygotowujemy maskę jako czwarty kanał [B, H, W, 1]
            alpha_part = m.unsqueeze(-1)
            
            # Łączymy RGB i Alpha w jeden tensor [B, H, W, 4]
            rgba_result = torch.cat((rgb_part, alpha_part), dim=-1)
            
            return (rgba_result,)