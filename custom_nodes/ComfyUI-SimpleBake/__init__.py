from .baker_node import SimpleTextureBaker
from .uv_mask_generator import MeshUVToMask 
from .apply_mask_to_image import ApplyMaskToImage
from .mesh_fbx_loader import LoadFBXMeshTool
from .image_path_loader import ImageWithPath
from .texture_mirror_save import TextureMirrorSave
from .image_max_size_calculator import ImageMaxSizeCalculator

NODE_CLASS_MAPPINGS = {
    "SimpleTextureBaker": SimpleTextureBaker,
    "MeshUVToMask": MeshUVToMask,
    "ApplyMaskToImage": ApplyMaskToImage,
    "LoadFBXMeshTool": LoadFBXMeshTool,
    "ImageWithPath": ImageWithPath,
    "TextureMirrorSave": TextureMirrorSave,
    "ImageMaxSizeCalculator": ImageMaxSizeCalculator
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SimpleTextureBaker": "Simple AI Texture Baker",
    "MeshUVToMask": "Mesh UV to Mask Generator",
    "ApplyMaskToImage": "Apply UV Mask to Image",
    "LoadFBXMeshTool": "Load FBX to Mesh",
    "ImageWithPath": "Load image with path returned",
    "TextureMirrorSave": "Save image in currend mirror tree of catalogs",
    "ImageMaxSizeCalculator": "Image Max Size Calculator"
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']