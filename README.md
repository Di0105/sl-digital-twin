# Sri Lanka Heritage Digital Twin — Galle Fort & Kandy

A web-based 3D digital twin that streams UAV photogrammetry reality meshes of Sri
Lankan heritage sites directly in the browser. Built with CesiumJS, served as a
static site on GitHub Pages — **no install, no login, works on any modern
desktop or laptop browser.**

**Live site:** https://di0105.github.io/sl-digital-twin/

| Model | Site |
| --- | --- |
| Yellow House | Galle Dutch Fort |
| Galle Fort Church | Galle Dutch Fort |
| Galle Lighthouse | Galle Dutch Fort |
| University (Peradeniya area) | Kandy region |

> 繁體中文版說明請見下方 [繁體中文](#繁體中文)。

---

## English

### What it is

Four buildings were captured by UAV, processed into textured reality meshes with
Bentley iTwin Capture / ContextCapture, and exported into the OGC **3D Tiles 1.1**
streaming format. A lightweight React + CesiumJS front end loads the tilesets onto
a satellite-imagery globe at their true geographic positions in Sri Lanka.

### How to use it

Just open the link on any PC. The page is a fully static bundle, so:

- No software to install, no account, no Cesium ion key required by the visitor.
- Click a building in the side panel to fly to it; orbit with the mouse, zoom with
  the wheel.
- Satellite imagery is the token-free **Esri World Imagery** layer, so the globe
  renders for everyone regardless of region.

### Technical pipeline

```
ContextCapture .3sm (SQLite reality mesh)
        │  tools/sm_export/sm_to_3dtiles.py
        ▼
Per-leaf glTF/GLB  +  tileset.json   (OGC 3D Tiles 1.1, KHR_materials_unlit)
        │  tiles/<model>/…  +  tiles/registry.json
        ▼
React 18 + Resium / CesiumJS 1.122   (app/, built with Vite)
        │  GitHub Actions  →  GitHub Pages
        ▼
Public static website (Esri World Imagery basemap)
```

| Layer | Technology |
| --- | --- |
| Source data | UAV photogrammetry → ContextCapture `.3sm` (SQLite container) |
| Coordinate system | EPSG:32644 (WGS 84 / UTM zone 44N) + EPSG:5773 (EGM96 orthometric height) |
| Export | Custom Python exporter (`tools/sm_export/`) — decodes leaf nodes, re-welds position/UV pairs, writes GLB + tileset |
| Streaming format | OGC 3D Tiles 1.1, one GLB per leaf node, unlit + double-sided materials |
| Front end | React 18.3, Resium 1.19, CesiumJS 1.122, TypeScript 5.5, Vite 5.4 |
| Basemap | Esri World Imagery (no token) |
| Hosting | GitHub Pages, deployed by GitHub Actions on every push to `main` |

### How the models are seated on the ground

Each tileset is translated vertically so its lowest point rests a fixed
**1.5 m clearance** above the WGS 84 ellipsoid surface:

```
offset = sampledTerrainHeight + 1.5 m − (centroidEllipsoidalHeight + baseHeightLocal)
```

Because the globe uses the smooth WGS 84 ellipsoid (no exaggerated world
terrain), every building lands flush and consistent — no floating, no sinking.
The per-model base/top heights and the geoid-corrected ellipsoidal heights live
in `tiles/registry.json`.

### Interesting problems we solved

This project was as much a geospatial-engineering exercise as a web one. Three
problems were genuinely instructive:

#### 1. The mesh first rendered "shattered" / fragmented

Early builds showed the buildings as broken, see-through shards instead of solid
walls. The geometry itself was perfectly valid (≈488k triangles for the church,
all indices in range). The real cause was a **translucent custom shader**: an
attempt to hide stray dark faces used `translucencyMode: TRANSLUCENT`, which
turned the entire tileset translucent. On **double-sided** meshes this breaks
depth sorting, so back faces bled through front faces and the model looked
fragmented.

**Fix:** remove the translucent shader entirely and keep the materials opaque.
The geometry was never the problem — the rendering mode was. (If hiding no-data
faces is ever needed, the correct approach is an opaque alpha-test/discard, never
translucency.)

#### 2. WGS 84 ellipsoidal vs. EGM96 orthometric height datum confusion

The reality meshes are georeferenced in **EPSG:32644 + EPSG:5773**, i.e. UTM
horizontal plus **EGM96 orthometric (mean-sea-level) heights**. CesiumJS, on the
other hand, expects **WGS 84 ellipsoidal heights**. Feeding the raw orthometric
Z straight into Cesium made the buildings sink roughly **99 m underground** at
Galle, because the geoid undulation there is about **−99.31 m**.

**Fix:** apply the geoid undulation `N` during export to convert orthometric
height `H` into ellipsoidal height `h`:

```
h_ellipsoidal = H_orthometric_EGM96 + N        (N ≈ −99.31 m at Galle)
```

The corrected ellipsoidal heights are baked into every GLB and recorded in
`registry.json` (e.g. church: `143.09 + (−99.31) = 43.78 m`). After this, the
buildings sit at the correct elevation. Mixing these two vertical datums is a
classic, easy-to-miss geodesy trap — getting it right is what puts the model on
the ground instead of below it.

#### 3. Black-blotchy textures (the texture-atlas indexing bug)

After the two fixes above, the buildings were solid but still patchy with dark
blotches. ContextCapture stores each leaf node's texture atlas under a
**`SMNodeHeader.TexID`** that is *different* from the geometry `NodeId`. The
exporter had been fetching `SMTexture WHERE NodeId = …`, pairing each mesh with
the **wrong atlas**, so ~66 % of triangles sampled black padding.

**Fix:** look up `TexID` from `SMNodeHeader` and fetch the texture by that ID.
The church's black-pixel coverage dropped from **65 % to 0.2 %**, and the walls,
red-tile roofs and even rooftop solar panels render correctly.

### Build & develop

```powershell
cd app
npm install
npm run build      # production bundle (dev server is environment-specific)
```

Re-export the tiles from the source meshes:

```powershell
cd tools/sm_export
python build_all_tiles.py   # rebuilds tiles/ for all four models
```

### Repository layout

```
app/                 React + Resium front end (Vite)
tiles/               Exported 3D Tiles (GLB + tileset.json) + registry.json
tools/sm_export/     .3sm → 3D Tiles / OBJ exporters
.github/workflows/   GitHub Pages deployment
```

---

## 繁體中文

### 專案簡介

本專案是一個在瀏覽器中即時呈現的三維「數位孿生（Digital Twin）」網站，將斯里蘭卡
文化遺產建築的無人機（UAV）攝影測量實景網格直接串流到網頁中。以 CesiumJS 製作，
透過 GitHub Pages 以純靜態網站方式發佈——**免安裝、免登入，任何現代桌面或筆電瀏覽器
都能直接開啟使用。**

**線上網站：** https://di0105.github.io/sl-digital-twin/

| 模型 | 地點 |
| --- | --- |
| Yellow House（黃屋） | 加勒荷蘭古堡 Galle Dutch Fort |
| Galle Fort Church（加勒古堡教堂） | 加勒荷蘭古堡 Galle Dutch Fort |
| Galle Lighthouse（加勒燈塔） | 加勒荷蘭古堡 Galle Dutch Fort |
| University（培拉德尼亞大學一帶） | 康提 Kandy 地區 |

### 內容說明

四棟建築由無人機拍攝，透過 Bentley iTwin Capture / ContextCapture 處理成帶貼圖的
實景網格，再匯出為 OGC **3D Tiles 1.1** 串流格式。前端使用輕量的 React + CesiumJS，
將這些 tileset 載入到衛星影像地球上，並放置於斯里蘭卡的真實地理座標位置。

### 如何使用

直接在任一台電腦上開啟連結即可。整個頁面是完全靜態的封裝檔，因此：

- 無需安裝任何軟體、無需帳號、訪客也不需要 Cesium ion 金鑰。
- 在側邊面板點選建築即可飛抵該位置；用滑鼠旋轉視角、用滾輪縮放。
- 衛星底圖使用免金鑰的 **Esri World Imagery** 圖層，任何地區的使用者都能正常顯示地球。

### 技術路線

```
ContextCapture .3sm（SQLite 實景網格）
        │  tools/sm_export/sm_to_3dtiles.py
        ▼
每個葉節點一個 glTF/GLB  +  tileset.json （OGC 3D Tiles 1.1，KHR_materials_unlit）
        │  tiles/<model>/…  +  tiles/registry.json
        ▼
React 18 + Resium / CesiumJS 1.122 （app/，以 Vite 建置）
        │  GitHub Actions  →  GitHub Pages
        ▼
公開靜態網站（Esri World Imagery 底圖）
```

| 層級 | 技術 |
| --- | --- |
| 來源資料 | 無人機攝影測量 → ContextCapture `.3sm`（SQLite 容器） |
| 座標系統 | EPSG:32644（WGS 84 / UTM 44N 帶）＋ EPSG:5773（EGM96 正高） |
| 匯出 | 自製 Python 匯出工具（`tools/sm_export/`）：解碼葉節點、重新焊接位置／UV 配對、輸出 GLB 與 tileset |
| 串流格式 | OGC 3D Tiles 1.1，每個葉節點一個 GLB，無光照（unlit）＋ 雙面材質 |
| 前端 | React 18.3、Resium 1.19、CesiumJS 1.122、TypeScript 5.5、Vite 5.4 |
| 底圖 | Esri World Imagery（免金鑰） |
| 部署 | GitHub Pages，每次推送到 `main` 由 GitHub Actions 自動部署 |

### 模型如何貼合地面

每個 tileset 都會在垂直方向上平移，使其最低點固定停在 WGS 84 橢球面之上
**1.5 公尺的淨空高度**：

```
offset = 取樣地形高度 + 1.5 m − （中心點橢球高 + 區域基準底高）
```

由於地球採用平滑的 WGS 84 橢球面（未加入誇張的世界地形），每棟建築都能一致地平貼
地面——不會懸浮、也不會陷入地底。各模型的基準底高／頂高與經過大地水準面修正的橢球
高都記錄在 `tiles/registry.json` 中。

### 我們解決的幾個有趣問題

這個專案既是網頁工程，也是地理空間工程的練習。其中三個問題特別具有啟發性：

#### 1. 模型一開始 render 出來是「破碎」的

早期版本中，建築呈現為破碎、半透明的碎片，而非完整的牆面。其實幾何本身完全正確
（教堂約 48.8 萬個三角形，所有索引都在有效範圍內）。真正的原因是一個**半透明的
自訂著色器（custom shader）**：為了隱藏零星的暗面，當時使用了
`translucencyMode: TRANSLUCENT`，結果讓整個 tileset 變成半透明。在**雙面（double-
sided）**網格上，這會破壞深度排序（depth sorting），導致背面穿透到正面前方，模型
看起來就像碎掉一樣。

**解法：** 直接移除半透明著色器，材質維持不透明。問題從來不在幾何，而在算繪模式。
（若日後真的需要隱藏無資料的面，正確做法是不透明的 alpha 測試／discard，絕不能用
半透明。）

#### 2. WGS 84 橢球高 與 EGM96 正高 兩種高程基準搞混

實景網格的地理參考使用 **EPSG:32644 + EPSG:5773**，也就是 UTM 平面座標加上
**EGM96 正高（以平均海水面為基準的高程）**。然而 CesiumJS 預期的是 **WGS 84 橢球高**。
若把原始的正高 Z 值直接餵給 Cesium，建築會在加勒一帶整整**下沉約 99 公尺到地底**，
因為當地的大地水準面起伏（geoid undulation）約為 **−99.31 公尺**。

**解法：** 在匯出時套用大地水準面起伏 `N`，把正高 `H` 轉換成橢球高 `h`：

```
橢球高 = EGM96 正高 + N        （加勒一帶 N ≈ −99.31 m）
```

修正後的橢球高會烘焙進每一個 GLB，並記錄在 `registry.json`（例如教堂：
`143.09 + (−99.31) = 43.78 m`）。完成後，建築便落在正確的高程上。混用這兩種垂直
基準是大地測量中經典又容易忽略的陷阱——把它做對，才能讓模型「站在地面上」而不是
「埋在地下」。

#### 3. 貼圖出現黑斑（貼圖圖集索引錯誤）

在解決上述兩個問題後，建築雖然變得完整，卻仍布滿暗黑色斑塊。ContextCapture 會把
每個葉節點的貼圖圖集（atlas）儲存在一個**與幾何 `NodeId` 不同**的
**`SMNodeHeader.TexID`** 之下。原本的匯出工具是用 `SMTexture WHERE NodeId = …`
取貼圖，等於把每個網格配上了**錯誤的圖集**，使得約 66% 的三角形取樣到黑色填充區。

**解法：** 改為先從 `SMNodeHeader` 讀取 `TexID`，再依該 ID 取貼圖。教堂的黑色像素
覆蓋率因此從 **65% 降到 0.2%**，牆面、紅瓦屋頂、甚至屋頂上的太陽能板都能正確呈現。

### 建置與開發

```powershell
cd app
npm install
npm run build      # 正式封裝（開發伺服器依環境而定）
```

從來源網格重新匯出 tiles：

```powershell
cd tools/sm_export
python build_all_tiles.py   # 重新建置四個模型的 tiles/
```

### 專案結構

```
app/                 React + Resium 前端（Vite）
tiles/               匯出的 3D Tiles（GLB + tileset.json）與 registry.json
tools/sm_export/     .3sm → 3D Tiles / OBJ 匯出工具
.github/workflows/   GitHub Pages 部署設定
```
