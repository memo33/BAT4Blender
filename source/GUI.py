import bpy
from .Enums import Operators, Rotation, Zoom


class MainPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "BAT4Blender"
    bl_idname = 'SCENE_PT_b4b_layout'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        # Create a simple row.
        layout.label(text="Rotation")
        rot = layout.row()
        rot.prop(context.window_manager.b4b, 'rotation', expand=True)
        layout.label(text="Zoom")
        zoom = layout.row()
        zoom.prop(context.window_manager.b4b, 'zoom', expand=True)

        self.layout.operator(Operators.PREVIEW.value[0])

        layout.label(text="LODs")
        lod = layout.row(align=True)
        lod.operator(Operators.LOD_ADD.value[0], text="Add")
        z = Zoom[context.window_manager.b4b.zoom]
        lod.operator(Operators.LOD_FIT_ZOOM.value[0], text=f"Fit Z{z.value+1}")
        lod.operator(Operators.LOD_DELETE.value[0], text="Delete")
        # lod.operator(Operators.LOD_EXPORT.value[0], text="Export .OBJ")  # LODs are exported during rendering

        layout.label(text="Camera")
        cam = layout.row(align=True)
        cam.operator(Operators.CAM_ADD.value[0], text="Add")
        cam.operator(Operators.CAM_DELETE.value[0], text="Delete")

        layout.label(text="Sun")
        sun = layout.row(align=True)
        sun.operator(Operators.SUN_ADD.value[0], text="Add")
        sun.operator(Operators.SUN_DELETE.value[0], text="Delete")

        layout.label(text="Render")
        grp = layout.row(align=True)
        grp.prop(context.scene.b4b, 'group_id', text="Grp ID")
        grp.operator(Operators.GID_RANDOMIZE.value[0], text='', icon='FILE_REFRESH')
        hd = layout.row()
        hd.prop(context.scene.b4b, 'hd', expand=True)
        if not context.window_manager.b4b.is_rendering:
            self.layout.operator(Operators.RENDER.value[0])
        else:
            progress_bar = layout.row(align=True)
            # progress_bar.enabled = False
            progress_bar.prop(context.window_manager.b4b, 'progress')
            label = layout.row()
            label.active = False
            label.label(text=context.window_manager.b4b.progress_label)


class PostProcessPanel(bpy.types.Panel):
    """A subpanel for BAT4Blender scene context of the properties editor"""
    bl_label = "Post-Processing"
    bl_idname = 'SCENE_PT_b4b_postprocess'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_parent_id = 'SCENE_PT_b4b_layout'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        layout = self.layout
        layout.prop(context.scene.b4b, 'postproc_enabled', icon_only=True)

    def draw(self, context):
        layout = self.layout
        layout.label(text="SC4Model Creation")
        row = layout.row()
        row.prop(context.preferences.addons[__package__].preferences, 'fshgen_path', text="fshgen")
        row.enabled = context.scene.b4b.postproc_enabled


class B4BWmProps(bpy.types.PropertyGroup):
    r"""These properties are stored on the WindowManager, so affect all open scenes, but are not persistent.
    """

    # (unique identifier, property name, property description, icon identifier, number)
    rotation: bpy.props.EnumProperty(
        items=[
            (Rotation.SOUTH.name, 'S', 'South view', '', Rotation.SOUTH.value),
            (Rotation.EAST.name, 'E', 'East view', '', Rotation.EAST.value),
            (Rotation.NORTH.name, 'N', 'North view', '', Rotation.NORTH.value),
            (Rotation.WEST.name, 'W', 'West view', '', Rotation.WEST.value)
        ],
        default=Rotation.SOUTH.name
    )

    zoom: bpy.props.EnumProperty(
        items=(lambda self, context: [
            (Zoom.ONE.name, '1', 'zoom 1', '', Zoom.ONE.value),
            (Zoom.TWO.name, '2', 'zoom 2', '', Zoom.TWO.value),
            (Zoom.THREE.name, '3', 'zoom 3', '', Zoom.THREE.value),
            (Zoom.FOUR.name, '4', 'zoom 4', '', Zoom.FOUR.value),
            (Zoom.FIVE.name, '5ᴴᴰ' if context.scene.b4b.hd == 'HD' else '5', 'zoom 5', '', Zoom.FIVE.value),
        ]),
        default=Zoom.FIVE.value,
    )

    is_rendering: bpy.props.BoolProperty(default=False, name="Render In Progress")
    progress: bpy.props.FloatProperty(name="Progress", subtype='PERCENTAGE', soft_min=0, soft_max=100, precision=0)
    progress_label: bpy.props.StringProperty()


class B4BSceneProps(bpy.types.PropertyGroup):
    r"""These properties are persistently stored for each individual Scene in the .blend file.
    """

    group_id: bpy.props.StringProperty(
            name="Group ID",
            description="the Group ID as provided by gmax",
            default="")

    hd: bpy.props.EnumProperty(
        items=[
            ('SD', 'SD', "standard definition", '', 0),
            ('HD', 'HD', "high definition (doubles zoom 5 resolution)", '', 1),
        ],
        default='SD',
    )

    postproc_enabled: bpy.props.BoolProperty(
        default=False,
        name="Post-Processing",
        description="When enabled, create SC4Model after rendering and delete intermediate files",
    )


class B4BPreferences(bpy.types.AddonPreferences):
    r"""These properties are stored once globally for the Add-on.
    """
    bl_idname = __package__

    fshgen_path: bpy.props.StringProperty(
        name="""The "fshgen" script file""",
        description="""For creating SC4Model files, install "fshgen" and select the location of the "fshgen.bat" (Windows) or "fshgen" (macOS/Linux) script file if it is not on your PATH""",
        subtype='FILE_PATH',
    )

    def draw(self, context):
        layout = self.layout
        desc = self.__annotations__['fshgen_path'].keywords['description']
        layout.label(text=f"{desc}.")
        layout.prop(self, 'fshgen_path')
