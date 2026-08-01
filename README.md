# 🛠️ 學長的工具箱 SenpaiToolBox (Blender Add-on)

一個專為 Blender 3D 美術、動畫師與遊戲開發者打造的自動化工具箱。一鍵整合了貼圖打包、材質管理、動畫烘焙與導出等五大核心功能，完全相容於 Blender 4.x 與 5.x 新版動畫系統。

---

## 🌟 核心功能說明

### 1. 📦 自動打包序列/單張貼圖 (Pack Textures)
* **說明**：自動掃描場景中所有材質的 Image Texture 節點。
* **特色**：將原本散落各處的單張貼圖或序列圖，實體複製到 `.blend` 檔案旁邊的 `Textures` 資料夾中，並將 Blender 內的節點路徑自動重導向為「相對路徑」。
* **優勢**：不使用會使檔案肥大的內建 `pack` 指令，確保外部遊戲引擎（如 Unity、Unreal Engine）能正常讀取貼圖。若有已 Pack 的貼圖，會自動解包（Unpack）釋出。

### 2. 🏷️ 材質球與選定物件自動同名 (Rename Materials)
* **說明**：一鍵將選取物件身上的材質球名稱，修改為與該物件相同的名稱。
* **特色**：解決美術資產命名混亂的問題，提高整理場景的效率。

### 3. 🎬 Alembic (ABC) 動態快取轉 ShapeKey (ABC to ShapeKeys)
* **說明**：將外部匯入的 Alembic（.abc）動畫快取（Mesh Sequence Cache）逐幀（或隔幀）烘焙為網格本身的 Shape Keys。
* **特色**：烘焙後即可擺脫外部快取檔案獨立播放。
* **黑科技穩定機制**：為徹底防範 Blender 4.x/5.x 底層動畫系統重構導致的 F-curve API 報錯，本工具在寫入關鍵幀時會**暫時將系統全域預設插值強制設為 Constant（斷點）**，處理完後再還原。100% 避免因 API 變更引起的崩潰。

### 4. 🚀 多 Action 精確隔離批量導出 FBX (Export FBX Actions)
* **說明**：針對遊戲動畫設計。當一個骨架擁有多個動畫軌（Actions，如走路、跑步、攻擊）時，此功能會自動輪流切換各個 Action，並精確隔離、批量導出成獨立的 FBX 檔案到指定目錄。

### 5. 🎨 序列圖檔轉 Flipbook 網格圖 (Sequence to Flipbook)
* **說明**：將指定資料夾中的序列圖檔（PNG, JPG 等）拼貼重組成一張專供遊戲特效（如 Niagara/VFX）使用的 Flipbook 網格大圖（Texture Sheet）。
* **特色**：
  * **即時數量偵測**：選擇資料夾後，UI 會自動偵測並顯示有效的圖片數量。
  * **容量安全防呆**：自動計算 `欄數 × 列數` 的畫布總容量。若容量不足會觸發**紅色高亮警告**並攔截執行；若有多餘格子則自動留空。
  * **3 種通道輸出模式**：
    1. `RGB` (不透明)：填滿 Alpha 為 1.0，保留原始邊緣防漏色擴張。
    2. `RGB + 黑底`：顏色與 Alpha 乘算（Premultiply），全透明區域轉為乾淨純黑，並強制 Alpha 為不透明。
    3. `RGBA` (透明)：完整保留 Alpha 透明去背通道輸出。

---

## ⚙️ 系統需求與依賴

* **Blender 版本**：相容於 Blender 4.0.0 及以上版本（包含 5.x 動畫系統）。
* **Python 依賴**：Flipbook 功能需要使用 Blender 內建的 `numpy` 庫。

---

## 💾 安裝與使用指南

1. **取得腳本**：下載本倉庫中的 `senpai_toolbox.py`。
2. **安裝套件**：
   * 開啟 Blender，前往頂部選單 `Edit` -> `Preferences` (偏好設定)。
   * 切換到 `Add-ons` (擴充套件) 標籤頁，點擊右上角的 `Install...` (安裝)。
   * 選擇 `senpai_toolbox.py` 檔案並點擊安裝。
3. **啟用套件**：在列表中勾選啟用 **"Object: 學長的工具箱 SenpaiToolBox"**。
4. **快速啟動**：回到 Blender 3D 視圖（3D Viewport），按下鍵盤的 **`N` 鍵**，即可在右側側邊欄看到 **「學長的工具箱 SenpaiToolBox」** 面板，展開後即可一鍵使用五大功能！

---

## 📁 建議倉庫目錄結構

如果你想在 GitHub 上維護此專案，建議採用以下目錄結構：

```text
your-repo-name/
├── README.md               # 本說明文件
├── senpai_toolbox.py       # 整合了五大功能的 v1.8 終極穩定版 Add-on 主程式
└── individual_scripts/     # (選用) 當初開發時的獨立單項功能腳本
    ├── pack_textures.py
    ├── rename_materials.py
    ├── abc_to_shapekey.py
    ├── export_fbx_actions.py
    └── sequence_to_flipbook.py
```
