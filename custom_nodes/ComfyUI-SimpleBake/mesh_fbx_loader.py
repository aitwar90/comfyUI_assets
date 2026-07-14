import os
import torch
import importlib
import folder_paths as comfy_paths
import trimesh

# --- DYNAMICZNY IMPORT KLASY MESH ---
# Próbujemy znaleźć klasę Mesh w zainstalowanych nodach 3D-MeshTool
try:
    # Ścieżka relatywna do folderu custom_nodes
    mesh_module = importlib.import_module("custom_nodes.ComfyUI-3D-MeshTool.moduel.mesh_class")
    Mesh = mesh_module.Mesh
except ImportError:
    # Jeśli folder ma inną nazwę, szukamy bezpośrednio w sys.modules
    raise ImportError("Nie znaleziono ComfyUI-3D-MeshTool. Upewnij się, że ten dodatek jest zainstalowany.")

class LoadFBXMeshTool:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "fbx_path": ("STRING", {"default": "input/model.fbx"}),
            }
        }

    RETURN_TYPES = ("MESH",)
    RETURN_NAMES = ("mesh",)
    FUNCTION = "process"
    CATEGORY = "3D_MeshTool/Basics"

    def process(self, fbx_path):
        # 1. Obsługa ścieżki
        if not os.path.isabs(fbx_path):
            full_path = os.path.join(comfy_paths.get_input_directory(), fbx_path)
        else:
            full_path = fbx_path

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Nie znaleziono pliku: {full_path}")

        print(f"Ładowanie FBX przez Trimesh: {full_path}")

        # 2. Ładowanie FBX za pomocą trimesh (lekka biblioteka)
        # Trimesh zazwyczaj radzi sobie z FBX jeśli zainstalowane jest 'pyfbx' lub 'collada'
        # Jeśli nie, konwertuje go wewnętrznie.
        scene_or_mesh = trimesh.load(full_path)

        # FBX często wczytuje się jako 'Scene'. Musimy połączyć obiekty w jeden Mesh.
        if isinstance(scene_or_mesh, trimesh.Scene):
            geo = scene_or_mesh.dump(concatenate=True)
        else:
            geo = scene_or_mesh

        # 3. Konwersja na format kompatybilny z 3D-MeshTool
        # 3D-MeshTool używa własnej klasy Mesh, która oczekuje tensorów torch.
        
        custom_mesh = Mesh()
        
        # Wierzchołki (Vertices)
        custom_mesh.v = torch.from_numpy(geo.vertices).float().cuda() if torch.cuda.is_available() else torch.from_numpy(geo.vertices).float()
        
        # Ściany (Faces)
        custom_mesh.f = torch.from_numpy(geo.faces).int().cuda() if torch.cuda.is_available() else torch.from_numpy(geo.faces).int()

        # UV (jeśli istnieją)
        if hasattr(geo.visual, 'uv'):
            custom_mesh.vt = torch.from_numpy(geo.visual.uv).float().cuda() if torch.cuda.is_available() else torch.from_numpy(geo.visual.uv).float()
            # 3D-MeshTool często oczekuje, że ft (face texture) to to samo co f
            custom_mesh.ft = custom_mesh.f
        
        # Normale
        if hasattr(geo, 'vertex_normals'):
            custom_mesh.vn = torch.from_numpy(geo.vertex_normals).float().cuda() if torch.cuda.is_available() else torch.from_numpy(geo.vertex_normals).float()
            custom_mesh.fn = custom_mesh.f

        print(f"Sukces! Załadowano {len(custom_mesh.v)} wierzchołków.")
        
        return (custom_mesh,)

# Rejestracja noda
NODE_CLASS_MAPPINGS = {
    "LoadFBXMeshTool": LoadFBXMeshTool
}

NODE_DISPLAY_NAMES_MAPPINGS = {
    "LoadFBXMeshTool": "Load FBX (MeshTool Direct)"
}