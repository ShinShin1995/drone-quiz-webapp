# 實作計畫：通用測驗題庫 Web App 升級與機車 804 題庫物理定位對齊

本計畫旨在透過前端 CSS 局部視窗裁剪、Python PyMuPDF 表格物理坐標分析與跨頁選項孤兒合併演算法，解決機車題庫 PDF 匯入時的圖表圖片遺失、選項/答案不完全對齊之問題，並將其作為 Web App 的第二個內建預載題庫，同時保障網頁程式運作的極致流暢與題庫 100% 精準練習。

---

## 🛠 技術方案

### 1. 答案解析與數據模型（Fail-Fast）
- **數據模型定義**：
  In JSON and system default database, each question will contain:
  - `options`: Clean option strings (e.g. `["彎路", "圓環", "遵行方向"]`).
  - `answerIndex`: Integer `0 | 1 | 2`, matching `options[answerIndex]`.
  - `answerLabel`: String `"A" | "B" | "C"`.
- **答案解析與 Fail-Fast**：
  - 答案數字由 Column 2 (物理 X 坐標在 `[75, 95]`) 提取。
  - 若解析時找不到合法的 `[1, 2, 3]` 答案、或者解析出的選項 `options` 為空，程式將**立刻拋出 ValueError 異常（Fail-Fast）**，輸出包含頁碼、Y 座標與鄰近單字的 blocking diagnostics。
- **Post-processing 驗證**：
  - 檢查總題數是否為精確的 **804**。
  - 檢查 `0 <= answerIndex < options.length`，若超出範圍則拋出錯誤並阻斷後續注入。

### 2. 圖片題的 PyMuPDF 圖像區塊物理重疊判定與 BBox
- **物理圖像 Block 重疊檢測**：
  - 使用 PyMuPDF 的 `page.get_text("dict")` 提取頁面上的所有 blocks。
  - 遍歷每個 block，若其 `block["type"] == 1`（代表它是一個 Image Block），我們提取其絕對 bounding box `image_bbox = (x0, y0, x1, y1)`。
  - 判定條件：只有當該題目的 Y 軸區間 `[y_top, y_bottom]` 與任何一個 Image Block 的 `y0` 和 `y1` 有**非零的物理重疊**時，才判定 `is_image_question = True`。
  - **拒絕盲目判斷**：若題目文字缺失，但該題目區間內**沒有檢測到任何物理 Image Block**，程式將**立刻拋出 ValueError 異常（Fail-Fast）**。
  - 純圖片題必須同時滿足題號、答案、選項（如是非題 A/B）與 crop bbox 合法性。
- **物理座標裁剪模型與 Invariant（滿寬裁剪）**：
  為了保證在任何裝置與 Viewport 下皆無失真，我們制定滿寬裁剪不變量（Invariant）：
  - `crop_x = 0`
  - `crop_width = page_width = 595.32`
  - `crop_y = y_top`
  - `crop_height = y_bottom - y_top`
  - `page_height = 841.92`
- **前端 Viewport 自適應公式**：
  網頁渲染題目時，若 `is_image_question` 為 true，我們建立高度自適應的 div 容器：
  - `scale = container_width / crop_width`
  - `container_height = crop_height * scale`
  - `background_position_y = -(crop_y * scale)`
  - `background_position_x = 0`
  - `background_size = 100% auto`

### 3. 跨頁選項與題目分割錯誤修正 (跨頁孤兒選項合併與 fail-fast)
- **孤兒選項判定**：
  在解析下一頁時，在第一個題號 word 之前的文字如果含有 `(1)` 標籤：
  - 驗證上一題的選項是否缺失或不完整。
  - 驗證孤兒選項字串是否能與上一題的選項連續，例如拼接後選項個數為 2 或 3，且索引順序連續。
  - 若無法連續或發生資料衝突，程式立刻拋出 `ValueError` (fail-fast) 並輸出 blocking diagnostics。
- **物理邊界防護**：
  圖片的 Y 軸 Crop 範圍 `y_bottom` 最多只延伸至當前頁面底部（`800`），選項則由下一頁的文字區塊獨立合併，絕不讓圖片裁剪被錯誤拉伸。
- **自動輸出修補題號**：執行時程式會自動列印出所有成功合併的跨頁題號清單，以供抽樣查證（如 Q706）。

### 4. 靜態注入的安全 Marker 防護與 JS Syntax Check
- **注入 Marker 防護**：
  在 `index.html` 的 JavaScript 段落中使用：
  ```javascript
  // MOTORCYCLE_DATABASE_START
  const motorcycleDatabase = [];
  // MOTORCYCLE_DATABASE_END
  ```
  作為精確的注入範圍。`inject_database.py` 僅會替換這兩個 Marker 之間的內容，絕不使用寬鬆 regex 以避免干擾無人機題庫的 `const database`。
- **JS Syntax Check**：
  在注入成功後，`inject_database.py` 會將 `index.html` 中的整個 `<script>` 區塊內容提取出來，寫入臨時檔案 `temp.js`。隨後呼叫系統指令 `node --check temp.js` 進行 JS 語法解析檢驗，以確保無語法錯誤。我們不在此處宣稱瀏覽器 runtime 的可用性。

### 5. 多題庫進度隔離與舊進度自動遷移 (Migration)
- **題庫 ID 宣告**：
  - 無人機題庫：`drone_quiz_default`
  - 機車題庫：`motorcycle_quiz_default`
- **LocalStorage 儲存命名空間與舊進度遷移**：
  - 新命名空間：`quiz_state_${bankId}`（如 `quiz_state_motorcycle_quiz_default`）。
  - **自動遷移策略**：在 Web App 啟動的 `init()` 邏輯中，檢查是否存在舊 Key `'drone_quiz_state'`。若存在且此時新 Key `'quiz_state_drone_quiz_default'` 尚未建立，系統將自動將舊進度數據搬移至新 Key，並於完成後**刪除**舊 Key `'drone_quiz_state'`。若新 Key 已存在，則直接讀取新 Key。此舉在 100% 保留用戶舊進度的同時，完成了向新命名空間的升級防護。
  - `resetAllProgress` 將明確重置當前正切換的題庫進度，並在 UI 上清晰指明題庫名稱。

---

## Proposed Changes

### [Web App Component]
#### [MODIFY] [index.html](file:///c:/Users/WS293/OneDrive/桌面/Antigravity/無人機測驗題庫WEBAPP/index.html)
- **嵌入機車題庫資料**：在 JavaScript 代碼中新增預載標記，並嵌入機車題庫 `motorcycleDatabase`。
- **自適應 BBox 渲染**：利用 aspect ratio 重新計算圖片高度，實現手機/桌機 viewport 的自適應無失真顯示。
- **舊進度遷移與進度隔離**：在 `init` 內增加 `'drone_quiz_state'` 到 `'quiz_state_drone_quiz_default'` 的自動遷移與刪除舊 Key 邏輯。

### [Python Scripts]
#### [MODIFY] [preload_motorcycle_quiz.py](file:///c:/Users/WS293/OneDrive/桌面/Antigravity/無人機測驗題庫WEBAPP/preload_motorcycle_quiz.py)
- 改用「獨立解耦題號去重與跨頁孤兒選項合併演算法」，包含 fail-fast、PyMuPDF 的 dict 物理 Image Block 檢測、物理坐標模型與選項順序驗證。

#### [MODIFY] [inject_database.py](file:///c:/Users/WS293/OneDrive/桌面/Antigravity/無人機測驗題庫WEBAPP/inject_database.py)
- 改用明確的 Marker 注入，並在注入後使用 `node --check` 對 JS 進行語法安全性驗證。

---

## Verification Plan

### Automated Verification
- 執行 `preload_motorcycle_quiz.py`，若有解析失敗直接 fail-fast。
- 驗證產出的 JSON 數據：
  - 題數必須精確等於 **804**。
  - `originalId` 無重複、無缺號，完全連續。
  - 每題 `options.length` 為 2 或 3。
  - 答案與選項內容完全對應，`0 <= answerIndex < options.length`。
  - 所有被判定為 `is_image_question` 的題目，均滿足 BBox 合法性：
    - 驗證實體圖片檔案 `pages/page_${page}.png` 確實存在。
    - `0 <= crop_x < 595.32`
    - `0 <= crop_y < 841.92`
    - `crop_width > 0`且`crop_height > 0`。
    - `crop_x + crop_width <= 595.32`
    - `crop_y + crop_height <= 841.92`
    - 滿足滿寬 Invariant：`crop_x === 0` 且 `crop_width === 595.32`。
- 執行 `inject_database.py`，驗證注入成功且通過 `node --check` 的 JS syntax check。

### Manual Verification
- 打開 [index.html](file:///c:/Users/WS293/OneDrive/桌面/Antigravity/無人機測驗題庫WEBAPP/index.html)。
- 在 Chrome DevTools 中切換為手機模式與桌機模式，檢查圖片題（如第 706 題）的圓環號誌圖片是否無壓扁、錯位或截斷。
- 進行模擬作答，答錯與答對，重新整理頁面，驗證兩個題庫的進度是否完美隔離，且 reset 只清除當前題庫。

[REVIEW_PASSED_BY_CODEX]
