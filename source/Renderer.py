from __future__ import annotations

import bpy
from math import tan, atan
from mathutils import Vector
from .Config import LOD_NAME, CAM_NAME
from .Utils import tgi_formatter, get_relative_path_for, translate, instance_id
from .Enums import Zoom
from .Canvas import Canvas

# sd default
zoom_sizes = [8, 16, 32, 73, 146]  # from SFCameraRigHD.ms (horizontal extent of 16×16 cell in pixels)

_SLOP = 3


class Renderer:

    # @staticmethod
    # def enable_nodes():
    #     # switch on nodes
    #     bpy.context.scene.use_nodes = True
    #     tree = bpy.context.scene.node_tree
    #     links = tree.links

    #     # clear default nodes
    #     for n in tree.nodes:
    #         tree.nodes.remove(n)

    #     # create input render layer node
    #     rl = tree.nodes.new('CompositorNodeRLayers')
    #     rl.location = 185, 285

    #     # create output node
    #     v = tree.nodes.new('CompositorNodeViewer')
    #     v.location = 750, 210
    #     v.use_alpha = True

    #     # Links
    #     links.new(rl.outputs[0], v.inputs[0])  # link Image output to Viewer input

    @staticmethod
    def generate_output(v, z, gid, model_name: str):
        from .LOD import LOD
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'
        bpy.context.scene.render.film_transparent = True
        # First, position the camera for the current zoom and rotation. TODO Why does this not use v?
        canvas = Renderer.camera_manoeuvring(z)
        cam = bpy.context.scene.objects[CAM_NAME]
        lod = bpy.context.scene.objects[LOD_NAME]

        # Next, slice the LOD and export it.
        tile_indices = list(canvas.tiles())
        lod_slices = LOD.sliced(lod, cam, canvas)
        tile_indices_nonempty = [pos for pos in tile_indices if len(lod_slices[pos].data.polygons) > 0]
        assert tile_indices_nonempty, "LOD must not be completely empty, but should contain at least 1 polygon"
        for count, pos in enumerate(tile_indices_nonempty):
            iid = instance_id(z.value, v.value, count)
            mesh_name = f"{model_name}_UserModel_Z{z.value+1}{v.compass_name()}_{count}"
            mat_name = f"{iid:08X}_{model_name}_UserModel_Z{z.value+1}{v.compass_name()}"
            lod_slices[pos].name = lod_slices[pos].data.name = mesh_name  # keep object and data names in sync
            LOD.assign_material_name(lod_slices[pos], mat_name)
        filename = tgi_formatter(gid, z.value, v.value, 0)
        path = get_relative_path_for(f"{filename}.obj")
        LOD.export([lod_slices[pos] for pos in tile_indices_nonempty], path, v)
        # after export, we can discard LOD slices, as we only need tile indices.
        for lod_slice in lod_slices.values():
            bpy.data.meshes.remove(lod_slice.data)

        # Next, render the images and export them.
        # Renderer.enable_nodes()  # the nodes are mainly used as workaround to access the resulting rendered image (disabled to avoid conflicts)

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
            w, h = canvas.tile_dimensions_px(row, col)
            # img = bpy.data.images['Viewer Node']
            # img.save_render(path)
            # assert tuple(img.size) == (w, h), \
            #         f"Rendered image has unexpected size: {tuple(img.size)} instead of {w}×{h}"
            bpy.context.scene.render.filepath = path
            print(f"Rendering image ({w}×{h})")
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
    def camera_manoeuvring(zoom: Zoom) -> Canvas:
        r"""Adjust the offset, orthographic scale and resolution of the current
        camera so that the LOD fits into view, including a margin, and such
        that the orthographic scale results in a pixel-perfect display of the
        rendered image at the given zoom level.
        """
        lod = bpy.context.scene.objects[LOD_NAME]
        cam = bpy.context.scene.objects[CAM_NAME]
        bpy.context.scene.render.resolution_x = 256  # temporary for computation of os_reference
        bpy.context.scene.render.resolution_y = 256
        depsgraph = bpy.context.evaluated_depsgraph_get()
        bpy.context.scene.camera = cam  # apparently invoke default also checks if the scene has a camera..?

        # We use a 16×16 cell centered at origin as reference.
        # Its rendered (horizontal) dimension is zoom_sizes[zoom.value] in pixels.
        # Hence
        #   os_reference : zoom_sizes[zoom.value] == os_lod : dim_lod
        # where dim_lod is the actual maximum dimension of the LOD in pixels.
        os_reference = Renderer.get_orthographic_scale(depsgraph, cam, lod=None)
        os_lod = Renderer.get_orthographic_scale(depsgraph, cam, lod)
        dim_lod = zoom_sizes[zoom.value] * os_lod / os_reference
        cam.data.ortho_scale = os_lod
        canvas = Canvas.create(cam, lod, dim_lod=dim_lod, margin=_SLOP)

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
    def get_orthographic_scale(dg, cam, lod):
        if lod is None:
            # use 16×16 cell centered at origin as reference
            coordinates = [Vector([-8, -8, 0]), Vector([-8, 8, 0]), Vector([8, -8, 0]), Vector([8, 8, 0])]
        else:
            # This uses the same vertices as `Camera.lod_bounds_LRTB`, as that
            # determines the dimensions of the camera viewport.
            coordinates = [lod.matrix_world @ v.co for v in lod.data.vertices]
        loc, scale = cam.camera_fit_coords(dg, [vi for v in coordinates for vi in v])
        return scale
