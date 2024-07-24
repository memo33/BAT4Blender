import bpy
import os

tid = "7ab50e44"


def tgi_formatter(gid, z, v, no):
    t = 0  # default to day render
    iid = 0x30000 + t * 0x10000 + z * 0x100 + v * 0x10 + no
    return f"{tid}_{gid}_{iid:08x}"


def get_relative_path_for(fn):
    fp = bpy.data.filepath
    folder = os.path.dirname(fp)
    path = os.path.join(folder, fn)
    return path


def translate(value, left_min, left_max, right_min, right_max):
    # Figure out how 'wide' each range is
    left_span = left_max - left_min
    right_span = right_max - right_min

    # Convert the left range into a 0-1 range (float)
    value_scaled = float(value - left_min) / float(left_span)

    # Convert the 0-1 range into a value in the right range.
    return right_min + (value_scaled * right_span)


def clip(value: float, min: float, max: float) -> float:
    return min if value < min else max if value > max else value


def b4b_collection():
    from .Config import COLLECTION_NAME
    if COLLECTION_NAME in bpy.data.collections:
        return bpy.data.collections[COLLECTION_NAME]
    else:
        c = bpy.data.collections.new(COLLECTION_NAME)
        bpy.context.scene.collection.children.link(c)
        return c
