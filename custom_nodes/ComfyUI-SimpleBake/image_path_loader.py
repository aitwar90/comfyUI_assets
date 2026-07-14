import os
import torch
import numpy as np
from PIL import Image, ImageOps
import folder_paths

class ImageWithPath:
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        # Dodajemy obsługę podfolderów, abyś mógł wybierać pliki z głębi struktury
        for root, dirs, filenames in os.walk(input_dir):
            for f in filenames:
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    rel_path = os.path.relpath(os.path.join(root, f), input_dir)
                    if rel_path not in files:
                        files.append(rel_path)
        
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("IMAGE", "MASK", "PATH")
    FUNCTION = "load_image_with_path"
    CATEGORY = "SimpleBake/Utils"

    def load_image_with_path(self, image):
        input_dir = folder_paths.get_input_directory()
        print((f"Input dir {input_dir}"))
        # 'image' to np. "AssetyPrzerobione/Dry_Trees/Materials/Bark.jpg"
        # Musimy stworzyć pełną ścieżkę absolutną dla systemu operacyjnego
        full_path = os.path.abspath(os.path.join(input_dir, image))
        print((f"Full path {full_path}"))
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Nie znaleziono pliku: {full_path}")

        img = Image.open(full_path)
        img = ImageOps.exif_transpose(img)
        image_data = img.convert("RGB")
        image_data = np.array(image_data).astype(np.float32) / 255.0
        image_data = torch.from_numpy(image_data)[None,]
        
        if 'A' in img.getbands():
            mask = np.array(img.getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
            mask = mask.unsqueeze(0) # Dodajemy wymiar Batch [1, H, W]
        else:
            mask = torch.zeros((1,64,64), dtype=torch.float32)

        return (image_data, mask, full_path)