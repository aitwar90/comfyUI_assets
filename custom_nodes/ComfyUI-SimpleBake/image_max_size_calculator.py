import torch

class ImageMaxSizeCalculator:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "max_size": ("INT", {
                    "default": 2048, 
                    "min": 64, 
                    "max": 16384, 
                    "step": 64,
                    "display": "number"
                }),
            }
        }

    # Zwracamy jedną liczbę całkowitą (INT)
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("max_dimension",)
    FUNCTION = "calculate_max_size"
    CATEGORY = "SimpleBake/Utils"

    def calculate_max_size(self, image, max_size):
        # W ComfyUI obraz (tensor) ma kształt [batch_size, height, width, channels]
        height = image.shape[1]
        width = image.shape[2]
        
        # Szukamy dłuższego boku oryginalnego obrazka
        current_max_side = max(height, width)
        
        # Wybieramy mniejszą wartość: albo rzeczywisty dłuższy bok, albo podany limit
        final_size = min(current_max_side, max_size)
        
        print(f"[ImageMaxSizeCalculator] Org. wymiary: {width}x{height}. Dłuższy bok: {current_max_side}. Zwracam limitowane: {final_size}")
        
        return (final_size,)