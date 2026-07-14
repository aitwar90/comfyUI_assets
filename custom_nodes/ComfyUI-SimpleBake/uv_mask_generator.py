import torch
import numpy as np
from PIL import Image, ImageDraw

class MeshUVToMask:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mesh": ("MESH",),
                "width": ("INT", {"default": 1024, "min": 64, "max": 4096}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 4096}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "generate_mask"
    CATEGORY = "MeshTools"

    def generate_mask(self, mesh, width, height):
        # 1. Pobieramy dane UV dokładnie tak jak w Twoim Bakerze
        try:
            # Używamy .vt i .ft - tak jak w Twoim działającym kodzie
            vt_np = mesh.vt.detach().cpu().numpy()
            ft_np = mesh.ft.detach().int().cpu().numpy()
        except AttributeError:
            print("LOG: Obiekt mesh nie ma atrybutów .vt lub .ft!")
            return self.empty_result(width, height)

        # 2. Tworzymy czyste płótno
        mask_img = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask_img)

        # 3. Rysujemy siatkę UV
        # ft_np to lista trójkątów, gdzie każdy element to 3 indeksy do vt_np
        for tri_indices in ft_np:
            points = []
            for idx in tri_indices:
                u, v = vt_np[idx]
                
                # Skalowanie do pikseli
                x = u * width
                # Flip Y (standard w UV względem obrazu)
                y = v * height
                points.append((x, y))
            
            # Rysujemy wypełniony trójkąt na masce
            if len(points) == 3:
                draw.polygon(points, fill=255, outline=255)

        # 4. Konwersja na format ComfyUI
        out_image = np.array(mask_img).astype(np.float32) / 255.0
        out_tensor = torch.from_numpy(out_image).unsqueeze(0) # [1, H, W]
        
        # IMAGE potrzebuje [1, H, W, 3]
        out_image_rgb = out_tensor.unsqueeze(-1).repeat(1, 1, 1, 3)
        
        return (out_image_rgb, out_tensor)

    def empty_result(self, width, height):
        img = torch.zeros((1, height, width, 3))
        mask = torch.zeros((1, height, width))
        return (img, mask)