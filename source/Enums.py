from enum import Enum


class Operators(Enum):
    PREVIEW = "object.b4b_preview",
    PREVIEW_DOWNSAMPLING = "object.b4b_preview_downsampling",
    RENDER = "object.b4b_render",
    LOD_FIT_ZOOM = "object.b4b_lod_fit_zoom",
    LOD_ADD = "object.b4b_lod_add",
    LOD_CUSTOM = "object.b4b_lod_custom",
    LOD_DELETE = "object.b4b_lod_delete",
    SUN_ADD = "object.b4b_sun_add",
    SUN_DELETE = "object.b4b_sun_delete",
    CAM_ADD = "object.b4b_camera_add",
    CAM_DELETE = "object.b4b_camera_delete",
    GID_RANDOMIZE = "object.b4b_gid_randomize",


class Rotation(Enum):
    SOUTH = 0
    EAST = 1
    NORTH = 2
    WEST = 3

    def compass_name(self) -> str:
        return self.name[0]


class Zoom(Enum):
    ONE = 0
    TWO = 1
    THREE = 2
    FOUR = 3
    FIVE = 4
