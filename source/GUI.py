import bpy
from .Enums import Operators, Rotation, Zoom, NightMode
from .GUI_ops import B4BRender
from . import Sun
import math


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
        rot.prop(context.scene.b4b, 'rotation', expand=True)
        layout.label(text="Zoom")
        zoom = layout.row()
        zoom.prop(context.scene.b4b, 'zoom', expand=True)
        night = layout.row()
        night.prop(context.scene.b4b, 'night', expand=True)

        self.layout.operator(Operators.PREVIEW.value[0])

        layout.label(text="LODs")
        lod = layout.row(align=True)
        lod.operator(Operators.LOD_ADD.value[0], text="Add")
        z = Zoom[context.scene.b4b.zoom]
        lod.operator(Operators.LOD_FIT_ZOOM.value[0], text=f"Fit Z{z.value+1}")
        lod.operator(Operators.LOD_DELETE.value[0], text="Delete")
        # lod.operator(Operators.LOD_EXPORT.value[0], text="Export .OBJ")  # LODs are exported during rendering

        layout.label(text="World")
        world = layout.row(align=True)
        world.operator(Operators.WORLD_SETUP.value[0], text="Setup World")
        world.operator(Operators.COMPOSITING_SETUP.value[0], text="Setup Compositing")

        layout.label(text="Camera")
        cam = layout.row(align=True)
        cam.operator(Operators.CAM_ADD.value[0], text="Add")
        cam.operator(Operators.CAM_DELETE.value[0], text="Delete")

        layout.label(text="Render")
        grp = layout.row(align=True)
        grp.prop(context.scene.b4b, 'group_id', text="Grp ID")
        grp.operator(Operators.GID_RANDOMIZE.value[0], text='', icon='FILE_REFRESH')
        hd = layout.row()
        hd.prop(context.scene.b4b, 'hd', expand=True)
        day_night = layout.row(align=True).split(factor=.333, align=False)
        day_night.label(text="Day/Night:")
        day_night_name = day_night.enum_item_name(context.scene.b4b, 'render_day_night', context.scene.b4b.render_day_night)
        day_night.menu(DayNightSelectMenu.bl_idname, text=day_night_name)  # using a custom menu instead of `prop` to allow disabling some enum items

        if not context.window_manager.b4b.is_rendering:
            text = (B4BRender.bl_label if not context.scene.b4b.render_current_view_only
                    else f"Render only Zoom {z.value+1} {Rotation[context.scene.b4b.rotation].compass_name()} {NightMode[context.scene.b4b.night].label()}  (see {AdvancedPanel.bl_label})")
            self.layout.operator(Operators.RENDER.value[0], text=text)
        else:
            progress_bar = layout.row(align=True)
            # progress_bar.enabled = False
            progress_bar.prop(context.window_manager.b4b, 'progress')
            label = layout.row()
            label.active = False
            label.label(text=context.window_manager.b4b.progress_label)


class SuperSamplingPanel(bpy.types.Panel):
    """A subpanel for BAT4Blender scene context of the properties editor"""
    bl_label = ""  # "Super-Sampling"
    bl_idname = 'SCENE_PT_b4b_supersampling'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_parent_id = 'SCENE_PT_b4b_layout'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        layout = self.layout
        layout.prop(context.scene.b4b, 'supersampling_enabled', icon_only=False)

    def draw(self, context):
        layout = self.layout
        downsampling = layout.row()
        downsampling.prop(context.scene.b4b, 'downsampling_filter', expand=False)
        downsampling.enabled = context.scene.b4b.supersampling_enabled
        path = layout.row()
        path.prop(context.preferences.addons[__package__].preferences, 'imagemagick_path', text="ImageMagick")
        path.enabled = context.scene.b4b.supersampling_enabled
        preview = layout.row()
        preview.prop(context.scene.b4b, 'supersampling_preview', expand=False)
        preview.enabled = context.scene.b4b.supersampling_enabled
        if context.scene.b4b.supersampling_preview == 'no_downsampling':
            preview2 = layout.row()
            preview2.operator(Operators.PREVIEW_DOWNSAMPLING.value[0])
            preview2.enabled = context.scene.b4b.supersampling_enabled and context.scene.b4b.supersampling_preview == 'no_downsampling'


class PostProcessPanel(bpy.types.Panel):
    """A subpanel for BAT4Blender scene context of the properties editor"""
    bl_label = ""  # "Post-Processing": empty string as it does not seem to allow gray-out when disabled
    bl_idname = 'SCENE_PT_b4b_postprocess'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_parent_id = 'SCENE_PT_b4b_layout'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        layout = self.layout
        layout.prop(context.scene.b4b, 'postproc_enabled', icon_only=False)
        layout.enabled = int(context.scene.b4b.render_day_night) & (1 << NightMode.DAY.value) != 0

    def draw(self, context):
        layout = self.layout
        layout.label(text="SC4Model Creation")
        layout.enabled = context.scene.b4b.postproc_enabled
        row = layout.row()
        row.prop(context.preferences.addons[__package__].preferences, 'fshgen_path', text="fshgen")


class AdvancedPanel(bpy.types.Panel):
    """A subpanel for BAT4Blender scene context of the properties editor"""
    bl_label = "Advanced"
    bl_idname = 'SCENE_PT_b4b_advanced'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_parent_id = 'SCENE_PT_b4b_layout'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(context.scene.b4b, 'render_current_view_only')


class B4BWmProps(bpy.types.PropertyGroup):
    r"""These properties are stored on the WindowManager, so affect all open scenes, but are not persistent.
    """
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

    def _get_sun_angles(self):
        _, s_y, s_z = Sun.get_sun_rotation(Rotation[self.rotation])
        return -s_y + math.pi/2, -s_z + math.pi/2  # elevation, rotation

    sun_angles: bpy.props.FloatVectorProperty(
        description="Elevation and rotation of sun",
        unit='ROTATION',
        size=2,
        get=_get_sun_angles,
    )

    zoom: bpy.props.EnumProperty(
        items=(lambda self, context: [
            (Zoom.ONE.name, '1', 'zoom 1', '', Zoom.ONE.value + 1),
            (Zoom.TWO.name, '2', 'zoom 2', '', Zoom.TWO.value + 1),
            (Zoom.THREE.name, '3', 'zoom 3', '', Zoom.THREE.value + 1),
            (Zoom.FOUR.name, '4', 'zoom 4', '', Zoom.FOUR.value + 1),
            (Zoom.FIVE.name, '5ᴴᴰ' if context.scene.b4b.hd == 'HD' else '5', 'zoom 5', '', Zoom.FIVE.value + 1),
        ]),
        default=Zoom.FIVE.value + 1,
    )

    def _update_night(self, context):
        import threading
        assert threading.current_thread() is threading.main_thread(), "BAT4Blender expects `night` property to be updated only from main thread"  # as a precaution, since in general properties might be updated from other threads
        nightmode = NightMode[self.night]
        is_night = nightmode != NightMode.DAY
        for coll in bpy.data.collections:
            if coll.name == 'Night' or coll.name.startswith('Night.'):
                coll.hide_render = not is_night
                coll.hide_viewport = not is_night
                if coll.color_tag == 'NONE':
                    coll.color_tag = 'COLOR_06'  # purple
            elif coll.name == 'Day' or coll.name.startswith('Day.'):
                coll.hide_render = is_night
                coll.hide_viewport = is_night
                if coll.color_tag == 'NONE':
                    coll.color_tag = 'COLOR_06'  # purple

    night: bpy.props.EnumProperty(
        items=[
            (NightMode.DAY.name, 'Day', 'day light', '', NightMode.DAY.value),
            (NightMode.MAXIS_NIGHT.name, 'MN', 'Maxis night', '', NightMode.MAXIS_NIGHT.value),
            (NightMode.DARK_NIGHT.name, 'DN', 'dark night', '', NightMode.DARK_NIGHT.value),
        ],
        default=NightMode.DAY.value,
        update=_update_night,
    )

    render_day_night: bpy.props.EnumProperty(
        items=[
            (str(flags), label, desc, '', flags) for label, desc, flags in [
                ("Day only", "No night lights", 1 << NightMode.DAY.value),
                ("Day & MN", "Day and Maxis night", 1 << NightMode.DAY.value | 1 << NightMode.MAXIS_NIGHT.value),
                ("MN only", "Maxis night (incompatible with SC4Model creation)", 1 << NightMode.MAXIS_NIGHT.value),
                ("Day & DN", "Day and dark night", 1 << NightMode.DAY.value | 1 << NightMode.DARK_NIGHT.value),
                ("DN only", "Dark night (incompatible with SC4Model creation)", 1 << NightMode.DARK_NIGHT.value),
                ("Day & MN & DN", "Day and both Maxis/dark night", 1 << NightMode.DAY.value | 1 << NightMode.MAXIS_NIGHT.value | 1 << NightMode.DARK_NIGHT.value),
            ]
        ],
        default=str(1 << NightMode.DAY.value),
        name="Day/Night",
        # description="Select day and night modes to render",
    )

    supersampling_enabled: bpy.props.BoolProperty(
        default=True,
        name="Super-Sampling",
        description="When enabled, render at 2× resolution for sharper results. In turn, you may reduce the Max Samples down to 25 % or increase the Noise Threshold",
    )

    supersampling_preview: bpy.props.EnumProperty(
        items=[
            ('no_supersampling', "1× resolution (no super-sampling)", "Disable super-sampling for Preview renders", '', 0),
            ('no_downsampling', "keep 2× resolution (no down-sampling)", "Keep the super-sampled Preview rendendering", '', 1),
        ],
        default='no_supersampling',
        name="Preview",
        description="Super-sampling setting for Preview renders",
    )

    downsampling_filter: bpy.props.EnumProperty(
        items=[
            ('MagicKernelSharp2021', "Magic Kernel Sharp 2021", "Sharp, but slightly more artifacts than Catmull-Rom", '', 0),
            ('CatRom', "Catmull-Rom", "Slightly smoother than Magic Kernel Sharp 2021", '', 1),
        ],
        default='MagicKernelSharp2021',
        name="Down-Sampling",
        description="Filter for down-scaling the high-res image",
    )

    postproc_enabled: bpy.props.BoolProperty(
        default=False,
        name="Post-Processing",
        description="When enabled, create SC4Model after rendering and delete intermediate files (requires Day render)",
    )

    render_current_view_only: bpy.props.BoolProperty(
        default=False,
        name="Render current view only (for debugging)",
        description="When enabled, only the current Zoom and Rotation is rendered and exported",
    )


class B4BPreferences(bpy.types.AddonPreferences):
    r"""These properties are stored once globally for the Add-on.
    """
    bl_idname = __package__

    imagemagick_path: bpy.props.StringProperty(
        name="""The location of the "magick" executable""",
        description="""For down-sampling, ImageMagick needs to be installed; select the location of the "magick" executable if it is not on your PATH""",
        subtype='FILE_PATH',
    )

    fshgen_path: bpy.props.StringProperty(
        name="""The "fshgen" script file""",
        description="""For creating SC4Model files, install "fshgen" and select the location of the "fshgen.bat" (Windows) or "fshgen" (macOS/Linux) script file if it is not on your PATH""",
        subtype='FILE_PATH',
    )

    def draw(self, context):
        layout = self.layout
        desc = self.__annotations__['imagemagick_path'].keywords['description']
        layout.label(text=f"{desc}.")
        layout.prop(self, 'imagemagick_path')
        desc = self.__annotations__['fshgen_path'].keywords['description']
        layout.label(text=f"{desc}.")
        layout.prop(self, 'fshgen_path')


class DayNightSelectMenu(bpy.types.Menu):
    bl_label = "Day/Night"
    bl_idname = "SCENE_MT_b4b_select_day_night"
    bl_context = 'scene'
    bl_description = "Select day and night modes to render"

    def draw(self, context):
        items = context.scene.b4b.bl_rna.properties['render_day_night'].enum_items_static
        pp = context.scene.b4b.postproc_enabled
        for item in items:
            item_layout = self.layout.row(align=True)
            item_layout.enabled = not pp or (item.value & (1 << NightMode.DAY.value) != 0)
            text = item.name if item_layout.enabled else f"{item.name} (disable Post-Processing)"
            item_layout.prop_enum(context.scene.b4b, 'render_day_night', value=item.identifier, text=text)
        self.layout.separator()
        self.layout.label(text=self.bl_label)
