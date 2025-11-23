import bpy
from .Utils import BAT4BlenderUserError, b4b_collection, find_object
from pathlib import Path
from mathutils import Vector
from . import Sun
from .Config import WORLD_NAME, COMPOSITING_NAME


def _ensure_cycles(context):
    if context.scene.render.engine == 'BLENDER_EEVEE':
        print("Switching from EEVEE to CYCLES render engine")
        context.scene.render.engine = 'CYCLES'


def _load_asset(coll_name, name, *, debug_label="Asset"):
    data_coll = getattr(bpy.data, coll_name)
    if name in data_coll:
        data_coll.remove(data_coll[name], do_unlink=True)
    import BAT4Blender
    library_path = Path(BAT4Blender.__file__).with_name("assets")
    print(f"Loading BAT4Blender assets from '{library_path}'")
    blend_files = [fp for fp in library_path.rglob("*.blend") if fp.is_file()]
    for blend_file in reversed(blend_files):
        with bpy.data.libraries.load(str(blend_file), link=True, assets_only=True) as (data_src, b4b_asset_lib):
            setattr(b4b_asset_lib, coll_name, [s for s in getattr(data_src, coll_name) if s == name][:1])
        lib_coll = getattr(b4b_asset_lib, coll_name)
        if lib_coll:
            return lib_coll[0]
    raise BAT4BlenderUserError(f"{debug_label} {name!r} not found in assets '{library_path}'")


def setup_world(context, world_name=WORLD_NAME):
    _ensure_cycles(context)
    Sun.delete_from_scene()  # for backward compatibility, remove sun object used in earlier versions of BAT4Blender
    context.scene.world = _load_asset('worlds', name=world_name, debug_label="World")


def setup_compositing(context):
    _ensure_cycles(context)
    b4b_compositing = _load_asset('node_groups', name=COMPOSITING_NAME, debug_label="Node group")  # removes previous group_node.node_tree if it existed
    context.scene.use_nodes = True
    tree = context.scene.node_tree
    for node in tree.nodes:  # remove previous group_node if it existed
        if isinstance(node, bpy.types.CompositorNodeGroup) and node.node_tree is None:
            tree.nodes.remove(node)
    group_node = tree.nodes.new('CompositorNodeGroup')
    group_node.node_tree = b4b_compositing
    missing = []

    rl_node = tree.nodes.get('Render Layers') or tree.nodes.new('CompositorNodeRLayers')
    for key, in_ in group_node.inputs.items():
        match key:  # enable additional passes as needed
            case 'Normal': context.view_layer.use_pass_normal = True
            case 'DiffCol': context.view_layer.use_pass_diffuse_color = True
            case 'Noisy Image': context.scene.cycles.use_denoising = True
            case 'Combined_env_light':
                lg_name = context.scene.world.lightgroup
                if lg_name != 'env_light':
                    raise BAT4BlenderUserError("World lacks lightgroup 'env_light'. Make sure to load World first.")
                if lg_name not in context.view_layer.lightgroups:
                    lg = context.view_layer.lightgroups.add(name=lg_name)
                    if lg.name != lg_name:
                        raise BAT4BlenderUserError(f"Failed to enable view layer lightgroup {lg_name!r}")
            case _: pass
        rl_node.update()
        out = rl_node.outputs.get(key)
        if out is None or out.is_unavailable:
            missing.append(key)
        else:
            link = tree.links.new(out, in_)
            if not link.is_valid:
                missing.append(key)

    comp_node = tree.nodes.get('Composite') or tree.nodes.new('CompositorNodeComposite')
    for key, out in group_node.outputs.items():
        in_ = comp_node.inputs.get(key)
        if in_ is None or in_.is_unavailable:
            missing.append(key)
        else:
            link = tree.links.new(out, in_)
            if not link.is_valid:
                missing.append(key)

    # positioning
    group_node.location = rl_node.location + Vector((350, 0))
    if group_node.location.x + 250 >= comp_node.location.x:
        comp_node.location = group_node.location + Vector((250, 0))

    if missing:
        raise BAT4BlenderUserError(f"Compositor node {b4b_compositing.name!r} has only been partially connected. Missing connections: {', '.join(missing)}")
