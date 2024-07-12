from __future__ import annotations
import bpy_extras

from collections.abc import Iterator
from math import tan, atan, ceil
from mathutils import Vector
from .Config import *
from .Utils import *
from .Enums import Rotation, Zoom

# render dimensions need to take view into account
# sd default
render_dimension = [16, 32, 64, 128, 256]

_MAX_TILE_SIZE_PX = 256
_MIN_TILE_SIZE_PX = 4
_SLOP = 3


class Canvas:
    width_px: int
    height_px: int
    num_columns: int
    num_rows: int

    def __init__(self, width_px: int, height_px: int):
        assert width_px % _MIN_TILE_SIZE_PX == 0 and height_px % _MIN_TILE_SIZE_PX == 0, "FSH dimensions must be multiple of 4"
        self.width_px = width_px
        self.height_px = height_px
        self.num_columns = ceil(width_px / _MAX_TILE_SIZE_PX)
        self.num_rows = ceil(height_px / _MAX_TILE_SIZE_PX)

    @staticmethod
    def create(cam, lod, dim_lod: float) -> Canvas:
        r"""Create a Canvas for the current LOD and camera, and include a slop margin.
        The dim_lod parameter is a factor to map the LOD dimensions from the 0..1 range to the pixel range (i.e. [0,256) for zoom 5).
        """
        # convert from 3d space to 2d camera space
        xyz_coords = [lod.matrix_world @ Vector(corner) for corner in lod.bound_box]
        uv_coords = [bpy_extras.object_utils.world_to_camera_view(bpy.context.scene, cam, c) for c in xyz_coords]
        u_min = min(c[0] for c in uv_coords)
        u_max = max(c[0] for c in uv_coords)
        v_min = min(c[1] for c in uv_coords)
        v_max = max(c[1] for c in uv_coords)

        max_res = max(bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y)
        dim_u = (u_max - u_min) * dim_lod * (bpy.context.scene.render.resolution_x / max_res)
        dim_v = (v_max - v_min) * dim_lod * (bpy.context.scene.render.resolution_y / max_res)

        w = Canvas._round_up_to_fsh_chunk(dim_u + 2 * _SLOP)
        h = Canvas._round_up_to_fsh_chunk(dim_v + 2 * _SLOP)
        return Canvas(width_px=w, height_px=h)

    @staticmethod
    def _round_up_to_fsh_chunk(f) -> int:
        cnt, rem = divmod(ceil(f), _MAX_TILE_SIZE_PX)
        result = cnt * _MAX_TILE_SIZE_PX + (0 if rem == 0 else
                                            8 if rem <= 8 else
                                            16 if rem <= 16 else
                                            32 if rem <= 32 else
                                            64 if rem <= 64 else
                                            128 if rem <= 128 else
                                            _MAX_TILE_SIZE_PX)
        return result

    def tile_dimensions_px(self, row: int, col: int) -> (int, int):
        assert 0 <= row and row < self.num_rows
        assert 0 <= col and col < self.num_columns
        w = self.width_px - col * _MAX_TILE_SIZE_PX if col == self.num_columns - 1  else _MAX_TILE_SIZE_PX
        h = self.height_px - row * _MAX_TILE_SIZE_PX if row == self.num_rows - 1  else _MAX_TILE_SIZE_PX
        return w, h

    def tiles(self) -> Iterator[(int, int)]:
        for row in range(self.num_rows):
            for col in range(self.num_columns):
                yield row, col

    def tile_border_fractional_LRTB(self, row: int, col: int) -> (float, float, float, float):
        l = col * _MAX_TILE_SIZE_PX / self.width_px
        r = min((col+1) * _MAX_TILE_SIZE_PX, self.width_px) / self.width_px
        t = row * _MAX_TILE_SIZE_PX / self.height_px
        b = min((row+1) * _MAX_TILE_SIZE_PX, self.height_px) / self.height_px
        return l, r, t, b


class Renderer:

    @staticmethod
    def enable_nodes():
        # switch on nodes
        bpy.context.scene.use_nodes = True
        tree = bpy.context.scene.node_tree
        links = tree.links

        # clear default nodes
        for n in tree.nodes:
            tree.nodes.remove(n)

        # create input render layer node
        rl = tree.nodes.new('CompositorNodeRLayers')
        rl.location = 185, 285

        # create output node
        v = tree.nodes.new('CompositorNodeViewer')
        v.location = 750, 210
        v.use_alpha = False

        # Links
        links.new(rl.outputs[0], v.inputs[0])  # link Image output to Viewer input

    @staticmethod
    def generate_output(v, z, gid):

        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'
        canvas = Renderer.camera_manoeuvring(z)

        if canvas.num_rows > 1 or canvas.num_columns > 1:
            Renderer.enable_nodes()  # the nodes are mainly used as workaround to access the resulting rendered image

            for count, (row, col) in enumerate(canvas.tiles()):
                left, right, top, bottom = canvas.tile_border_fractional_LRTB(row, col)

                bpy.context.scene.render.use_border = True
                bpy.context.scene.render.use_crop_to_border = True
                bpy.context.scene.render.border_min_x = left
                bpy.context.scene.render.border_max_x = right
                bpy.context.scene.render.border_min_y = 1 - bottom
                bpy.context.scene.render.border_max_y = 1 - top

                bpy.ops.render.render()
                filename = tgi_formatter(gid, z.value, v.value, count)
                path = get_relative_path_for(f"{filename}.png")
                img = bpy.data.images['Viewer Node']
                img.save_render(path)
                assert tuple(img.size) == canvas.tile_dimensions_px(row, col), \
                        f"Rendered image has unexpected size: {tuple(img.size)} instead of {canvas.tile_dimensions_px(row, col)}"
                print(f"Saved image {path}")

        else:
            filename = tgi_formatter(gid, z.value, v.value, 0)
            bpy.context.scene.render.filepath = get_relative_path_for(f"{filename}.png")
            print("rendering single image")
            bpy.ops.render.render(write_still=True)

    @staticmethod
    def generate_preview(zoom):
        Renderer.camera_manoeuvring(zoom)
        #  reset camera border in case a large view has been rendered.. may want to do this after rendering instead
        bpy.context.scene.render.border_min_x = 0.0
        bpy.context.scene.render.border_max_x = 1.0
        bpy.context.scene.render.border_min_y = 0.0
        bpy.context.scene.render.border_max_y = 1.0
        bpy.ops.render.render('INVOKE_DEFAULT', write_still=False)

    @staticmethod
    def check_scale():
        lod = bpy.context.scene.objects[LOD_NAME]
        cam = bpy.context.scene.objects[CAM_NAME]
        depsgraph = bpy.context.evaluated_depsgraph_get()
        os_lod = Renderer.get_orthographic_scale(depsgraph, cam, lod)
        os_gmax = Renderer.get_orthographic_scale_gmax(cam.location[2])
        default_os = Renderer.get_orthographic_scale_gmax(134.35028)  # default location for zoom 5. .
        final_os = default_os + (default_os - os_gmax)
        s_f = Renderer.get_scale_factor(os_lod, final_os)
        return s_f >= 2


    @staticmethod
    def camera_manoeuvring(zoom: Zoom) -> Canvas:
        lod = bpy.context.scene.objects[LOD_NAME]
        cam = bpy.context.scene.objects[CAM_NAME]
        depsgraph = bpy.context.evaluated_depsgraph_get()
        bpy.context.scene.camera = cam  # apparently invoke default also checks if the scene has a camera..?

        os_lod = Renderer.get_orthographic_scale(depsgraph, cam, lod)
        os_gmax = Renderer.get_orthographic_scale_gmax(cam.location[2])
        default_os = Renderer.get_orthographic_scale_gmax(134.35028)  # default location for zoom 5. .
        final_os = default_os + (default_os - os_gmax)

        # Note that final_os is independent of the LOD and satisfies the following law:
        # final_os : render_dimension[zoom.value] == os_lod : "actual pixel dimension of LOD"
        dim_lod = render_dimension[zoom.value] * os_lod / final_os
        cam.data.ortho_scale = os_lod
        canvas = Canvas.create(cam, lod, dim_lod=dim_lod)

        # Adjustment of the orthographic scale to account for the added slop margin and the rounding to integer resolutions:
        cam.data.ortho_scale *= max(canvas.width_px, canvas.height_px) / dim_lod
        bpy.context.scene.render.resolution_x = canvas.width_px
        bpy.context.scene.render.resolution_y = canvas.height_px
        Renderer.offset_camera(cam, lod, canvas.width_px, canvas.height_px)

        print(f"Output dimensions are {canvas.width_px}×{canvas.height_px}")
        return canvas

    @staticmethod
    def offset_camera(cam, lod, dim_x, dim_y):
        r"""Position the camera such that the LOD is aligned with the top and
        left edges of the rendered image, accounting for the slop margin.
        """
        cam.data.shift_x = 0.0
        cam.data.shift_y = 0.0
        # get the 2d camera view coordinates for the LOD... is this a correct assumption?
        coordinates = [lod.matrix_world @ Vector(corner) for corner in lod.bound_box]
        coords_2d = [bpy_extras.object_utils.world_to_camera_view(bpy.context.scene, cam, coord) for coord in
                     coordinates]

        # grab outer left and top vertex in the camera view
        # map their 0..1 range to pixels to determine how far the LOD is from the left and top edges
        x_min = min(c[0] for c in coords_2d)
        y_max = max(c[1] for c in coords_2d)
        x_left = x_min * dim_x
        y_top = y_max * dim_y

        x_d = translate(x_left - _SLOP, 0, dim_x, 0.0, dim_x / max(dim_x, dim_y))
        y_d = translate(y_top - (dim_y - _SLOP), 0, dim_y, 0.0, dim_y / max(dim_x, dim_y))
        cam.data.shift_x = x_d
        cam.data.shift_y = y_d

    @staticmethod
    def get_scale_factor(os_lod, os_gmax):
        assert os_gmax > 0 and os_lod > 0
        factor = 1
        while os_lod > (os_gmax * factor):
            factor += 1
        return factor

    @staticmethod
    def get_orthographic_scale(dg, cam, lod):
        coordinates = [lod.matrix_world @ Vector(corner) for corner in lod.bound_box]
        coordinates_flat = [vi for v in coordinates for vi in v]
        loc, scale = cam.camera_fit_coords(dg, coordinates_flat)
        return scale

    # NOTE currently passing in camera height depending on zoom
    # not sure if that's correct, i.e. perhaps the OS for z5 should be used throughout
    @staticmethod
    def get_orthographic_scale_gmax(cam_z):
        unit = 16
        targetWidth2 = unit + 8  # unit cube with render slop applied as specified in gmax script
        renderFov = 2 * (atan(targetWidth2 / 190.0))
        return (cam_z + unit / 2) * tan(
            renderFov)  # assuming the gmax camera focus in on lod center height which seems correct
