import bpy
from .GUI import B4BWmProps, B4BSceneProps, MainPanel, SuperSamplingPanel, PostProcessPanel, AdvancedPanel, B4BPreferences, DayNightSelectMenu
from . import GUI_ops

bl_info = {
    "name": "BAT4Blender",
    "category": "Render",
    "blender": (3, 2, 0),  # minimum Blender version
    "author": "vrtxt, memo",
    "version": (0, 0, 4),
    "location": "Properties > Scene > BAT4Blender",
    "description": "Render and export an SC4Model (BAT) for use with SimCity 4.",
    "doc_url": "https://community.simtropolis.com/forums/topic/763334-bat4blender",
}


# note: registering is order dependent! i.e. registering layout before vars will throw errors
def register():
    print("Registering addon BAT4Blender.")
    bpy.utils.register_class(B4BWmProps)
    bpy.types.WindowManager.b4b = bpy.props.PointerProperty(type=B4BWmProps)
    bpy.utils.register_class(B4BSceneProps)
    bpy.types.Scene.b4b = bpy.props.PointerProperty(type=B4BSceneProps)
    bpy.utils.register_class(B4BPreferences)

    bpy.utils.register_class(MainPanel)
    bpy.utils.register_class(SuperSamplingPanel)
    bpy.utils.register_class(PostProcessPanel)
    bpy.utils.register_class(AdvancedPanel)
    bpy.utils.register_class(DayNightSelectMenu)
    bpy.utils.register_class(GUI_ops.B4BPreview)
    bpy.utils.register_class(GUI_ops.B4BPreviewDownSampling)
    bpy.utils.register_class(GUI_ops.B4BRender)
    bpy.utils.register_class(GUI_ops.B4BLODFitZoom)
    bpy.utils.register_class(GUI_ops.B4BLODAdd)
    bpy.utils.register_class(GUI_ops.B4BLODDelete)
    bpy.utils.register_class(GUI_ops.B4BCamAdd)
    bpy.utils.register_class(GUI_ops.B4BCamDelete)
    bpy.utils.register_class(GUI_ops.B4BWorldSetup)
    bpy.utils.register_class(GUI_ops.B4BCompositingSetup)
    bpy.utils.register_class(GUI_ops.B4BGidRandomize)
    bpy.utils.register_class(GUI_ops.OkOperator)
    bpy.utils.register_class(GUI_ops.MessageOperator)


def unregister():
    print("Unregistering addon BAT4Blender.")
    del bpy.types.WindowManager.b4b
    del bpy.types.Scene.b4b
    bpy.utils.unregister_class(B4BWmProps)
    bpy.utils.unregister_class(B4BSceneProps)
    bpy.utils.unregister_class(B4BPreferences)
    bpy.utils.unregister_class(MainPanel)
    bpy.utils.unregister_class(SuperSamplingPanel)
    bpy.utils.unregister_class(PostProcessPanel)
    bpy.utils.unregister_class(AdvancedPanel)
    bpy.utils.unregister_class(DayNightSelectMenu)
    bpy.utils.unregister_class(GUI_ops.B4BPreview)
    bpy.utils.unregister_class(GUI_ops.B4BPreviewDownSampling)
    bpy.utils.unregister_class(GUI_ops.B4BRender)
    bpy.utils.unregister_class(GUI_ops.B4BLODFitZoom)
    bpy.utils.unregister_class(GUI_ops.B4BLODAdd)
    bpy.utils.unregister_class(GUI_ops.B4BLODDelete)
    bpy.utils.unregister_class(GUI_ops.B4BCamAdd)
    bpy.utils.unregister_class(GUI_ops.B4BCamDelete)
    bpy.utils.unregister_class(GUI_ops.B4BWorldSetup)
    bpy.utils.unregister_class(GUI_ops.B4BCompositingSetup)
    bpy.utils.unregister_class(GUI_ops.B4BGidRandomize)
    bpy.utils.unregister_class(GUI_ops.OkOperator)
    bpy.utils.unregister_class(GUI_ops.MessageOperator)
