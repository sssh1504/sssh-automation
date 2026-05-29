# 4-2 fill_in_draft.py 設計文件

日期：2026-05-27

## 目的

承辦中公文在 4-1（`pending_doc_handler.handle_opened_document`）下載+解壓+總結完成後，
於同一個公文閱覽器分頁內，依公文標記自動「擬寫辦理文字」並儲存，再依標記決定是否陳會。
目標是把承辦中公文的例行處置自動化，僅在規則明確時動作，其餘留給人工。

## 範圍與邊界

- 只處理「填辦理文字 → 儲存 → 依標記不動作/陳會」這一段，接在 4-1 之後。
- 一律先儲存，再依標記決定後續動作；後續動作只有 `none`（不動作）與 `陳會` 兩種會實際執行，
  另預留 `備選動作` 列舉值（目前 no-op）。
- 找不到可用標記時，套保守的預設模板、儲存、不動作。
- 不做任何超出設定檔規則的不可復原操作。

## 架構與接點

新增模組 `fill_in_draft.py`，公開進入點：

```python
def fill_in_draft(driver, extract_dir) -> bool
```

接點在 `pending_doc_handler.py` 既有 TODO（`handle_opened_document` 末段，下載+解壓+總結成功後）。
此時 driver 仍 focus 在公文閱覽器分頁、`extract_dir` 為該公文解壓目錄，直接 chain 呼叫：

```
handle_opened_document (4-1)
  ├─ _download_and_extract  → summarize_doc (4-1-1)
  └─ fill_in_draft(driver, extract_dir)   ← 新增 4-2
```

- `main.py` 的 `FEATURES` 不變（4-2 內嵌在 4-1 流程內，不是獨立 feature）。
- 提供 `if __name__ == "__main__"` standalone 入口，仿現有模組（document_system / pending_doc_handler）
  從 edoc 跑完整路徑，供階段測試。

更新後的 README 專案結構：

```
└─[4-1]─ pending_doc_handler.py
         ├─[4-1-1]─ summarize_doc.py
         └─[4-2]─ fill_in_draft.py — 讀總結標記 → 套模板填辦理文字 → 儲存 → 依標記不動作/陳會
                  └ fill_in_draft.yaml — 標記→辦理文字模板+動作 對應表
```

## 資料流

1. **讀標記**：從 `extract_dir` 找 summarize_doc 產出的 `*總結*.md`，解析第二行
   `## 標記1 標記2`（規格見 summarize_doc.md）。找不到總結檔或無標記行 → 視為「無標記」走 fallback。
2. **查表**：讀 `fill_in_draft.yaml`，依優先序由小到大掃描 rules，第一個命中的標記同時決定
   辦理文字與動作；全部沒命中 → `default`。
3. **填字**：在公文閱覽器分頁定位辦理文字輸入框，填入模板文字。
4. **儲存**：一律點「儲存」鈕，並確認儲存成功。
5. **後續動作**：依查到的 `動作` —— `none` 不動作；`陳會` 點陳會鈕；`備選動作` 目前只記 log 不執行。
6. 回 `True`/`False`，全程不 raise。

## 設定檔 schema（fill_in_draft.yaml）

```yaml
# 標記 → 辦理文字模板 + 後續動作 對應表。改規則只動此檔。
# 動作可填三種值：
#   none    — 只儲存，不做後續動作
#   陳會    — 儲存後按「陳會」鈕
#   備選動作 — 預留值，目前程式遇到只記 log 不執行，未來再接邏輯

default:                      # 無標記 / 標記未命中時的保守 fallback
  辦理文字: "擬:"
  動作: none

rules:                       # 依優先序由小到大評估，第一個命中的標記決定一切
  - 標記: 不參加
    優先序: 10
    辦理文字: "擬:不參加，存查。"
    動作: 陳會
  - 標記: 資安
    優先序: 20
    辦理文字: "本案為資安宣導事項，擬上網公告，通知相關單位，存查。"
    動作: 陳會
  - 標記: 設備
    優先序: 30
    辦理文字: "……（待填）"
    動作: none
```

- 多標記規則：公文可能有多個標記（如 `## 不參加 研習`）。依 `優先序` 由小到大掃描 rules，
  第一個命中的標記同時決定辦理文字與動作；全部沒命中 → `default`。
- 實際標記字詞、模板文字、優先序由人工維護於此 yaml；程式只負責讀取與查表。
- `pyyaml` 已是專案相依套件（doc_classifier 已用）。

## 選擇器策略（最大未知與風險）

公文閱覽器內的「辦理文字輸入框 / 儲存鈕 / 陳會鈕」目前沒有現成選擇器，與當初 `#packageBtn`
下載鈕一樣需實機探查。實作初期先做診斷用 dump helper（仿 pending_doc_handler 的
`_dump_toolbar_candidates_here`）把候選元素印出，鎖定後寫死，並補進 README 故障排除表。

## 錯誤處理（安全優先）

- `fill_in_draft` 全程包 try/except，**絕不 raise**——4-1 的下載/總結已完成，4-2 失敗只回 `False` 並記 log。
- 找不到輸入框/儲存鈕 → 記 log、回 False，**不按任何動作鈕**。
- 「儲存」一律先做且需確認成功，才考慮後續動作；儲存失敗就不往下。
- `動作: 陳會` 但找不到陳會鈕 → 記 log、回 False，狀態停在「已儲存未送」（可人工接手）。
- LOG 開頭含 ISO 8601 時間戳（全域規範），落地到既有 `run.log`。

## 測試

- **單元測試（pytest，可離線跑）**：標記解析（含無總結檔、無標記行、多標記）、yaml 查表
  （命中/未命中→default/優先序順序/未知動作值），用假的總結檔與假 yaml，不碰 Selenium。
- **選擇器探查（實機，一次性）**：跑 dump helper 鎖定輸入框/儲存/陳會選擇器。
- **整合測試（實機手動）**：standalone 入口跑完整路徑，先用 `動作: none` 驗證「填字+儲存」，
  確認無誤再開 `陳會`。
- 提交前跑 `pytest`（專案規範）。
