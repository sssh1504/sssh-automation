# Document Closure (結案存查) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `/document_closure/document_closure.py` 模組，提供「結案存查」功能，可從 `main.py`（`python main.py 3`）呼叫，也可獨立執行（`python document_closure/document_closure.py`）。

**Architecture:** 在 `/document_closure/` 建立 Python package，`document_closure.py` 為主進入點，重用 `document_system.py` 的 sidebar 工具函式（`_click_sidebar_item`、`_get_sidebar_paren_count`、`_switch_to_frame_with_xpath`）。`document_system.py` 的 `pending_closeout_doc` 改為直接 delegate。`main.py` 的 FEATURES tuple 從 3-tuple 改為 4-tuple 以支援 per-feature processor。

**Tech Stack:** Python 3.14、Selenium 4.x、現有 `document_system.py` 工具函式

---

## File Map

| 動作 | 路徑 | 職責 |
|------|------|------|
| 新建 | `document_closure/__init__.py` | 空檔，讓 Python 認識此 package |
| 新建 | `document_closure/document_closure.py` | 結案存查主邏輯 + standalone 進入點 |
| 修改 | `main.py` | FEATURES 改 4-tuple，新增條目 3 |
| 修改 | `document_system.py` | `pending_closeout_doc` delegate 到新模組 |
| 修改 | `README.md` | ASCII 樹新增 `[5]` 節點 |

---

## Task 1：建立 `/document_closure/` package 骨架

**Files:**
- Create: `document_closure/__init__.py`
- Create: `document_closure/document_closure.py`

- [ ] **Step 1：建立空的 `__init__.py`**

  在 `c:\Users\ldc\Documents\GitHub\sssh-automation\document_closure\__init__.py` 建立空檔（讓目錄被視為 Python package）：

  ```python
  # document_closure package
  ```

- [ ] **Step 2：建立 `document_closure.py` 主檔**

  建立 `c:\Users\ldc\Documents\GitHub\sssh-automation\document_closure\document_closure.py`：

  ```python
  """
  document_closure.py
  結案存查功能主模組 — 假設 driver 已導航到 edoc 公文首頁（已登入）。

  呼叫方式：
  1) 從 main.py 串接（FEATURES[2]，python main.py 3）：
       process_document_closure(driver)
  2) 單獨執行（跳過登入，直接開 Chrome 到 edoc）：
       C:\\Python314\\python.exe document_closure/document_closure.py
     session 過期時會提示跑 main.py 重新登入。
  """

  import sys
  import time

  sys.stdout.reconfigure(encoding='utf-8')

  # edoc 公文首頁 URL（與 document_system.py 保持一致）
  EDOC_HOME_URL = "https://edoc.gov.taipei/tcqb/home/default.jsp?inLine=Y"


  def process_document_closure(driver):
      """結案存查主流程。driver 必須已導航到 edoc 公文首頁。

      流程：
          1. 確認 current_url 在 edoc.gov.taipei
          2. 讀左側 sidebar「待結案(N)」數字
             - > 0：點進待結案清單，切到 dTreeContent frame，執行結案存查
             - = 0：印「無待結案公文，跳過」
             - 判讀失敗 (-1)：印警告，return False
          3. 切回 default_content
      回傳 True 表示流程跑完；False 表示前置檢查失敗。
      """
      from document_system import (
          _get_sidebar_paren_count,
          _click_sidebar_item,
          _switch_to_frame_with_xpath,
      )

      print("[document_closure] 開始結案存查流程...")

      try:
          current = driver.current_url
      except Exception as e:
          print(f"[ERROR] 讀 current_url 失敗：{type(e).__name__}: {e}")
          return False

      if "edoc.gov.taipei" not in current:
          print(f"[ERROR] 當前 URL 不在 edoc：{current}")
          return False

      # ── 待結案 ────────────────────────────────────────────────────────────
      print("[document_closure] 讀左側 sidebar「待結案」數...")
      count = _get_sidebar_paren_count(driver, "待結案")
      if count < 0:
          print("[document_closure] 無法判讀待結案數，保守不點，結束。")
          return False
      if count == 0:
          print("[document_closure] 待結案 = 0，無待辦，跳過。")
          return True

      print(f"[document_closure] 待結案 = {count}，點選進入...")
      if not _click_sidebar_item(driver, "待結案"):
          print("[document_closure] 點「待結案」失敗，請手動處理。")
          return False

      time.sleep(0.5)
      try:
          print(f"[document_closure] 待結案頁 URL：{driver.current_url}")
          print(f"[document_closure] 待結案頁標題：{driver.title}")
      except Exception as e:
          print(f"[document_closure] 讀狀態失敗：{type(e).__name__}: {e}")

      # ── 切到內容 frame ────────────────────────────────────────────────────
      # 待結案清單在 dTreeContent iframe 內，操作前必須切換 frame
      target_xpath = "//th[contains(normalize-space(), '公文文號')]"
      print("[document_closure] 切到 dTreeContent frame...")
      if not _switch_to_frame_with_xpath(driver, target_xpath, "待結案清單表頭"):
          print("[document_closure] 切不到內容 frame，請手動處理。")
          return False

      # ── TODO: 逐筆執行結案存查 ──────────────────────────────────────────
      # 後續待實作：逐筆讀取待結案清單，對每一筆執行「結案存查」點擊動作。
      # 參考 pending_doc() 的 _click_first_document_in_pending 模式。
      print(f"[document_closure] 找到待結案清單（{count} 筆）。")
      print("[document_closure] TODO: 逐筆執行結案存查點擊動作（尚未實作）")

      driver.switch_to.default_content()
      print("[document_closure] 結案存查流程結束。")
      return True
  ```

- [ ] **Step 3：驗證 package 可以被 import**

  在專案根目錄執行：

  ```powershell
  C:\Python314\python.exe -c "from document_closure.document_closure import process_document_closure; print('OK')"
  ```

  預期輸出：`OK`（無 ImportError）

---

## Task 2：新增 standalone 進入點

**Files:**
- Modify: `document_closure/document_closure.py`（在檔尾新增 `__main__` block）

- [ ] **Step 1：在 `document_closure.py` 末尾加 `__main__`**

  在 `document_closure/document_closure.py` 現有內容**之後**加入（不是取代，接在 `process_document_closure` 函式後面）：

  ```python

  if __name__ == "__main__":
      # 把 stdout/stderr 同步落地到 run.log — entry point 開頭就 setup，確保
      # Chrome 預清理 / 啟動 / 導航每行 print 都進 log。
      from taipeion_login_selenium import _setup_stdout_logging
      from document_system import _standalone_open_chrome_at_edoc

      _setup_stdout_logging()
      driver = _standalone_open_chrome_at_edoc()
      if driver is None:
          sys.exit(1)
      ok = process_document_closure(driver)
      sys.exit(0 if ok else 1)
  ```

- [ ] **Step 2：驗證 standalone 執行不噴語法錯誤**

  不真正開 Chrome，先做 syntax check：

  ```powershell
  C:\Python314\python.exe -m py_compile document_closure/document_closure.py
  ```

  預期：無輸出（exit code 0）

---

## Task 3：更新 `main.py` — FEATURES 改 4-tuple

**Files:**
- Modify: `main.py`

- [ ] **Step 1：讀 `main.py` 確認目前結構**

  確認目前 FEATURES 的 tuple 格式與 `main()` 內的解構方式。

  現有格式（3-tuple）：
  ```python
  FEATURES = [
      ("名稱", login_fn, post_login_fn),
      ...
  ]
  # main() 內：
  name, func, post_login = FEATURES[idx]
  ```

- [ ] **Step 2：修改 `main.py` — import 新模組**

  在 `main.py` 頂部的 import 區塊加入（緊接在現有 import 之後）：

  ```python
  from document_closure.document_closure import process_document_closure
  from document_system import process_document_system
  ```

  注意：`process_document_system` 目前是 lazy import 在 `main()` 內，改成頂層 import，順便把 lazy import 那行移除。

- [ ] **Step 3：修改 FEATURES 為 4-tuple**

  將現有的 FEATURES 清單從：

  ```python
  FEATURES = [
      ("臺北市單一帳號認證平台 — 自然人憑證登入 + 點公文（Selenium 版）", login_taipeion_selenium, click_document_card),
      ("臺北市單一帳號認證平台 — 自然人憑證登入（pyautogui 像素版）", login_taipeion, None),
  ]
  ```

  改為（第四欄 = processor 函式，None 表示登入後不再串 processor）：

  ```python
  FEATURES = [
      ("臺北市單一帳號認證平台 — 自然人憑證登入 + 點公文（Selenium 版）",
       login_taipeion_selenium, click_document_card, process_document_system),
      ("臺北市單一帳號認證平台 — 自然人憑證登入（pyautogui 像素版）",
       login_taipeion, None, None),
      ("edoc 結案存查 — 自然人憑證登入 + 待結案處理（Selenium 版）",
       login_taipeion_selenium, click_document_card, process_document_closure),
  ]
  ```

- [ ] **Step 4：修改 `main()` 解構與 processor 呼叫**

  將 `main()` 內的解構從：

  ```python
  name, func, post_login = FEATURES[idx]
  ```

  改為：

  ```python
  name, func, post_login, processor = FEATURES[idx]
  ```

  並將 hardcoded 的 `process_document_system` 呼叫區塊：

  ```python
      else:
          # post_login (click_document_card) 回 True 表示已點進公文系統 (edoc)；
          # 串接 document_system 進去做後續處理。
          if post_login(driver):
              from document_system import process_document_system
              process_document_system(driver)
  ```

  改為：

  ```python
      else:
          # post_login 回 True 後呼叫 per-feature 的 processor（若有）。
          if post_login(driver) and processor is not None:
              processor(driver)
  ```

- [ ] **Step 5：syntax check**

  ```powershell
  C:\Python314\python.exe -m py_compile main.py
  ```

  預期：無輸出（exit code 0）

---

## Task 4：更新 `document_system.py` — delegate pending_closeout_doc

**Files:**
- Modify: `document_system.py:1135-1140`

- [ ] **Step 1：將 `pending_closeout_doc` 改為 delegate**

  將現有 stub（`document_system.py` line 1135–1140）：

  ```python
  def pending_closeout_doc(driver):
      """待結案處理流程。第一版只印 TODO。"""
      _ = driver  # 同 pending_doc
      print("[pending_closeout_doc] 待結案處理流程開始（尚未實作）")
      print("[pending_closeout_doc] TODO: 切到內容 frame、讀待結案清單、逐筆結案")
      return True
  ```

  改為：

  ```python
  def pending_closeout_doc(driver):
      """待結案處理流程。Delegate 給 document_closure.document_closure。"""
      from document_closure.document_closure import process_document_closure
      return process_document_closure(driver)
  ```

- [ ] **Step 2：syntax check**

  ```powershell
  C:\Python314\python.exe -m py_compile document_system.py
  ```

  預期：無輸出（exit code 0）

---

## Task 5：更新 `README.md` 架構圖

**Files:**
- Modify: `README.md`

- [ ] **Step 1：找到現有 ASCII 樹末尾**

  README.md 的 ASCII 樹目前以 `└─[不使用]─ doc_classifier/` 結尾（在 `└─[4]─ document_system.py` 之後）。

- [ ] **Step 2：在 `[4]` 節點後、`[不使用]` 節點前插入 `[5]`**

  在 `├─[不使用]─` 那行**前面**插入：

  ```
  │
  └─[5]─ document_closure/document_closure.py — 結案存查:點 sidebar「待結案」→
          切到 dTreeContent frame → 逐筆執行結案存查（TODO 待實作點擊動作）
  ```

  同時，`└─[不使用]─` 改為 `└─[不使用]─`（若原本是 `└─` 要改回 `├─` 因為後面還有節點）。

  完整插入後的相關片段：

  ```
  ├─[4]─ document_system.py — edoc 公文系統入口:催辦/待簽收/承辦中/受會案件/待結案 cascade
          │
          └─[4-1]─ pending_doc_handler.py — ...
                  │
                  └─[4-1-1]─ summarize_doc.py — ...
  │
  ├─[5]─ document_closure/document_closure.py — 結案存查:點 sidebar「待結案」→
  │       切到 dTreeContent frame → 逐筆執行結案存查（TODO 待實作點擊動作）
  │       可單獨執行：python document_closure/document_closure.py
  │
  └─[不使用]─ doc_classifier/ — ...
  ```

---

## Task 6：整合驗證

- [ ] **Step 1：import 鏈驗證（全部模組）**

  ```powershell
  C:\Python314\python.exe -c "
  import main
  from document_closure.document_closure import process_document_closure
  from document_system import pending_closeout_doc
  print('import OK')
  "
  ```

  預期輸出：（可能有 run.log 初始化 print）最後印 `import OK`，無 ImportError。

- [ ] **Step 2：FEATURES 條目數正確**

  ```powershell
  C:\Python314\python.exe -c "
  import main
  print(f'FEATURES 共 {len(main.FEATURES)} 條')
  for i, f in enumerate(main.FEATURES):
      print(f'  [{i+1}] {f[0]}')
  "
  ```

  預期輸出：
  ```
  FEATURES 共 3 條
    [1] 臺北市單一帳號認證平台 — 自然人憑證登入 + 點公文（Selenium 版）
    [2] 臺北市單一帳號認證平台 — 自然人憑證登入（pyautogui 像素版）
    [3] edoc 結案存查 — 自然人憑證登入 + 待結案處理（Selenium 版）
  ```

- [ ] **Step 3：確認原功能 1 引數解析不受影響**

  ```powershell
  C:\Python314\python.exe -c "
  import sys
  sys.argv = ['main.py', '1']
  import main
  # main() 會嘗試真正執行，只需確認解構不爆
  print('argv parse OK')
  "
  ```

  預期：到 import main 為止不噴錯誤（實際執行不進行，因為 `__name__ != '__main__'`）。

- [ ] **Step 4：Commit**

  ```powershell
  git add document_closure/__init__.py document_closure/document_closure.py main.py document_system.py README.md
  git commit -m "新增結案存查功能模組 (document_closure)，main.py FEATURES 支援 4-tuple per-feature processor"
  ```

---

## Self-Review

**Spec coverage：**
- [x] `document_closure/document_closure.py` 為主檔 ✓
- [x] 所有程式放在 `/document_closure/` 目錄 ✓
- [x] `main.py` 加入新功能、可 `python main.py 3` 呼叫 ✓
- [x] 可單獨執行（standalone `__main__`）✓
- [x] 沿用 document_system 的待結案邏輯（delegate + reuse sidebar utils）✓
- [x] README 樹狀圖更新 `[5]` ✓

**Placeholder scan：**
- `pending_closeout_doc` delegate 後，`document_system._run_sidebar_cascade` 中呼叫 `pending_closeout_doc(driver)` 仍有效 ✓
- `process_document_closure` 中的 TODO 是明確的佔位，已標清楚「尚未實作」✓

**Type consistency：**
- `process_document_closure(driver)` 在 Task 1、Task 3、Task 4 出現的簽名一致 ✓
- `FEATURES` 4-tuple 格式在 Task 3 中完整定義，Task 6 的驗證與之一致 ✓
