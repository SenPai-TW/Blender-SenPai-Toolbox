bl_info = {
    "name": "學長的工具箱 SenPaiToolBox",
    "author": "SenPai Developer",
    "version": (1, 8),  # 已更新至 V1.8
    "blender": (4, 0, 0),  # 完全相容 Blender 4.x 與 5.x 核心新版系統
    "location": "View3D > Sidebar > 學長的工具箱 SenPaiToolBox Tab",
    "description": "一鍵整合五大功能：序列貼圖打包、材質與物件同名、ABC動畫轉ShapeKey、多Action獨立輸出FBX、動態 Flipbook 網格生成器",
    "category": "Object",
}

import bpy
import os
import shutil
import re
import gc
try:
    import numpy as np
except Exception:
    raise Exception("本工具的 Flipbook 功能需要 Blender 內建的 numpy。")

# ============================================================
# 1. 自動打包序列/單張圖檔 - 核心邏輯
# ============================================================
def run_pack_textures():
    TEXTURE_ROOT_FOLDER = "Textures"
    NORMAL_TEXTURE_FOLDER = "_Single_Textures"
    COPY_IMAGE_SEQUENCES = True
    SAVE_BLEND_AFTER_COLLECT = True
    OVERWRITE_EXISTING_FILES = True

    blend_path = bpy.data.filepath
    if not blend_path:
        return {"ERROR": "請先儲存 .blend 檔案，否則無法建立 Textures 資料夾。"}

    blend_dir = os.path.dirname(blend_path)
    textures_root_dir = os.path.join(blend_dir, TEXTURE_ROOT_FOLDER)
    os.makedirs(textures_root_dir, exist_ok=True)

    def sanitize_name(name):
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in name).strip()

    def get_node_folder_name(node):
        if node.label and node.label.strip():
            return sanitize_name(node.label)
        return sanitize_name(node.name)

    def make_unique_folder_path(base_folder):
        if not os.path.exists(base_folder):
            return base_folder
        counter = 1
        while True:
            new_folder = f"{base_folder}_{counter}"
            if not os.path.exists(new_folder):
                return new_folder
            counter += 1

    def make_unique_file_path(target_path):
        if OVERWRITE_EXISTING_FILES:
            return target_path
        if not os.path.exists(target_path):
            return target_path
        dir_name = os.path.dirname(target_path)
        base_name = os.path.basename(target_path)
        name, ext = os.path.splitext(base_name)
        counter = 1
        while True:
            new_path = os.path.join(dir_name, f"{name}_{counter}{ext}")
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    def copy_file(src_path, dst_folder):
        abs_src = bpy.path.abspath(src_path)
        if not os.path.exists(abs_src):
            return None
        filename = os.path.basename(abs_src)
        dst_path = os.path.join(dst_folder, filename)
        dst_path = make_unique_file_path(dst_path)
        try:
            shutil.copy2(abs_src, dst_path)
            return dst_path
        except:
            return None

    def find_sequence_files(image_node):
        img = image_node.image
        if not img or img.source != 'SEQUENCE':
            return []
        abs_path = bpy.path.abspath(img.filepath)
        folder = os.path.dirname(abs_path)
        filename = os.path.basename(abs_path)
        if not os.path.exists(folder):
            return []
        match = re.search(r'(.*?)(\d+)(\.[a-zA-Z0-9]+)$', filename)
        if not match:
            return [abs_path]
        prefix, _, ext = match.groups()
        return [os.path.join(folder, f) for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(ext)]

    image_nodes = []
    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image_nodes.append({"material": mat, "node": node, "image": node.image})

    if not image_nodes:
        return {"INFO": "沒有找到任何材質 Image Texture 節點。"}

    processed_count = 0
    for item in image_nodes:
        node = item["node"]
        img = item["image"]
        
        if img.source == 'SEQUENCE' and COPY_IMAGE_SEQUENCES:
            node_folder = get_node_folder_name(node)
            base_target = os.path.join(textures_root_dir, f"Seq_{node_folder}")
            target_folder = make_unique_folder_path(base_target)
            os.makedirs(target_folder, exist_ok=True)
            
            files_to_copy = find_sequence_files(node)
            for f in files_to_copy:
                new_path = copy_file(f, target_folder)
                if new_path and f == bpy.path.abspath(img.filepath):
                    img.filepath = bpy.path.relpath(new_path)
            processed_count += 1
        elif img.source == 'FILE':
            target_folder = os.path.join(textures_root_dir, NORMAL_TEXTURE_FOLDER)
            os.makedirs(target_folder, exist_ok=True)
            new_path = copy_file(img.filepath, target_folder)
            if new_path:
                img.filepath = bpy.path.relpath(new_path)
                processed_count += 1

    bpy.ops.file.make_paths_relative()
    if SAVE_BLEND_AFTER_COLLECT:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
        
    return {"SUCCESS": f"貼圖收集完成！處理了 {processed_count} 個節點。"}


# ============================================================
# 2. 自動材質球改名 - 核心邏輯
# ============================================================
def run_rename_materials():
    selected_objects = bpy.context.selected_objects
    if not selected_objects:
        return {"ERROR": "請先選取至少一個物件！"}

    count = 0
    for obj in selected_objects:
        if obj.type == 'MESH' and obj.data.materials:
            for slot in obj.material_slots:
                if slot.material:
                    slot.material.name = obj.name
                    count += 1
    return {"SUCCESS": f"材質球重命名完成，共修改了 {count} 個材質。"}


# ============================================================
# 3. ABC 動態檔轉 ShapeKey - 核心邏輯 (防 Fcurve 報錯穩定版)
# ============================================================
def run_abc_to_shapekeys():
    DISABLE_CACHE_MODIFIER_AFTER_BAKE = False
    FRAME_STEP = 1
    SHAPE_KEY_PREFIX = "ABC_Frame_"
    ONLY_PROCESS_ALEMBIC_CACHE_OBJECTS = True

    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    start_frame = scene.frame_start
    end_frame = scene.frame_end
    selected = bpy.context.selected_objects
    
    if not selected:
        return {"ERROR": "請先選擇要轉換的網格物件。"}
        
    current_frame = scene.frame_current
    processed_objects = 0

    old_interpolation = bpy.context.preferences.edit.keyframe_new_interpolation_type
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'CONSTANT'

    try:
        for obj in selected:
            if obj.type != 'MESH':
                continue
                
            cache_modifier = next((m for m in obj.modifiers if m.type == 'MESH_SEQUENCE_CACHE'), None)
            if ONLY_PROCESS_ALEMBIC_CACHE_OBJECTS and not cache_modifier:
                continue

            if obj.data.shape_keys:
                for i in range(len(obj.data.shape_keys.key_blocks)-1, -1, -1):
                    kb = obj.data.shape_keys.key_blocks[i]
                    if kb.name.startswith(SHAPE_KEY_PREFIX) or kb.name == "Basis":
                        obj.shape_key_remove(kb)

            bpy.context.scene.frame_set(start_frame)
            obj.shape_key_add(name="Basis", from_mix=False)
            baked_keys = []
            
            for frame in range(start_frame, end_frame + 1, FRAME_STEP):
                bpy.context.scene.frame_set(frame)
                eval_obj = obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.to_mesh()
                
                key = obj.shape_key_add(name=f"{SHAPE_KEY_PREFIX}{frame:04d}", from_mix=False)
                baked_keys.append((frame, key))
                
                for v_idx, vert in enumerate(eval_mesh.vertices):
                    key.data[v_idx].co = vert.co
                obj.to_mesh_clear()
                
            for frame, key in baked_keys:
                key.value = 0.0
                key.keyframe_insert(data_path="value", frame=frame)
                if frame - FRAME_STEP >= start_frame:
                    key.value = 0.0
                    key.keyframe_insert(data_path="value", frame=frame - FRAME_STEP)
                if frame + FRAME_STEP <= end_frame:
                    key.value = 0.0
                    key.keyframe_insert(data_path="value", frame=frame + FRAME_STEP)
                key.value = 1.0
                key.keyframe_insert(data_path="value", frame=frame)

            if cache_modifier and DISABLE_CACHE_MODIFIER_AFTER_BAKE:
                cache_modifier.show_viewport = False
                cache_modifier.show_render = False
                
            processed_objects += 1

    finally:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = old_interpolation
        
    bpy.context.scene.frame_set(current_frame)
    if processed_objects == 0:
        return {"INFO": "未選中任何帶有 Alembic 快取的網格物件。"}
    return {"SUCCESS": f"成功烘焙 {processed_objects} 個物件的 ABC 為 Shape Keys！"}


# ============================================================
# 4. 多 Action 輸出多 FBX - 核心邏輯
# ============================================================
def run_export_actions(armature_name, output_path):
    if armature_name not in bpy.data.objects:
        return {"ERROR": f"場景中找不到骨架：{armature_name}"}
        
    if not os.path.exists(output_path):
        try:
            os.makedirs(output_path, exist_ok=True)
        except:
            return {"ERROR": "無效的導出路徑，無法建立資料夾。"}

    armature_obj = bpy.data.objects[armature_name]
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    
    for child in armature_obj.children:
        if child.type == 'MESH':
            child.select_set(True)

    if not armature_obj.animation_data:
        armature_obj.animation_data_create()
        
    original_action = armature_obj.animation_data.action
    action_count = 0

    for action in bpy.data.actions:
        armature_obj.animation_data.action = action
        if action.frame_range:
            bpy.context.scene.frame_start = int(action.frame_range[0])
            bpy.context.scene.frame_end = int(action.frame_range[1])

        safe_action_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in action.name).strip()
        export_file_path = os.path.join(output_path, f"{armature_name}_{safe_action_name}.fbx")
        
        bpy.ops.export_scene.fbx(
            filepath=export_file_path,
            use_selection=True,
            bake_anim=True,
            bake_anim_use_all_actions=False,
            bake_anim_use_nla_strips=False,
            object_types={'ARMATURE', 'MESH'}
        )
        action_count += 1
        
    armature_obj.animation_data.action = original_action
    return {"SUCCESS": f"已成功導出 {action_count} 個 Action FBX 檔至目標資料夾！"}


# ============================================================
# 5. Blender 序列圖檔轉 Flipbook - 核心與更新回饋邏輯
# ============================================================
VALID_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr"]

def natural_sort_key(text):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", os.path.basename(text))]

def collect_image_files(input_folder):
    if not os.path.exists(input_folder):
        return []
    files = []
    for f in os.listdir(input_folder):
        ext = os.path.splitext(f)[1].lower()
        if ext in VALID_EXTENSIONS:
            files.append(os.path.join(input_folder, f))
    files.sort(key=natural_sort_key)
    return files

def update_flipbook_source_count(self, context):
    scene = context.scene
    folder = bpy.path.abspath(scene.flipbook_source_dir)
    if os.path.exists(folder):
        try:
            files = collect_image_files(folder)
            scene.flipbook_source_count = len(files)
        except:
            scene.flipbook_source_count = 0
    else:
        scene.flipbook_source_count = 0

def make_flipbook(input_folder, output_path, cols, rows, target_size, channel_mode):
    files = collect_image_files(input_folder)
    if not files:
        return {"ERROR": "在指定的來源資料夾中找不到任何支援的圖像序列。"}
    
    total_width = cols * target_size
    total_height = rows * target_size
    
    canvas = np.zeros((total_height, total_width, 4), dtype=np.float32)
    
    for idx, filepath in enumerate(files):
        if idx >= cols * rows:
            break
            
        c = idx % cols
        r = idx // cols
        blender_row = (rows - 1) - r
        
        try:
            img = bpy.data.images.load(filepath)
        except Exception as e:
            print(f"無法載入影像檔案: {filepath}，錯誤: {e}")
            continue
            
        if img.size[0] != target_size or img.size[1] != target_size:
            img.scale(target_size, target_size)
            
        pixels = np.array(img.pixels, dtype=np.float32).reshape((target_size, target_size, 4))
        
        if channel_mode == 'RGB_BLACK':
            pixels[:, :, :3] = pixels[:, :, :3] * pixels[:, :, 3:4]
            pixels[:, :, 3] = 1.0
        elif channel_mode == 'RGB':
            pixels[:, :, 3] = 1.0
        
        y_start = blender_row * target_size
        y_end = y_start + target_size
        x_start = c * target_size
        x_end = x_start + target_size
        
        canvas[y_start:y_end, x_start:x_end, :] = pixels
        bpy.data.images.remove(img)
        
    fb_img = bpy.data.images.new("Generated_Flipbook", width=total_width, height=total_height, alpha=True)
    fb_img.pixels = canvas.flatten()
    fb_img.filepath_raw = output_path
    fb_img.file_format = 'PNG'
    fb_img.save()
    bpy.data.images.remove(fb_img)
    
    gc.collect()
    return {"SUCCESS": f"Flipbook 網格圖產生完成！已導出至：{output_path}"}


# ============================================================
# UI 面板佈局與 Operator 介面綁定 (N快捷欄位全整合)
# ============================================================

class TOOLBOX_OT_PackTextures(bpy.types.Operator):
    bl_idname = "toolbox.pack_textures"
    bl_label = "1. 自動打包序列/單張貼圖"
    bl_description = "複製場景所有貼圖 to .blend 旁的 Textures 資料夾，並自動切換為相對路徑"
    
    def execute(self, context):
        res = run_pack_textures()
        if "ERROR" in res:
            self.report({'ERROR'}, res["ERROR"])
        elif "INFO" in res:
            self.report({'INFO'}, res["INFO"])
        else:
            self.report({'INFO'}, res["SUCCESS"])
        return {'FINISHED'}


class TOOLBOX_OT_RenameMaterials(bpy.types.Operator):
    bl_idname = "toolbox.rename_materials"
    bl_label = "2. 材質球改名為物件名"
    bl_description = "將所有選中物件身上的材質球名稱自動改為與物件本身同名"
    
    def execute(self, context):
        res = run_rename_materials()
        if "ERROR" in res:
            self.report({'ERROR'}, res["ERROR"])
        else:
            self.report({'INFO'}, res["SUCCESS"])
        return {'FINISHED'}


class TOOLBOX_OT_AbcToShapekeys(bpy.types.Operator):
    bl_idname = "toolbox.abc_to_shapekeys"
    bl_label = "3. ABC 快取動畫轉 ShapeKey"
    bl_description = "將選中物件的 Mesh Sequence Cache 快取逐幀烘焙成網格內建的 Shape Keys 動畫"
    
    def execute(self, context):
        res = run_abc_to_shapekeys()
        if "ERROR" in res:
            self.report({'ERROR'}, res["ERROR"])
        elif "INFO" in res:
            self.report({'INFO'}, res["INFO"])
        else:
            self.report({'INFO'}, res["SUCCESS"])
        return {'FINISHED'}


class TOOLBOX_OT_ExportFbxActions(bpy.types.Operator):
    bl_idname = "toolbox.export_fbx_actions"
    bl_label = "4. 分離輸出所有 Action 為 FBX"
    bl_description = "自動切換當前骨架的所有 Action，並批量獨立導出成對應的 FBX 檔案"
    
    def execute(self, context):
        scene = context.scene
        res = run_export_actions(scene.toolbox_armature_name, scene.toolbox_export_path)
        if "ERROR" in res:
            self.report({'ERROR'}, res["ERROR"])
        else:
            self.report({'INFO'}, res["SUCCESS"])
        return {'FINISHED'}


class TOOLBOX_OT_MakeFlipbook(bpy.types.Operator):
    bl_idname = "toolbox.make_flipbook"
    bl_label = "5. 執行生成 Flipbook 網格圖"
    bl_description = "將選定資料夾中的序列圖檔拼貼重組成單張 Flipbook 網格圖"
    
    def execute(self, context):
        scene = context.scene
        total_slots = scene.flipbook_cols * scene.flipbook_rows
        if scene.flipbook_source_count > total_slots:
            self.report({'ERROR'}, f"生成失敗: 目前網格格數({total_slots})小於圖片數量({scene.flipbook_source_count})，請調大欄數或列數！")
            return {'CANCELLED'}
            
        res = make_flipbook(
            bpy.path.abspath(scene.flipbook_source_dir),
            bpy.path.abspath(scene.flipbook_output_path),
            scene.flipbook_cols,
            scene.flipbook_rows,
            scene.flipbook_tile_size,
            scene.flipbook_channel_mode
        )
        if "ERROR" in res:
            self.report({'ERROR'}, res["ERROR"])
        else:
            self.report({'INFO'}, res["SUCCESS"])
        return {'FINISHED'}


class TOOLBOX_PT_MainPanel(bpy.types.Panel):
    bl_label = "學長的工具箱 SenPaiToolBox"
    bl_idname = "TOOLBOX_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '學長的工具箱 SenPaiToolBox'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        box = layout.box()
        box.label(text="檔案與材質管理", icon='MATERIAL')
        box.operator("toolbox.pack_textures", icon='FILE_FOLDER')
        box.operator("toolbox.rename_materials", icon='FONT_DATA')
        
        layout.separator()
        
        box = layout.box()
        box.label(text="核心動畫烘焙", icon='ANIM')
        box.operator("toolbox.abc_to_shapekeys", icon='SHAPEKEY_DATA')
        
        layout.separator()
        
        box = layout.box()
        box.label(text="多 Action 導出 FBX", icon='EXPORT')
        box.prop(scene, "toolbox_armature_name")
        box.prop(scene, "toolbox_export_path")
        box.operator("toolbox.export_fbx_actions", icon='PLAY_REVERSE')
        
        layout.separator()
        
        box = layout.box()
        box.label(text="5. 序列圖檔轉 Flipbook", icon='IMAGE_DATA')
        box.prop(scene, "flipbook_source_dir")
        box.prop(scene, "flipbook_output_path")
        
        # 修正後的安全 icon 使用
        if scene.flipbook_source_dir:
            box.label(text=f" 偵測到序列圖片數量: {scene.flipbook_source_count} 張", icon='IMAGE_DATA')
        else:
            box.label(text=" 請選擇包含序列圖檔的來源路徑", icon='INFO')
        
        row1 = box.row()
        row1.prop(scene, "flipbook_cols")
        row1.prop(scene, "flipbook_rows")
        
        total_slots = scene.flipbook_cols * scene.flipbook_rows
        box.label(text=f" 目前設定總網格數: {scene.flipbook_cols} × {scene.flipbook_rows} = {total_slots} 格", icon='GRID')
        
        if scene.flipbook_source_count > 0:
            if total_slots < scene.flipbook_source_count:
                warn_row = box.row()
                warn_row.alert = True
                warn_row.label(text=f"⚠️ 網格不足！尚缺 {scene.flipbook_source_count - total_slots} 格空間！", icon='ERROR')
            else:
                box.label(text="✅ 網格容量充足（剩餘空格將自動留空）", icon='CHECKMARK')
        
        row2 = box.row()
        row2.prop(scene, "flipbook_tile_size")
        row2.prop(scene, "flipbook_channel_mode")
        
        desc_box = box.box()
        if scene.flipbook_channel_mode == 'RGB':
            desc_box.label(text="【RGB 模式說明】", icon='QUESTION')
            desc_box.label(text="不更動原始像素色彩，強行將 Alpha 去背填滿不透明。")
            desc_box.label(text="（適合自帶邊緣色彩擴張 Dilation 的圖，防漏色）。")
        elif scene.flipbook_channel_mode == 'RGB_BLACK':
            desc_box.label(text="【RGB + 黑底模式說明】", icon='QUESTION')
            desc_box.label(text="將 RGB 與 Alpha 相乘使其邊緣乾淨黑化，Alpha 填滿不透明。")
            desc_box.label(text="（適合煙霧、火焰等黑底混合的特效不透明貼圖）。")
        elif scene.flipbook_channel_mode == 'RGBA':
            desc_box.label(text="【RGBA 模式說明】", icon='QUESTION')
            desc_box.label(text="完整保留 Alpha 透明去背通道背景輸出。")
            desc_box.label(text="（適合需要完全透明度的常規粒子、網格特效圖）。")
            
        btn_row = box.row()
        if scene.flipbook_source_count > total_slots:
            btn_row.alert = True
        btn_row.operator("toolbox.make_flipbook", icon='RENDER_ANIMATION')


# ============================================================
# 註冊與註銷機制
# ============================================================
classes = (
    TOOLBOX_OT_PackTextures,
    TOOLBOX_OT_RenameMaterials,
    TOOLBOX_OT_AbcToShapekeys,
    TOOLBOX_OT_ExportFbxActions,
    TOOLBOX_OT_MakeFlipbook,
    TOOLBOX_PT_MainPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.toolbox_armature_name = bpy.props.StringProperty(
        name="骨架名稱", default="Armature"
    )
    bpy.types.Scene.toolbox_export_path = bpy.props.StringProperty(
        name="導出路徑", default="D:/FBX_Exports/", subtype='DIR_PATH'
    )
    
    bpy.types.Scene.flipbook_source_dir = bpy.props.StringProperty(
        name="來源目錄", description="選擇包含圖像序列的資料夾", default="", subtype='DIR_PATH',
        update=update_flipbook_source_count
    )
    bpy.types.Scene.flipbook_source_count = bpy.props.IntProperty(
        name="圖片數量", default=0
    )
    bpy.types.Scene.flipbook_output_path = bpy.props.StringProperty(
        name="存檔位置", description="設定輸出的 Flipbook 貼圖路徑 (.png)", default="D:/Flipbook_Output.png", subtype='FILE_PATH'
    )
    bpy.types.Scene.flipbook_cols = bpy.props.IntProperty(
        name="欄數 (Cols)", description="水平網格數量", default=12, min=1
    )
    bpy.types.Scene.flipbook_rows = bpy.props.IntProperty(
        name="列數 (Rows)", description="垂直網格數量", default=10, min=1
    )
    bpy.types.Scene.flipbook_tile_size = bpy.props.IntProperty(
        name="單格尺寸", description="單張影像縮放後的正方形像素尺寸", default=256, min=1
    )
    bpy.types.Scene.flipbook_channel_mode = bpy.props.EnumProperty(
        name="通道模式",
        items=[
            ('RGB', "RGB (不透明)", "僅保留原始色彩，將 Alpha 強制設為 1.0"),
            ('RGB_BLACK', "RGB + 黑底", "將透明背景區域乘算為純黑色，並將 Alpha 強制設為 1.0"),
            ('RGBA', "RGBA (透明)", "保留完整的 Alpha 透明去背通道背景")
        ],
        default='RGBA'
    )

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    del bpy.types.Scene.toolbox_armature_name
    del bpy.types.Scene.toolbox_export_path
    del bpy.types.Scene.flipbook_source_dir
    del bpy.types.Scene.flipbook_source_count
    del bpy.types.Scene.flipbook_output_path
    del bpy.types.Scene.flipbook_cols
    del bpy.types.Scene.flipbook_rows
    del bpy.types.Scene.flipbook_tile_size
    del bpy.types.Scene.flipbook_channel_mode

if __name__ == "__main__":
    register()
