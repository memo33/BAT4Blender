import bpy
import os

tid_fsh = "7ab50e44"
tid_s3d = "5ad0e817"


def instance_id(z, v, count):
    t = 0  # default to day render
    # This mapping should allow for more than 16 anim groups (for slicing of large BAT models).
    # Available bits for sliced tile IDs:
    # digit 8: 4 bits
    # digit 7: 2 bits (2 bits rotation)
    # digit 6: 1 bit (3 bits zoom)
    # digit 5: (1 bit nightlight) 3 bits
    assert count >= 0 and count < (1 << (4 + 2 + 1 + 3)), "This building is huge! It's just not going to work!"
    offset = ((count & 0x0380) << (3 + 2)) | ((count & 0x0040) << (3 + 2)) | ((count & 0x0030) << 2) | (count & 0x000f)
    iid = 0x30000 + t * 0x10000 + z * 0x100 + v * 0x10 + offset
    return iid


def tgi_formatter(gid: str, z, v, count, is_model=False, prefix=False):
    iid = instance_id(z, v, count)
    return "_".join(f"0x{i}" if prefix else i for i in [
        (tid_s3d if is_model else tid_fsh),
        gid,
        f"{iid:08x}",
    ])


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


def find_object(collection, name: str):
    r"""Look up an object in a collection by name. The name is treated as
    prefix to handle duplicate names such as `name.001`, for example when
    working with multiple scenes.
    """
    if name in collection.objects:
        return collection.objects[name]
    for ob in collection.objects:
        if ob.name.startswith(name):
            return ob
    return None


def b4b_collection():
    from .Config import COLLECTION_NAME
    for coll in bpy.context.scene.collection.children:
        if coll.name.startswith(COLLECTION_NAME):
            return coll
    coll = bpy.data.collections.new(COLLECTION_NAME)
    bpy.context.scene.collection.children.link(coll)
    return coll


def blend_file_name():
    return bpy.path.display_name_from_filepath(bpy.context.blend_data.filepath)


class BAT4BlenderUserError(Exception):
    pass
