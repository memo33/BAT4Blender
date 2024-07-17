import bpy
import bmesh
from mathutils import Vector, Matrix
from typing import List, Any
from .Config import LOD_NAME
from .Utils import get_relative_path_for, b4b_collection, translate, clip
from .Renderer import Canvas

class LOD:
    @staticmethod
    def fit_new():
        bb = LOD.get_all_bound_boxes()
        min_max_xyz = LOD.get_min_max_xyz(bb)
        LOD.create_and_update(min_max_xyz)

    @staticmethod
    def get_all_bound_boxes() -> List:
        b_boxes = []
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH' and not obj.hide_render:
                bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
                b_boxes.append(bbox_corners)
        return b_boxes

    @staticmethod
    def get_min_max_xyz(b_boxes: List[List[Any]]) -> List[Any]:
        v = b_boxes[0][0]
        (min_x, max_x, min_y, max_y, min_z, max_z) = (v[0], v[0], v[1], v[1], v[2], v[2])
        for b in b_boxes:
            for v in b:
                if v[0] < min_x:
                    min_x = v[0]
                if v[0] > max_x:
                    max_x = v[0]
                if v[1] < min_y:
                    min_y = v[1]
                if v[1] > max_y:
                    max_y = v[1]
                if v[2] < min_z:
                    min_z = v[2]
                if v[2] > max_z:
                    max_z = v[2]
        return [min_x, max_x, min_y, max_y, min_z, max_z]

    @staticmethod
    def get_mesh_cube(name) -> object:
        verts = [(1.0, 1.0, -1.0),
                 (1.0, -1.0, -1.0),
                 (-1.0, -1.0, -1.0),
                 (-1.0, 1.0, -1.0),
                 (1.0, 1.0, 1.0),
                 (1.0, -1.0, 1.0),
                 (-1.0, -1.0, 1.0),
                 (-1.0, 1.0, 1.0)]
        faces = [(0, 1, 2, 3),
                 (4, 7, 6, 5),
                 (0, 4, 5, 1),
                 (1, 5, 6, 2),
                 (2, 6, 7, 3),
                 (4, 0, 3, 7)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        return bpy.data.objects.new(name, mesh)

    @staticmethod
    def create_and_update(xyz_mm: List[Any]):
        width = xyz_mm[1] - xyz_mm[0]
        depth = xyz_mm[3] - xyz_mm[2]
        height = xyz_mm[5] - xyz_mm[4]
        loc = (xyz_mm[0] + width / 2, xyz_mm[2] + depth / 2, xyz_mm[4] + height / 2)

        c = LOD.get_mesh_cube(LOD_NAME)
        c.matrix_world @= Matrix.Translation(loc)
        c.matrix_world @= Matrix.Scale(width / 2, 4, (1, 0, 0))
        c.matrix_world @= Matrix.Scale(depth / 2, 4, (0, 1, 0))
        c.matrix_world @= Matrix.Scale(height / 2, 4, (0, 0, 1))
        c.hide_render = True
        c.display_type = 'WIRE'
        b4b_collection().objects.link(c)
        bpy.context.view_layer.update()

    @staticmethod
    def export():
        if LOD_NAME in bpy.data.objects:
            with bpy.context.temp_override(selected_objects=[bpy.data.objects[LOD_NAME]]):
                bpy.ops.export_scene.obj(
                    filepath="{}.obj".format(get_relative_path_for(LOD_NAME)),
                    check_existing=False,
                    axis_forward='Y',
                    axis_up='Z',
                    use_selection=True
                )

        else:
            print("there is no LOD to export!")

    @staticmethod
    def _copy_bmesh_with_face_filter(mesh: bmesh.types.BMesh, name: str, face_filter) -> bpy.types.Mesh:
        mesh.verts.index_update()  # important if vertices have been added that still have index -1

        faces = [f for f in mesh.faces if face_filter(f)]
        vertices = list(set(v for f in faces for v in f.verts))
        vmap = {vert.index: i for i, vert in enumerate(vertices)}  # maps vertex indices of old mesh to new mesh (with fewer vertices)
        coords = [v.co for v in vertices]
        polys = [tuple(vmap[v.index] for v in f.verts) for f in faces]

        mesh2 = bpy.data.meshes.new(name=name)
        mesh2.from_pydata(coords, [], polys)
        mesh2.update(calc_edges=True)
        return mesh2
        # bm2 = bmesh.new()
        # bm2.from_mesh(mesh)
        # bpy.data.meshes.remove(mesh)

    def copy_visible_faces(lod, cam) -> bpy.types.Object:
        r"""Create a copy of the LOD containing only faces whose normals point towards the camera.
        """
        cam_view_direction = cam.matrix_world @ Vector([0, 0, -1]) - cam.location
        bm = bmesh.new()
        bm.from_mesh(lod.data)
        name = 'b4b_lod_visible'
        mesh = LOD._copy_bmesh_with_face_filter(bm, name, lambda f: f.normal.dot(cam_view_direction) < 0)
        obj = bpy.data.objects.new(name, mesh)
        obj.location = lod.location
        obj.scale = lod.scale
        obj.rotation_euler = lod.rotation_euler
        obj.hide_render = True
        b4b_collection().objects.link(obj)
        return obj

    def slice(lod, cam, canvas_tile):
        r"""Create a LOD slice object cut out by the given canvas tile.
        """
        lod_visible = LOD.copy_visible_faces(lod, cam)  # as the knife_project modifies this object, we create it anew for each tile
        lod_visible.parent = canvas_tile  # for local coordinates (to find vertices inside tile boundary)
        lod_visible.matrix_parent_inverse = canvas_tile.matrix_world.inverted()  # TODO or .matrix_local?

        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = lod_visible

        # apply knife project operator
        bpy.ops.object.mode_set(mode='EDIT')
        canvas_tile.select_set(True)
        ctx_override = Canvas.find_view3d()
        assert 'area' in ctx_override
        with bpy.context.temp_override(**ctx_override):
            bpy.ops.mesh.knife_project()

        # compute tile boundary
        assert canvas_tile.parent is not None, "Parent of canvas tile should be the corresponding camera for local coordinates to work."
        tile_coords = [canvas_tile.matrix_local @ v.co for v in canvas_tile.data.vertices]
        tile_x_min = min(c[0] for c in tile_coords)
        tile_x_max = max(c[0] for c in tile_coords)
        tile_y_min = min(c[1] for c in tile_coords)
        tile_y_max = max(c[1] for c in tile_coords)

        # Create sliced LOD from faces selected by knife project operator
        # and, additionally, faces whose vertices are completely within the tile boundaries.
        # (The latter is important for faces that do not intersect with the
        # tile boundary, so would not be selected by the knife project operator.)
        bm = bmesh.from_edit_mesh(bpy.context.edit_object.data)
        name = 'b4b_lod_slice'
        bm_verts_inside = {v.index for v in bm.verts
                           if tile_x_min <= (c := lod_visible.matrix_local @ v.co)[0] and c[0] <= tile_x_max
                           and tile_y_min <= c[1] and c[1] <= tile_y_max}
        slice_mesh = LOD._copy_bmesh_with_face_filter(bm, name, lambda f: f.select or all(v.index in bm_verts_inside for v in f.verts))

        slice_obj = bpy.data.objects.new(name, slice_mesh)
        slice_obj.location = lod_visible.location
        slice_obj.scale = lod_visible.scale
        slice_obj.rotation_euler = lod_visible.rotation_euler
        slice_obj.hide_render = True

        # TODO if canvas_tile is new, maybe we need to call bpy.context.view_layer.update() for up-to-date matrices
        slice_obj.parent = canvas_tile
        slice_obj.matrix_parent_inverse = canvas_tile.matrix_world.inverted()  # TODO or .matrix_local?

        b4b_collection().objects.link(slice_obj)

        bpy.ops.object.mode_set(mode='OBJECT')
        # set uv coordinates
        uv_map = LOD._compute_uv_of_lod_slice(slice_obj)
        uv_layer = slice_obj.data.uv_layers.new(name='UVmap')
        for polygon in slice_obj.data.polygons:
            for loopindex in polygon.loop_indices:  # loopindex corresponds to a "face vertex"
                meshloop = slice_obj.data.loops[loopindex]
                meshuvloop = uv_layer.data[loopindex]
                meshuvloop.uv.xy = uv_map[meshloop.vertex_index]

        bpy.data.meshes.remove(lod_visible.data, do_unlink=True)
        return slice_obj

    def _compute_uv_of_lod_slice(lod_slice):
        assert lod_slice.parent is not None, "Parent of LOD slice should be the corresponding canvas_tile."
        canvas_tile = lod_slice.parent

        tile_coords = [canvas_tile.matrix_local @ v.co for v in canvas_tile.data.vertices]
        x_min = min(c[0] for c in tile_coords)
        x_max = max(c[0] for c in tile_coords)
        y_min = min(c[1] for c in tile_coords)
        y_max = max(c[1] for c in tile_coords)

        def vert2uv(vert):
            # the local coordinates are relative to the parent (canvas_tile),
            # so first two coordinates correspond to u,v (up to stretching)
            c = lod_slice.matrix_local @ vert.co
            return (clip(translate(c[0], x_min, x_max, 0.0, 1.0), 0, 1),
                    clip(translate(c[1], y_min, y_max, 0.0, 1.0), 0, 1))

        uv_map = {v.index: vert2uv(v) for v in lod_slice.data.vertices}
        return uv_map
