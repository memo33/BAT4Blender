from __future__ import annotations

import bpy
from mathutils import Vector
from .Config import LODZ_NAME, CAM_NAME
from .Utils import tgi_formatter, get_relative_path_for, translate, instance_id, b4b_collection, find_object
from .Enums import Zoom, Rotation
from .Canvas import Canvas
from pathlib import Path

# sd default
zoom_sizes = [8, 16, 32, 73, 146]  # from SFCameraRigHD.ms (horizontal extent of 16×16 cell in pixels)
zoom_sizes_hd = [8, 16, 32, 73, 292]

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
    def render_pre(z: Zoom, v: Rotation, gid, model_name: str, hd: bool):
        r"""This function is invoked by the modal operator before the rendering of this view started.
        We do some setup such as slicing and exporting the LODs.
        """
        from .LOD import LOD
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'
        bpy.context.scene.render.film_transparent = True
        # First, position the camera for the current zoom and rotation. TODO Why does this not use v?
        canvas = Renderer.camera_manoeuvring(z, hd=hd)
        coll = b4b_collection()
        cam = find_object(coll, CAM_NAME)
        lod = find_object(coll, LODZ_NAME[z.value])

        # Next, slice the LOD and export it.
        tile_indices = list(canvas.tiles())
        lod_slices = LOD.sliced(lod, cam, canvas)
        tile_indices_nonempty = [pos for pos in tile_indices if len(lod_slices[pos].data.polygons) > 0]
        assert tile_indices_nonempty, "LOD must not be completely empty, but should contain at least 1 polygon"
        materials = []
        for count, pos in enumerate(tile_indices_nonempty):
            iid = instance_id(z.value, v.value, count)
            mesh_name = f"{model_name}_UserModel_Z{z.value+1}{v.compass_name()}_{count}"
            mat_name = f"{iid:08X}_{model_name}_UserModel_Z{z.value+1}{v.compass_name()}"
            lod_slices[pos].name = lod_slices[pos].data.name = mesh_name  # keep object and data names in sync
            materials.append(LOD.assign_material_name(lod_slices[pos], mat_name))
        stem = tgi_formatter(gid, z.value, v.value, 0, is_model=True)
        obj_path = get_relative_path_for(f"{stem}.obj")
        mtl_path = get_relative_path_for(f"{stem}.mtl")
        LOD.export([lod_slices[pos] for pos in tile_indices_nonempty], obj_path, v)
        try:
            # .obj export creates .mtl material files that are not needed
            Path(mtl_path).unlink(missing_ok=True)
        except IOError:
            pass  # ignored
        # after export, we can discard LOD slices, as we only need tile indices.
        for lod_slice in lod_slices.values():
            bpy.data.meshes.remove(lod_slice.data)
        for mat in materials:
            bpy.data.materials.remove(mat)

        # Render the full image to a temporary location
        bpy.context.scene.render.use_border = False  # always render the full frame
        tmp_path = get_relative_path_for(f"{tgi_formatter(gid, z.value, v.value, 0)}.tmp.png")
        bpy.context.scene.render.filepath = tmp_path
        print(f"Rendering image ({canvas.width_px}×{canvas.height_px})")
        return canvas, tile_indices_nonempty, tmp_path, obj_path

    @staticmethod
    def render_post(z: Zoom, v: Rotation, gid, canvas: Canvas, tile_indices_nonempty: list[(int, int)], tmp_path: str, obj_path: str):
        r"""This function is invoked by the modal operator after the rendering of this view finished,
        and yields the generated output files.
        We slice the rendered image here.
        """
        import numpy as np
        import os
        from pathlib import Path
        if not Path(tmp_path).is_file():
            return  # this can happen when rendering was cancelled
        yield obj_path
        img = bpy.data.images.load(tmp_path)
        try:
            assert tuple(img.size) == (canvas.width_px, canvas.height_px), \
                    f"Rendered image has unexpected size: {tuple(img.size)} instead of {canvas.width_px}×{canvas.height_px}"
            arr = np.asarray(img.pixels).reshape((img.size[1], img.size[0], img.channels))

            # Slice the image into 256×256 tiles.
            # Slicing *after* rendering (as opposed to rendering individual 256×256 regions) has advantages when a denoising filter is applied.
            # Otherwise, the denoising filter would lead to visible artifacts at the borders of the 256×256 tiles, preventing a seamless appearance.
            for count, (row, col) in enumerate(tile_indices_nonempty):
                left, right, top0, bottom0 = canvas.tile_border_px_LRTB(row, col)
                top = canvas.height_px - top0
                bottom = canvas.height_px - bottom0
                img_tile = bpy.data.images.new("b4b_canvas_tile", width=(right-left), height=(top-bottom), alpha=(img.channels >= 4))
                img_tile.file_format
                img_tile.file_format = 'PNG'
                img_tile.filepath = get_relative_path_for(f"{tgi_formatter(gid, z.value, v.value, count)}.png")
                img_tile.pixels = arr[bottom:top, left:right, :].ravel()
                img_tile.save()
                print(f"Saved: '{img_tile.filepath}'")
                yield img_tile.filepath
                bpy.data.images.remove(img_tile)

        finally:
            bpy.data.images.remove(img)
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except IOError:
                pass  # ignored

    @staticmethod
    def generate_preview(zoom: Zoom, hd: bool):
        Renderer.camera_manoeuvring(zoom, hd=hd)
        #  reset camera border in case a large view has been rendered.. may want to do this after rendering instead
        bpy.context.scene.render.border_min_x = 0.0
        bpy.context.scene.render.border_max_x = 1.0
        bpy.context.scene.render.border_min_y = 0.0
        bpy.context.scene.render.border_max_y = 1.0
        bpy.context.scene.render.film_transparent = True
        bpy.ops.render.render('INVOKE_DEFAULT', write_still=False)

    @staticmethod
    def camera_manoeuvring(zoom: Zoom, hd: bool) -> Canvas:
        r"""Adjust the offset, orthographic scale and resolution of the current
        camera so that the LOD fits into view, including a margin, and such
        that the orthographic scale results in a pixel-perfect display of the
        rendered image at the given zoom level.
        """
        coll = b4b_collection()
        cam = find_object(coll, CAM_NAME)
        lod = find_object(coll, LODZ_NAME[zoom.value])
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
        dim_lod = (zoom_sizes_hd if hd else zoom_sizes)[zoom.value] * os_lod / os_reference
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
        Also move the camera further away from the origin to put the whole LOD into view.
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

        distance = Camera.distance_from_lod(cam, lod)
        extra_camera_offset = 80  # distance to keep between camera and lod
        cam.location = cam.location * ((cam.location.length - distance + extra_camera_offset) / cam.location.length)

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

    @staticmethod
    def create_sc4model(fshgen_script: str, files: list[str], name: str, gid: str, delete: bool):
        import subprocess
        tgi = tgi_formatter(gid, 0, 0, 0, is_model=True, prefix=True)
        sc4model_path = get_relative_path_for(f"{name}-{tgi}.SC4Model")
        print(f"Using fshgen to create SC4Model: {sc4model_path}")
        result = subprocess.run([
            fshgen_script, "import",
            "--output", sc4model_path,
            "--force",
            "--with-BAT-models",
            "--format", "Dxt1",
            "--gid", f"0x{gid}",
        ], input="\n".join(files).encode())
        assert result.returncode == 0  # otherwise previous command would have raised
        if delete:
            for f in files:
                try:
                    Path(f).unlink(missing_ok=True)
                except IOError:
                    pass  # ignored
