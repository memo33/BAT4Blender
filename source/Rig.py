import bpy
from .Enums import Zoom
from .LOD import LOD
from .Camera import Camera
from .Sun import Sun
from .Config import CAM_NAME, SUN_NAME, LODZ_NAME
from .Utils import b4b_collection


class Rig:
    @staticmethod
    def setup(rotation, zoom, hd: bool):
        coll = b4b_collection()
        if CAM_NAME not in coll.objects:
            Camera.add_to_scene()
        if SUN_NAME not in coll.objects:
            Sun.add_to_scene()
        Rig.lods_add()

        Camera.update(rotation, zoom)
        Sun.update(rotation)
        bpy.context.view_layer.update()

    @staticmethod
    def lods_add():
        coll = b4b_collection()
        for z, name in enumerate(LODZ_NAME):
            if name not in coll.objects:
                LOD.fit_new(Zoom(z))

    @staticmethod
    def lod_fit(zoom: Zoom):
        Rig.lod_delete(zoom)
        LOD.fit_new(zoom)

    @staticmethod
    def lod_delete(zoom: Zoom):
        name = LODZ_NAME[zoom.value]
        coll = b4b_collection()
        if name in coll.objects:
            ob = coll.objects[name]
            bpy.data.meshes.remove(ob.data, do_unlink=True, do_ui_user=True)
        bpy.context.view_layer.update()
