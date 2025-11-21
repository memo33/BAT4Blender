import bpy
import bpy_extras
from math import radians, sin, cos
from .Config import CAM_NAME
from .Enums import Zoom, Rotation
from .Utils import b4b_collection, find_object

camera_range = 190  # (initial) distance of camera from origin
angle_zoom = [radians(60), radians(55), radians(50), radians(45)]
angle_rotation = [radians(-67.5), radians(22.5), radians(112.5), radians(202.5)]


class Camera:
    @staticmethod
    def get_location_and_rotation(rotation, zoom):
        pitch = angle_zoom[min(zoom.value, len(angle_zoom) - 1)]  # zoom 4, 5 & 6 all use the same camera angle
        yaw = angle_rotation[rotation.value]

        x = camera_range * sin(pitch) * cos(yaw)
        y = camera_range * sin(pitch) * sin(yaw)
        z = camera_range * cos(pitch)
        loc = (x, y, z)
        rot = (pitch, 0, yaw + radians(90))  # need to add 90 for proper camera location in scene
        return [loc, rot]

    @staticmethod
    def set_camera(location, angles):
        cam = bpy.data.cameras.new(CAM_NAME)
        cam_ob = bpy.data.objects.new(CAM_NAME, cam)
        cam_ob.data.type = "ORTHO"
        cam_ob.data.clip_end = 10000  # in meters, i.e. 10 km seems sufficient
        cam_ob.rotation_mode = "XYZ"
        cam_ob.location = location
        cam_ob.rotation_euler = angles
        cam_ob.data.shift_x = 0.0
        cam_ob.data.shift_y = 0.0
        b4b_collection().objects.link(cam_ob)

    @staticmethod
    def update(rotation, zoom):
        (loc, rot) = Camera.get_location_and_rotation(rotation, zoom)
        cam = find_object(b4b_collection(), CAM_NAME)
        cam.location = loc
        cam.rotation_euler = rot
        bpy.context.view_layer.update()

    @staticmethod
    def add_to_scene():
        if find_object(b4b_collection(), CAM_NAME) is None:
            v = Rotation[bpy.context.scene.b4b.rotation]
            z = Zoom[bpy.context.scene.b4b.zoom]
            (location, rotation) = Camera.get_location_and_rotation(v, z)
            Camera.set_camera(location, rotation)

    @staticmethod
    def delete_from_scene():
        ob = find_object(b4b_collection(), CAM_NAME)
        if ob is not None:
            bpy.data.cameras.remove(ob.data, do_unlink=True)

    @staticmethod
    def camera_to_view3d():
        from .Canvas import Canvas
        override = Canvas.find_view3d()
        assert 'area' in override
        override['active_object'] = find_object(b4b_collection(), CAM_NAME)  # TODO what if None?
        with bpy.context.temp_override(**override):
            bpy.ops.view3d.object_as_camera()
            override['region'].data.update()  # updates the matrices so that the change of view takes affect immediately

    @staticmethod
    def _lod_in_cam_coords(cam, lod):
        xyz_coords = (lod.matrix_world @ v.co for v in lod.data.vertices)
        uvw_coords = [bpy_extras.object_utils.world_to_camera_view(bpy.context.scene, cam, c) for c in xyz_coords]
        return uvw_coords

    @staticmethod
    def lod_bounds_LRTB(cam, lod) -> (float, float, float, float):
        r"""Determine the bounding rectangle of the LOD in camera view.
        """
        uv_coords = Camera._lod_in_cam_coords(cam, lod)
        u_min = min(c[0] for c in uv_coords)
        u_max = max(c[0] for c in uv_coords)
        v_min = min(c[1] for c in uv_coords)
        v_max = max(c[1] for c in uv_coords)
        return u_min, u_max, v_max, v_min

    @staticmethod
    def distance_from_lod(cam, lod) -> float:
        r"""If negative, the camera needs to be moved back to fully put the LOD in view."""
        uvw_coords = Camera._lod_in_cam_coords(cam, lod)
        return min(c[2] for c in uvw_coords)
