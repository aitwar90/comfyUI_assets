import os
import torch
import numpy as np
from PIL import Image
import folder_paths

class TextureMirrorSave:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "original_path": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save_mirror"
    CATEGORY = "SimpleBake/Utils"
    OUTPUT_NODE = True

    def save_mirror(self, image, original_path):
        try:
            input_dir = folder_paths.get_input_directory()
            output_dir = folder_paths.get_output_directory()
            
            # 1. Wyciągamy relatywną ścieżkę względem input
            # Jeśli original_path to /app/input/modele/atom/tekstura.png
            # rel_path będzie wynosić: modele/atom/tekstura.png
            rel_path = os.path.relpath(original_path, input_dir)
            print(f"Relatywna sciezka: {rel_path}")
            
            # 2. Tworzymy pełną ścieżkę w output
            final_output_path = os.path.join(output_dir, rel_path)
            print(final_output_path)
            # 3. Tworzymy foldery, jeśli nie istnieją
            os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

            # 4. Przetwarzanie i zapis
            i = 255. * image[0].cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            ext = os.path.splitext(final_output_path)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                img.save(final_output_path, quality=95, subsampling=0)
            else:
                img.save(final_output_path, optimize=True)

            print(f"✓ [MirrorSave] Plik zapisany w: {final_output_path}")
            return (final_output_path,)

        except Exception as e:
            print(f"× [MirrorSave] Błąd: {str(e)}")
            return (f"Error: {str(e)}",)