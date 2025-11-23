import bpy
from math import radians, atan2
from mathutils import Vector
from .Config import SUN_NAME
from .Enums import Rotation
from .Utils import b4b_collection, find_object


def _bat4max_sun_orientation():
    # note that sun angle of BATs differs from in-game sun
    x, y, z = -474, -352, 575  # South sun location in BAT4Max
    return 0, atan2(Vector([x, y]).length, z), atan2(y, x)  # 0°, 45.757°, 36.598°-180°


def get_sun_rotation(rotation):
    s_x, s_y, s_z = _bat4max_sun_orientation()
    match rotation:
        case Rotation.SOUTH: return s_x, s_y, s_z
        case Rotation.EAST:  return s_x, s_y, s_z + radians(90)
        case Rotation.NORTH: return s_x, s_y, s_z + radians(180)
        case Rotation.WEST:  return s_x, s_y, s_z + radians(270)


def delete_from_scene():
    ob = find_object(b4b_collection(), SUN_NAME)
    if ob is not None:
        bpy.data.lights.remove(ob.data, do_unlink=True)
