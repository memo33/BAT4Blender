from __future__ import annotations

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
    r"""A 2D rendering canvas, divided into tiles of size at most 256 px.
    """
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
        from .Camera import Camera
        # convert from 3d space to 2d camera space
        u_min, u_max, v_max, v_min = Camera.lod_bounds_LRTB(cam, lod)

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

    @staticmethod
    def find_view3d():
        for area in bpy.context.window.screen.areas:
            if area.type == 'VIEW_3D':
                v3d = area.spaces[0]
                # rv3d = v3d.region_3d
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return {'area': area, 'space': v3d, 'region': region}
        return {}

    @staticmethod
    def _plane_from_vertices(name: str, bottom_left: Vector, bottom_right: Vector, top_left: Vector, top_right: Vector):
        mesh = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        b4b_collection().objects.link(obj)
        faces = [(0, 1, 3, 2)]
        mesh.from_pydata([bottom_left, bottom_right, top_left, top_right], [], faces)
        mesh.update(calc_edges=True)
        return obj

    @staticmethod
    def _mean(vertices: list) -> Vector:
        assert vertices, "vertices list must not be empty"
        return sum(vertices[1:], vertices[0]) / len(vertices)

    def create_tile_object(self, cam, row: int, col: int):
        r"""Create a plane object representing the canvas tile physically."""
        l, r, t, b = self.tile_border_fractional_LRTB(row=row, col=col)
        cam_verts = cam.data.view_frame(scene=bpy.context.scene)  # with scene keyword, this shrinks shorter dimension to fit resolution
        cam_center = Canvas._mean(cam_verts)
        assert len(cam_verts) == 4
        bot_l, = [v for v in cam_verts if v[0] < cam_center[0] and v[1] < cam_center[1]]
        bot_r, = [v for v in cam_verts if v[0] > cam_center[0] and v[1] < cam_center[1]]
        top_l, = [v for v in cam_verts if v[0] < cam_center[0] and v[1] > cam_center[1]]
        top_r, = [v for v in cam_verts if v[0] > cam_center[0] and v[1] > cam_center[1]]

        def weighted(s0, s1) -> Vector:
            return (1-s0) * ((1-s1) * top_l + s1 * bot_l) + s0 * ((1-s1) * top_r + s1 * bot_r)
            # return top_l + s0 * (top_r - top_l) + s1 * (bot_l - top_l)

        obj = Canvas._plane_from_vertices(
                'b4b_canvas_tile',
                bottom_left=weighted(l, b),
                bottom_right=weighted(r, b),
                top_left=weighted(l, t),
                top_right=weighted(r, t))
        obj.location = cam.location
        obj.scale = cam.scale
        obj.rotation_euler = cam.rotation_euler
        obj.hide_render = True
        obj.display_type = 'WIRE'

        # TODO if cam is new, maybe we need to call bpy.context.view_layer.update() for up-to-date matrices
        obj.parent = cam
        obj.matrix_parent_inverse = cam.matrix_world.inverted()  # TODO or .matrix_local?

        return obj


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
        v.use_alpha = True

        # Links
        links.new(rl.outputs[0], v.inputs[0])  # link Image output to Viewer input

    @staticmethod
    def generate_output(v, z, gid):
        from .LOD import LOD
        from .Camera import Camera
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'
        bpy.context.scene.render.film_transparent = True
        # First, position the camera for the current zoom and rotation. TODO Why does this not use v?
        canvas = Renderer.camera_manoeuvring(z)
        Camera.camera_to_view3d()  # important to call this *after* manoeuvering the camera and *before* slicing the LOD
        cam = bpy.context.scene.objects[CAM_NAME]
        lod = bpy.context.scene.objects[LOD_NAME]

        # Next, slice the LOD and export it.
        tile_indices = list(canvas.tiles())
        canvas_tiles = {pos: canvas.create_tile_object(cam, row=pos[0], col=pos[1]) for pos in tile_indices}
        lod_slices = {pos: LOD.slice(lod, cam, canvas_tiles[pos]) for pos in tile_indices}
        tile_indices_nonempty = [pos for pos in tile_indices if len(lod_slices[pos].data.polygons) > 0]
        assert tile_indices_nonempty, "LOD must not be completely empty, but should contain at least 1 polygon"
        filename = tgi_formatter(gid, z.value, v.value, 0)
        path = get_relative_path_for(f"{filename}.obj")
        LOD.export([lod_slices[pos] for pos in tile_indices_nonempty], path, v)
        # after export, we can discard LOD slices and canvas tiles, as we only need tile indices.
        for pos in tile_indices:
            bpy.data.meshes.remove(lod_slices[pos].data)
            bpy.data.meshes.remove(canvas_tiles[pos].data)

        # Next, render the images and export them.
        if canvas.num_rows > 1 or canvas.num_columns > 1:
            Renderer.enable_nodes()  # the nodes are mainly used as workaround to access the resulting rendered image

            for count, (row, col) in enumerate(tile_indices_nonempty):
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
        bpy.context.scene.render.film_transparent = True
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
        from .Camera import Camera
        cam.data.shift_x = 0.0
        cam.data.shift_y = 0.0
        # get the 2d camera view coordinates for the LOD... is this a correct assumption?
        x_min, x_max, y_max, y_min = Camera.lod_bounds_LRTB(cam, lod)

        # grab outer left and top vertex in the camera view
        # map their 0..1 range to pixels to determine how far the LOD is from the left and top edges
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
        # This uses the same vertices as `Camera.lod_bounds_LRTB`, as that
        # determines the dimensions of the camera viewport.
        coordinates = (lod.matrix_world @ v.co for v in lod.data.vertices)
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
