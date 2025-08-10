import bpy
from .Enums import Operators, Rotation, Zoom
from .Rig import Rig
from .LOD import LOD
from .Sun import Sun
from .Camera import Camera
from .Renderer import Renderer, SuperSampling
from .Utils import blend_file_name, BAT4BlenderUserError
from bpy.props import StringProperty
import queue


# The OK button in the error dialog
class OkOperator(bpy.types.Operator):
    bl_idname = "error.ok"
    bl_label = "OK"

    def execute(self, context):
        return {'FINISHED'}


class MessageOperator(bpy.types.Operator):
    bl_idname = "error.message"
    bl_label = "Message"
    type: StringProperty()
    message: StringProperty()

    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400)

    def draw(self, context):
        self.layout.label(text="A message has arrived")
        row = self.layout.split(factor=0.25)
        row.prop(self, "type")
        row.prop(self, "message")
        row = self.layout.split(factor=0.80)
        row.label(text="")
        row.operator("error.ok")


class B4BRender(bpy.types.Operator):
    r"""Render all zooms and rotations.
    The implementation of this operator attempts to avoid blocking the UI, so
    that progress can be displayed in the UI and the operation can be cancelled
    by pressing ESC.
    This introduces some complexity due to the need for timers/threading to
    distribute the computations between the main UI thread and background
    computations.
    """
    bl_description = r"""Exports LOD .obj files and rendered images"""
    bl_idname = Operators.RENDER.value[0]
    bl_label = "Render all zooms & rotations"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cancelled = False
        self._finished = False  # is set after last rendering step or after being cancelled
        self._exception = None
        context = bpy.context
        if context.scene.b4b.render_current_view_only:
            self._steps = [(Zoom[context.window_manager.b4b.zoom], Rotation[context.window_manager.b4b.rotation])]
        else:
            self._steps = [(z, v) for z in Zoom for v in Rotation]
        self._step = 0
        self._interval = 0.5  # seconds
        self._render_post_args = None
        self._execution_queue = queue.Queue()
        self._output_files = []  # is *only* accessed on main thread, so no need for synchronization

    def _post_handler(self, scene, depsgraph):
        r"""Runs after each rendering call.
        """
        def f():
            z, v = self._steps[self._step]
            self._output_files.extend(Renderer.render_post(z, v, scene.b4b.group_id, *self._render_post_args))
            self._render_post_args = None
            print("-" * 60)
            self._step += 1
            if not self._cancelled:
                if self._step < len(self._steps):
                    self.handle_next_step()
                else:  # after last step, create SC4Model
                    context = bpy.context
                    if context.scene.b4b.postproc_enabled:
                        context.window_manager.b4b.progress = 100
                        context.window_manager.b4b.progress_label = "Creating SC4Model file"
                        fshgen_script = context.preferences.addons[__package__].preferences.fshgen_path or "fshgen"
                        model_name = blend_file_name()
                        Renderer.create_sc4model(fshgen_script,
                                                 self._output_files,
                                                 name=model_name,
                                                 gid=context.scene.b4b.group_id,
                                                 delete=True)

        self.run_on_main_thread(f)

    def _cancel_handler(self, scene, depsgraph):
        print("Rendering was cancelled.")
        def f():
            self._cancelled = True
        self.run_on_main_thread(f)

    # can be called on other threads, see https://docs.blender.org/api/current/bpy.app.timers.html#use-a-timer-to-react-to-events-in-another-thread
    def run_on_main_thread(self, function):
        self._execution_queue.put(function)

    def execute(self, context):
        if context.window_manager.b4b.is_rendering:
            print("A rendering operation is already in progress.")
            return {'FINISHED'}
        context.window_manager.b4b.is_rendering = True

        if context.scene.b4b.group_id in ["default", "", None]:  # GID is only generated once
            bpy.ops.object.b4b_gid_randomize()  # Operators.GID_RANDOMIZE

        bpy.app.handlers.render_post.append(self._post_handler)
        bpy.app.handlers.render_cancel.append(self._cancel_handler)
        context.window_manager.modal_handler_add(self)
        self.run_on_main_thread(self.handle_next_step)
        bpy.app.timers.register(self.execute_queue_loop)

        return {'RUNNING_MODAL'}

    def _redraw_properties_panel(self):
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
                    break

    def modal(self, context, event):
        if self._finished:  # (potentially problematic since this is set on another thread)
            if self._exception:
                raise self._exception
            else:
                return {'CANCELLED' if self._cancelled else 'FINISHED'}
        else:
            return {'PASS_THROUGH'}  # important for render function to be cancelable

    def execute_queue_loop(self):
        if self._cancelled or self._step >= len(self._steps):
            # cleanup, then finish
            bpy.app.handlers.render_post.remove(self._post_handler)
            bpy.app.handlers.render_cancel.remove(self._cancel_handler)
            print('CANCELLED' if self._cancelled else 'FINISHED')
            self._finished = True
            bpy.context.window_manager.b4b.is_rendering = False
            self._redraw_properties_panel()  # redraw to show Render button instead of progress bar again
            return None  # timer finishes and is unregistered
        else:
            # run next function from execution queue
            if not self._execution_queue.empty() and not self._cancelled and self._step < len(self._steps):
                f = self._execution_queue.get()
                try:
                    f()
                except BAT4BlenderUserError as e:
                    import sys
                    print(str(e), file=sys.stderr)
                    self.report({'ERROR'}, str(e))  # consume user errors by reporting them in the UI
                    self._cancelled = True
                except Exception as e:
                    self._exception = e  # keep forwarding internal errors (with stack trace)
                    self._cancelled = True
            return self._interval  # calls `execute_queue_loop` again after _interval

    def handle_next_step(self):
        context = bpy.context
        z, v = self._steps[self._step]
        print(f"Step ({self._step+1}/{len(self._steps)}): Zoom {z.value+1} {v.name}")
        context.window_manager.b4b.progress = 100 * self._step / len(self._steps)  # TODO consider non-linearity
        context.window_manager.b4b.progress_label = f"({self._step+1}/{len(self._steps)}) Zoom {z.value+1} {v.name}"
        model_name = blend_file_name()
        hd = context.scene.b4b.hd == 'HD'
        Rig.setup(v, z, hd=hd)
        if context.scene.b4b.supersampling_enabled:
            supersampling = SuperSampling(
                enabled=True,
                magick_exe=(context.preferences.addons[__package__].preferences.imagemagick_path or "magick"),
                downsampling_filter=context.scene.b4b.downsampling_filter)
        else:
            supersampling = SuperSampling(enabled=False)
        self._render_post_args = Renderer.render_pre(z, v, context.scene.b4b.group_id, model_name, hd=hd, supersampling=supersampling)

        # The following render call returns immediately *before* rendering finished,
        # so slicing rendered image is done later in post processing after rendering finished.
        # Likewise, slicing LODs is done in preprocessing.
        def f():  # executing this delayed seems to be important to avoid deadlocks
            layer = bpy.context.view_layer  # we choose the active layer for rendering if enabled in 'Use for Rendering', otherwise the default layer
            kwds = dict(layer=layer.name) if layer.use else {}
            orig_display_type = bpy.context.preferences.view.render_display_type
            try:
                bpy.context.preferences.view.render_display_type = 'NONE'  # avoid opening new window for each view (instead use Rendering workspace to see result)
                bpy.ops.render.render('INVOKE_DEFAULT', write_still=True, **kwds)
            finally:
                bpy.context.preferences.view.render_display_type = orig_display_type
        self.run_on_main_thread(f)


class B4BPreview(bpy.types.Operator):
    bl_description = r"""Render a preview image for the current zoom"""
    bl_idname = Operators.PREVIEW.value[0]
    bl_label = "Preview"

    def execute(self, context):
        v = Rotation[context.window_manager.b4b.rotation]
        z = Zoom[context.window_manager.b4b.zoom]
        hd = context.scene.b4b.hd == 'HD'
        Rig.setup(v, z, hd=hd)
        # q: pass the context to the renderer? or just grab it from internals..
        supersampling = SuperSampling(enabled=(context.scene.b4b.supersampling_enabled and context.scene.b4b.supersampling_preview == 'no_downsampling'))
        Renderer.generate_preview(z, hd=hd, supersampling=supersampling)
        return {'FINISHED'}


class B4BLODAdd(bpy.types.Operator):
    bl_description = ("Add (and fit) all missing LODs, if any.\n"
                      "Note: Keep LODs as simple as possible, especially for distant zoom levels")
    bl_idname = Operators.LOD_ADD.value[0]
    bl_label = "LOD add"

    def execute(self, context):
        Rig.lods_add()
        return {'FINISHED'}


class B4BLODFitZoom(bpy.types.Operator):
    bl_description = ("For the selected zoom level, refit the LOD around all rendered meshes. Create the LOD if necessary.\n"
                      "Note: Keep LODs as simple as possible, especially for distant zoom levels")
    bl_idname = Operators.LOD_FIT_ZOOM.value[0]
    bl_label = "LOD fit for zoom"

    def execute(self, context):
        z = Zoom[context.window_manager.b4b.zoom]
        Rig.lod_fit(z)
        return {'FINISHED'}


class B4BLODDelete(bpy.types.Operator):
    bl_description = "Delete all LODs"
    bl_idname = Operators.LOD_DELETE.value[0]
    bl_label = "LODDelete"

    def execute(self, context):
        for z in Zoom:
            Rig.lod_delete(z)
        return {'FINISHED'}


class B4BSunDelete(bpy.types.Operator):
    bl_idname = Operators.SUN_DELETE.value[0]
    bl_label = "SunDelete"

    def execute(self, context):
        Sun.delete_from_scene()
        return {'FINISHED'}


class B4BSunAdd(bpy.types.Operator):
    bl_idname = Operators.SUN_ADD.value[0]
    bl_label = "SunAdd"

    def execute(self, context):
        Sun.add_to_scene()
        return {'FINISHED'}


class B4BCamAdd(bpy.types.Operator):
    bl_idname = Operators.CAM_ADD.value[0]
    bl_label = "CamAdd"

    def execute(self, context):
        Camera.add_to_scene()
        return {'FINISHED'}


class B4BCamDelete(bpy.types.Operator):
    bl_idname = Operators.CAM_DELETE.value[0]
    bl_label = "CamDelete"

    def execute(self, context):
        Camera.delete_from_scene()
        return {'FINISHED'}


class B4BGidRandomize(bpy.types.Operator):
    bl_description = r"""Generate a new random Group ID"""
    bl_idname = Operators.GID_RANDOMIZE.value[0]
    bl_label = "Randomize"

    _skip_gids = {
        0xbadb57f1,  # S3D (Maxis)
        0x1abe787d,  # FSH (Misc)
        0x0986135e,  # FSH (Base/Overlay Texture)
        0x2BC2759a,  # FSH (Shadow Mask)
        0x2a2458f9,  # FSH (Animation Sprites (Props))
        0x49a593e7,  # FSH (Animation Sprites (Non Props))
        0x891b0e1a,  # FSH (Terrain/Foundation)
        0x46a006b0,  # FSH (UI Image)
    }

    def execute(self, context):
        import random
        gid = None
        while gid is None or gid in self._skip_gids:
            gid = random.randrange(1, 2**32 - 1)
        context.scene.b4b.group_id = f"{gid:08x}"
        return {'FINISHED'}
