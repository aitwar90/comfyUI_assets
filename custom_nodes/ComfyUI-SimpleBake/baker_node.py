import torch
import numpy as np
import cv2
import logging

class SimpleTextureBaker:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mesh": ("MESH",), 
                "ai_image": ("IMAGE",), 
                "texture_resolution": ("INT", {"default": 1024, "min": 512, "max": 4096}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("baked_texture",)
    FUNCTION = "execute_bake"
    CATEGORY = "3D_MeshTool/Custom"

    def execute_bake(self, mesh, ai_image, texture_resolution):
        try:
            img = ai_image[0].cpu().numpy()
            img = (img * 255).astype(np.uint8)
            img_h, img_w = img.shape[:2]
            out_tex = np.zeros((texture_resolution, texture_resolution, 3), dtype=np.uint8)

            # Pobranie danych .v, .f, .vt, .ft
            v_np = mesh.v.detach().cpu().numpy()
            f_np = mesh.f.detach().int().cpu().numpy()
            vt_np = mesh.vt.detach().cpu().numpy()
            ft_np = mesh.ft.detach().int().cpu().numpy()

            for i in range(len(f_np)):
                f_idx = f_np[i]
                ft_idx = ft_np[i]
                
                # Wierzchołki trójkąta
                tri_v = v_np[f_idx]
                
                # 1. Obliczanie normalnej trójkąta (wektor kierunku)
                edge1 = tri_v[1] - tri_v[0]
                edge2 = tri_v[2] - tri_v[0]
                normal = np.cross(edge1, edge2)
                normal = normal / (np.linalg.norm(normal) + 1e-6)
                abs_normal = np.abs(normal)

                # 2. Wybór płaszczyzny rzutowania (Box Projection)
                # Sprawdzamy, która oś dominuje w normalnej
                if abs_normal[2] > abs_normal[0] and abs_normal[2] > abs_normal[1]:
                    # Ścianka góra/dół (Z) -> rzutujemy X, Y
                    src_coords = tri_v[:, :2]
                elif abs_normal[0] > abs_normal[1]:
                    # Ścianka boczna (X) -> rzutujemy Z, Y
                    src_coords = tri_v[:, [2, 1]]
                else:
                    # Ścianka przód/tył (Y) -> rzutujemy X, Z
                    src_coords = tri_v[:, [0, 2]]

                # Skalowanie współrzędnych 3D do wymiarów obrazka AI (-1,1 -> 0,1 -> px)
                src = ((src_coords + 1.0) / 2.0 * [img_w, img_h]).astype(np.float32)

                # Mapa UV docelowa (z siatki xatlas)
                dst = np.array([vt_np[idx] for idx in ft_idx], dtype=np.float32)
                dst[:, 1] = 1.0 - dst[:, 1] # Flip Y dla zgodności z UV
                dst = (dst * texture_resolution).astype(np.float32)

                try:
                    matrix = cv2.getAffineTransform(src, dst)
                    warped = cv2.warpAffine(img, matrix, (texture_resolution, texture_resolution))
                    mask = np.zeros((texture_resolution, texture_resolution), dtype=np.uint8)
                    cv2.fillConvexPoly(mask, dst.astype(np.int32), 255)
                    np.copyto(out_tex, warped, where=(mask[:,:,None] == 255))
                except:
                    continue

            res = torch.from_numpy(out_tex.astype(np.float32) / 255.0).unsqueeze(0)
            return (res,)

        except Exception as e:
            logging.error(f"SimpleBake Error: {str(e)}")
            return (ai_image,)