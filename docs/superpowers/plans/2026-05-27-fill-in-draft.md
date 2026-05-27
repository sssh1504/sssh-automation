# 4-2 fill_in_draft.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 承辦中公文於 4-1 下載+解壓+總結後，依公文標記自動套模板填辦理文字、儲存，再依標記決定不動作或陳會。

**Architecture:** 新增 `fill_in_draft.py`（純邏輯 + 薄 Selenium 包裝層分離），讀 `extract_dir` 內 summarize_doc 產出的總結檔取標記，查 `fill_in_draft.yaml` 對應表得「辦理文字 + 動作」，於公文閱覽器分頁填字→儲存→動作。純邏輯（解析、查表、流程分支）以 pytest 離線 TDD；Selenium DOM 操作（選擇器）為實機探查後寫死的薄包裝，由 unit test 以 monkeypatch 驗證呼叫序列。

**Tech Stack:** Python 3.14、pyyaml（已裝）、selenium、pytest。

---

## 檔案結構

- Create: `fill_in_draft.py` — 模組主體
  - 純邏輯：`_read_marks(extract_dir)`、`_load_rules(config_path)`、`_lookup(marks, rules, default)`
  - Selenium 薄包裝：`_fill_text(driver, text)`、`_save(driver)`、`_click_chen_hui(driver)`、`_dump_candidates(driver, label)`
  - 公開進入點：`fill_in_draft(driver, extract_dir, config_path=CONFIG_PATH)`
  - standalone：`if __name__ == "__main__"`
- Create: `fill_in_draft.yaml` — 標記→辦理文字模板+動作 對應表
- Create: `tests/__init__.py`、`tests/conftest.py`、`tests/test_fill_in_draft.py` — 離線單元測試
- Modify: `pytest.ini` — `testpaths` 加入 `tests`
- Modify: `pending_doc_handler.py` — `handle_opened_document` 末段 chain 呼叫 `fill_in_draft`
- Modify: `README.md` — 更新專案結構樹 + 故障排除表

設計依據：`docs/superpowers/specs/2026-05-27-fill-in-draft-design.md`。

---

## Task 1: 測試基礎 + 標記解析 `_read_marks`

**Files:**
- Modify: `pytest.ini`
- Create: `tests/__init__.py`、`tests/conftest.py`
- Create: `fill_in_draft.py`
- Test: `tests/test_fill_in_draft.py`

- [ ] **Step 1: 擴充 pytest testpaths**

修改 `pytest.ini`，把 `tests` 加進 `testpaths`：

```ini
[pytest]
testpaths = doc_classifier/tests tests
python_files = test_*.py
addopts = -v
```

- [ ] **Step 2: 建立測試套件骨架**

`tests/__init__.py`（空檔）。

`tests/conftest.py`（確保 repo 根層在 sys.path，讓 `import fill_in_draft` 可用）：

```python
import pathlib
import sys

# repo 根層目錄（tests/ 的上一層）加入 sys.path，供測試 import 根層模組
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
```

- [ ] **Step 3: 寫失敗測試 — `_read_marks`**

`tests/test_fill_in_draft.py`：

```python
import textwrap

import fill_in_draft


def _write_summary(extract_dir, filename, content):
    p = extract_dir / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_read_marks_parses_second_line(tmp_path):
    _write_summary(tmp_path, "123_456總結.gemini-2.5.md", """\
        #存查分類: 資安
        ## 不參加 研習
        1. 內容
        """)
    assert fill_in_draft._read_marks(tmp_path) == ["不參加", "研習"]


def test_read_marks_no_summary_file_returns_empty(tmp_path):
    assert fill_in_draft._read_marks(tmp_path) == []


def test_read_marks_no_mark_line_returns_empty(tmp_path):
    _write_summary(tmp_path, "123_456總結.gemini.md", """\
        #存查分類: 資安
        1. 只有分類沒有標記行
        """)
    assert fill_in_draft._read_marks(tmp_path) == []


def test_read_marks_single_mark(tmp_path):
    _write_summary(tmp_path, "9_9總結.claude.md", """\
        #存查分類: 設備
        ## 汰換
        """)
    assert fill_in_draft._read_marks(tmp_path) == ["汰換"]
```

- [ ] **Step 4: 執行測試確認失敗**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'fill_in_draft'` 或 `AttributeError: _read_marks`）

- [ ] **Step 5: 實作 `_read_marks`（最小）**

建立 `fill_in_draft.py`：

```python
"""4-2:承辦中公文擬寫辦理文字。

依 docs/superpowers/specs/2026-05-27-fill-in-draft-design.md。
讀 summarize_doc 產出的總結檔取標記 → 查 fill_in_draft.yaml 對應表得
「辦理文字 + 動作」→ 於公文閱覽器分頁填字、儲存、依動作決定不動作/陳會。
"""

import pathlib

_BASE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_PATH = _BASE_DIR / "fill_in_draft.yaml"


def _read_marks(extract_dir):
    """從 extract_dir 找 *總結*.md,解析 `## 標記1 標記2` 行,回標記 list。

    找不到總結檔、或沒有以 `##` 開頭的標記行 → 回 []。
    (存查分類行開頭是單一 `#`,不會被誤判為標記行。)
    """
    extract_dir = pathlib.Path(extract_dir)
    summaries = sorted(extract_dir.glob("*總結*.md"))
    if not summaries:
        return []
    for raw in summaries[0].read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("##"):
            return line.lstrip("#").split()
    return []
```

- [ ] **Step 6: 執行測試確認通過**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -v`
Expected: PASS（4 個 `test_read_marks_*` 通過）

- [ ] **Step 7: Commit**

```bash
git add pytest.ini tests/__init__.py tests/conftest.py tests/test_fill_in_draft.py fill_in_draft.py
git commit -m "新增 fill_in_draft 標記解析 _read_marks 與測試基礎"
```

---

## Task 2: 設定載入與查表 `_load_rules` / `_lookup`

**Files:**
- Create: `fill_in_draft.yaml`
- Modify: `fill_in_draft.py`
- Test: `tests/test_fill_in_draft.py`

- [ ] **Step 1: 建立 fill_in_draft.yaml**

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
    動作: none
  - 標記: 資安
    優先序: 20
    辦理文字: "本案為資安宣導事項，擬陳會相關單位知照。"
    動作: 陳會
  - 標記: 設備
    優先序: 30
    辦理文字: "……（待填）"
    動作: none
```

- [ ] **Step 2: 寫失敗測試 — `_load_rules` / `_lookup`**

在 `tests/test_fill_in_draft.py` 追加：

```python
import yaml


_SAMPLE_CONFIG = {
    "default": {"辦理文字": "擬:", "動作": "none"},
    "rules": [
        {"標記": "資安", "優先序": 20, "辦理文字": "陳會文字", "動作": "陳會"},
        {"標記": "不參加", "優先序": 10, "辦理文字": "不參加文字", "動作": "none"},
        {"標記": "汰換", "優先序": 30, "辦理文字": "汰換文字", "動作": "備選動作"},
    ],
}


def _write_config(tmp_path):
    p = tmp_path / "fill_in_draft.yaml"
    p.write_text(yaml.safe_dump(_SAMPLE_CONFIG, allow_unicode=True), encoding="utf-8")
    return p


def test_load_rules_returns_rules_and_default(tmp_path):
    rules, default = fill_in_draft._load_rules(_write_config(tmp_path))
    assert default == {"辦理文字": "擬:", "動作": "none"}
    assert len(rules) == 3


def test_lookup_first_match_by_priority_wins(tmp_path):
    rules, default = fill_in_draft._load_rules(_write_config(tmp_path))
    # 同時有「不參加」(優先序10) 與「資安」(優先序20) → 取優先序小的「不參加」
    text, action = fill_in_draft._lookup(["資安", "不參加"], rules, default)
    assert (text, action) == ("不參加文字", "none")


def test_lookup_single_mark_hits_its_rule(tmp_path):
    rules, default = fill_in_draft._load_rules(_write_config(tmp_path))
    assert fill_in_draft._lookup(["資安"], rules, default) == ("陳會文字", "陳會")


def test_lookup_no_match_falls_back_to_default(tmp_path):
    rules, default = fill_in_draft._load_rules(_write_config(tmp_path))
    assert fill_in_draft._lookup(["不存在的標記"], rules, default) == ("擬:", "none")


def test_lookup_empty_marks_falls_back_to_default(tmp_path):
    rules, default = fill_in_draft._load_rules(_write_config(tmp_path))
    assert fill_in_draft._lookup([], rules, default) == ("擬:", "none")
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -k "load_rules or lookup" -v`
Expected: FAIL（`AttributeError: _load_rules`）

- [ ] **Step 4: 實作 `_load_rules` / `_lookup`**

在 `fill_in_draft.py` 頂部 import 加 `import yaml`，並新增：

```python
def _load_rules(config_path=CONFIG_PATH):
    """讀 yaml 設定,回 (rules, default)。

    rules:list of dict(標記/優先序/辦理文字/動作);default:dict(辦理文字/動作)。
    """
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    rules = cfg.get("rules") or []
    default = cfg.get("default") or {"辦理文字": "擬:", "動作": "none"}
    return rules, default


def _lookup(marks, rules, default):
    """依優先序由小到大掃描 rules,第一個 `標記 in marks` 命中的決定一切。

    全部沒命中 → 回 default 的 (辦理文字, 動作)。
    """
    for rule in sorted(rules, key=lambda r: r.get("優先序", 0)):
        if rule.get("標記") in marks:
            return rule.get("辦理文字", ""), rule.get("動作", "none")
    return default.get("辦理文字", ""), default.get("動作", "none")
```

- [ ] **Step 5: 執行測試確認通過**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -k "load_rules or lookup" -v`
Expected: PASS（5 個測試通過）

- [ ] **Step 6: Commit**

```bash
git add fill_in_draft.yaml fill_in_draft.py tests/test_fill_in_draft.py
git commit -m "新增 fill_in_draft 設定載入與標記查表 _load_rules/_lookup"
```

---

## Task 3: 流程分支 `fill_in_draft`（以 monkeypatch 驗證序列）

**Files:**
- Modify: `fill_in_draft.py`
- Test: `tests/test_fill_in_draft.py`

說明：Selenium DOM 操作抽成薄包裝 `_fill_text` / `_save` / `_click_chen_hui`（Task 4 才填真選擇器）。
本任務先讓 `fill_in_draft` 串起「讀標記→查表→填字→儲存→依動作分支」並以 monkeypatch 驗證呼叫序列與回傳。

- [ ] **Step 1: 寫失敗測試 — 流程分支**

在 `tests/test_fill_in_draft.py` 追加：

```python
def _patch_selenium(monkeypatch, calls, fill_ok=True, save_ok=True, chen_ok=True):
    monkeypatch.setattr(fill_in_draft, "_fill_text",
                        lambda driver, text: calls.append(("fill", text)) or fill_ok)
    monkeypatch.setattr(fill_in_draft, "_save",
                        lambda driver: calls.append(("save",)) or save_ok)
    monkeypatch.setattr(fill_in_draft, "_click_chen_hui",
                        lambda driver: calls.append(("chen_hui",)) or chen_ok)


def test_fill_in_draft_action_none_fills_saves_no_action(tmp_path, monkeypatch):
    _write_summary(tmp_path, "1_1總結.x.md", "#存查分類: 研習\n## 不參加\n")
    cfg = _write_config(tmp_path)
    calls = []
    _patch_selenium(monkeypatch, calls)
    ok = fill_in_draft.fill_in_draft(driver=None, extract_dir=tmp_path, config_path=cfg)
    assert ok is True
    assert calls == [("fill", "不參加文字"), ("save",)]


def test_fill_in_draft_action_chen_hui_clicks_after_save(tmp_path, monkeypatch):
    _write_summary(tmp_path, "1_1總結.x.md", "#存查分類: 資安\n## 資安\n")
    cfg = _write_config(tmp_path)
    calls = []
    _patch_selenium(monkeypatch, calls)
    ok = fill_in_draft.fill_in_draft(driver=None, extract_dir=tmp_path, config_path=cfg)
    assert ok is True
    assert calls == [("fill", "陳會文字"), ("save",), ("chen_hui",)]


def test_fill_in_draft_backup_action_is_noop(tmp_path, monkeypatch):
    _write_summary(tmp_path, "1_1總結.x.md", "#存查分類: 設備\n## 汰換\n")
    cfg = _write_config(tmp_path)
    calls = []
    _patch_selenium(monkeypatch, calls)
    ok = fill_in_draft.fill_in_draft(driver=None, extract_dir=tmp_path, config_path=cfg)
    # 備選動作目前 no-op:有填字+儲存,但不點任何動作鈕
    assert ok is True
    assert calls == [("fill", "汰換文字"), ("save",)]


def test_fill_in_draft_no_marks_uses_default_template(tmp_path, monkeypatch):
    # 沒有總結檔 → 無標記 → default 模板 "擬:", 動作 none
    cfg = _write_config(tmp_path)
    calls = []
    _patch_selenium(monkeypatch, calls)
    ok = fill_in_draft.fill_in_draft(driver=None, extract_dir=tmp_path, config_path=cfg)
    assert ok is True
    assert calls == [("fill", "擬:"), ("save",)]


def test_fill_in_draft_fill_fails_returns_false_no_save(tmp_path, monkeypatch):
    _write_summary(tmp_path, "1_1總結.x.md", "#存查分類: 資安\n## 資安\n")
    cfg = _write_config(tmp_path)
    calls = []
    _patch_selenium(monkeypatch, calls, fill_ok=False)
    ok = fill_in_draft.fill_in_draft(driver=None, extract_dir=tmp_path, config_path=cfg)
    assert ok is False
    assert calls == [("fill", "陳會文字")]  # 填字失敗 → 不儲存、不動作


def test_fill_in_draft_save_fails_returns_false_no_action(tmp_path, monkeypatch):
    _write_summary(tmp_path, "1_1總結.x.md", "#存查分類: 資安\n## 資安\n")
    cfg = _write_config(tmp_path)
    calls = []
    _patch_selenium(monkeypatch, calls, save_ok=False)
    ok = fill_in_draft.fill_in_draft(driver=None, extract_dir=tmp_path, config_path=cfg)
    assert ok is False
    assert calls == [("fill", "陳會文字"), ("save",)]  # 儲存失敗 → 不點陳會
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -k fill_in_draft -v`
Expected: FAIL（`AttributeError: fill_in_draft` / `_fill_text` 等尚未定義）

- [ ] **Step 3: 實作 `fill_in_draft` 與薄包裝樁**

在 `fill_in_draft.py` 新增（Selenium 包裝先放會被 monkeypatch 取代的樁，Task 4 填真實作）：

```python
def _fill_text(driver, text):
    """在公文閱覽器分頁定位辦理文字輸入框並填入 text。回 True/False。

    真實選擇器於 Task 4 實機探查後填入;在那之前回 False。
    """
    print("[fill_in_draft] _fill_text 尚未接上真實選擇器 (Task 4)")
    return False


def _save(driver):
    """點「儲存」鈕並確認成功。回 True/False。Task 4 填真實作。"""
    print("[fill_in_draft] _save 尚未接上真實選擇器 (Task 4)")
    return False


def _click_chen_hui(driver):
    """點「陳會」鈕。回 True/False。Task 4 填真實作。"""
    print("[fill_in_draft] _click_chen_hui 尚未接上真實選擇器 (Task 4)")
    return False


def fill_in_draft(driver, extract_dir, config_path=CONFIG_PATH):
    """4-2 進入點:讀標記→查表→填辦理文字→儲存→依動作不動作/陳會。

    全程不 raise:任何例外都記 log 並回 False,不影響 4-1 已完成的下載/總結。
    """
    try:
        marks = _read_marks(extract_dir)
        rules, default = _load_rules(config_path)
        text, action = _lookup(marks, rules, default)
        print(f"[fill_in_draft] 標記={marks} → 動作={action},辦理文字={text!r}")

        if not _fill_text(driver, text):
            print("[fill_in_draft] 填辦理文字失敗,中止(不儲存、不動作)。")
            return False
        if not _save(driver):
            print("[fill_in_draft] 儲存失敗,中止(不動作)。")
            return False

        if action == "陳會":
            if not _click_chen_hui(driver):
                print("[fill_in_draft] 陳會失敗;狀態停在『已儲存未送』,可人工接手。")
                return False
        elif action == "none":
            pass
        else:
            # 備選動作 / 未知值:目前只記 log 不執行
            print(f"[fill_in_draft] 動作 {action!r} 目前未實作,僅儲存不執行後續。")
        return True
    except Exception as e:
        print(f"[fill_in_draft] 例外(不影響 4-1):{type(e).__name__}: {e}")
        return False
```

- [ ] **Step 4: 執行測試確認通過**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -k fill_in_draft -v`
Expected: PASS（6 個 `test_fill_in_draft_*` 通過）

- [ ] **Step 5: 跑整個測試檔確認無回歸**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -v`
Expected: PASS（全部通過）

- [ ] **Step 6: Commit**

```bash
git add fill_in_draft.py tests/test_fill_in_draft.py
git commit -m "新增 fill_in_draft 流程分支(填字→儲存→依動作不動作/陳會)與測試"
```

---

## Task 4: 選擇器探查（實機）+ 填入 Selenium 真實作

**Files:**
- Modify: `fill_in_draft.py`

說明：本任務需在 Chrome 已登入、停在承辦中公文閱覽器分頁的狀態下實機操作，無法離線 TDD。
先用 dump helper 印出候選元素鎖定選擇器，再把 `_fill_text` / `_save` / `_click_chen_hui` 接上。

- [ ] **Step 1: 新增診斷 dump helper**

在 `fill_in_draft.py` 新增（仿 `pending_doc_handler._dump_toolbar_candidates_here`）：

```python
def _dump_candidates(driver, label="fill_in_draft"):
    """印出當前 frame 內可能的輸入框/按鈕候選,供實機鎖定選擇器。"""
    try:
        rows = driver.execute_script(
            """
            const out = [];
            const sel = 'textarea, input, button, [role=button], .x-button';
            document.querySelectorAll(sel).forEach(el => {
                out.push({
                    tag: el.tagName,
                    id: el.id || '',
                    cls: (el.className || '').toString().slice(0, 80),
                    text: (el.innerText || el.value || '').trim().slice(0, 30),
                });
            });
            return out;
            """) or []
        print(f"[fill_in_draft] _dump_candidates({label}) — {len(rows)} 個候選:")
        for r in rows:
            print(f"    <{r['tag']}> id={r['id']!r} cls={r['cls']!r} text={r['text']!r}")
    except Exception as e:
        print(f"[fill_in_draft] _dump_candidates 失敗:{type(e).__name__}: {e}")
```

- [ ] **Step 2: 實機跑 dump,鎖定選擇器**

在 Chrome 已就位（登入 + 點到承辦中公文 + 公文閱覽器分頁開啟）狀態下，於 `if __name__ == "__main__"`
（Task 5 會補完整 standalone；此步可先臨時呼叫）或 Python REPL attach driver 後呼叫
`_dump_candidates(driver)`，記下「辦理文字輸入框 / 儲存鈕 / 陳會鈕」的 id 或 class。

可能需先用 `pending_doc_handler._switch_to_frame_with`（若辦理區在 iframe 內）切到正確 frame。
把確認到的選擇器記在本步驟下方備查。

- [ ] **Step 3: 接上 `_fill_text` 真實作**

用 Step 2 鎖定的選擇器替換 `_fill_text` 樁。範例（實際選擇器以實機為準）：

```python
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _fill_text(driver, text):
    """在公文閱覽器分頁定位辦理文字輸入框並填入 text。回 True/False。"""
    try:
        ta = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "<實機鎖定選擇器>")))
        ta.clear()
        ta.send_keys(text)
        return True
    except Exception as e:
        print(f"[fill_in_draft] _fill_text 失敗:{type(e).__name__}: {e}")
        return False
```

- [ ] **Step 4: 接上 `_save` / `_click_chen_hui` 真實作**

```python
def _save(driver):
    """點「儲存」鈕並確認成功。回 True/False。"""
    try:
        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "<實機鎖定的儲存鈕選擇器>")))
        btn.click()
        # 確認儲存成功:等成功提示/按鈕狀態變化(實機確認用何訊號),以下為示意
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "<實機確認的成功訊號>")))
        return True
    except Exception as e:
        print(f"[fill_in_draft] _save 失敗:{type(e).__name__}: {e}")
        return False


def _click_chen_hui(driver):
    """點「陳會」鈕。回 True/False。"""
    try:
        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "<實機鎖定的陳會鈕選擇器>")))
        btn.click()
        return True
    except Exception as e:
        print(f"[fill_in_draft] _click_chen_hui 失敗:{type(e).__name__}: {e}")
        return False
```

- [ ] **Step 5: 確認離線測試仍綠（monkeypatch 不受真實作影響）**

Run: `C:\Python314\python.exe -m pytest tests/test_fill_in_draft.py -v`
Expected: PASS（真實作被 monkeypatch 取代，序列測試仍通過）

- [ ] **Step 6: Commit**

```bash
git add fill_in_draft.py
git commit -m "fill_in_draft 接上公文閱覽器選擇器:填辦理文字/儲存/陳會 + 診斷 dump helper"
```

---

## Task 5: 接點 chain 進 4-1 + standalone 入口

**Files:**
- Modify: `pending_doc_handler.py`
- Modify: `fill_in_draft.py`

- [ ] **Step 1: 在 `handle_opened_document` chain 呼叫 fill_in_draft**

`pending_doc_handler.py` 的 `handle_opened_document` 末段（下載+解壓+總結成功、`return True` 之前的
TODO 處）加入：

```python
    # 4-2:依公文標記擬寫辦理文字、儲存、依標記決定不動作/陳會。
    # 容錯:fill_in_draft 不 raise,失敗只回 False,不影響已完成的下載/總結。
    if extract_dir:
        try:
            from fill_in_draft import fill_in_draft
            if fill_in_draft(driver, extract_dir):
                print("[pending_doc_handler] 4-2 擬辦完成")
            else:
                print("[pending_doc_handler] 4-2 擬辦未完成(詳見上方 log),留待人工")
        except Exception as e:
            print(f"      [WARN] fill_in_draft 呼叫失敗(不影響下載流程):"
                  f"{type(e).__name__}: {e}")
```

放在原本 `# TODO:在公文閱覽器內做後續動作` 註解處，取代該 TODO。

- [ ] **Step 2: 補完 fill_in_draft.py standalone 入口**

`fill_in_draft.py` 底部新增（仿 pending_doc_handler，從 edoc 跑完整路徑供階段測試）：

```python
if __name__ == "__main__":
    import sys

    from taipeion_login_selenium import _setup_stdout_logging
    _setup_stdout_logging()

    from document_system import (
        _standalone_open_chrome_at_edoc,
        process_document_system,
    )
    driver = _standalone_open_chrome_at_edoc()
    if driver is None:
        sys.exit(1)
    # process_document_system → cascade → pending_doc → handle_opened_document
    # 內已 chain 呼叫 fill_in_draft,本入口跑完整路徑即可。
    process_document_system(driver)
```

（先用 `git show HEAD:pending_doc_handler.py` 對照其 `__main__` 寫法，確保 import 名稱一致。）

- [ ] **Step 3: 確認語法與 import 正確**

Run: `C:\Python314\python.exe -c "import fill_in_draft, pending_doc_handler; print('import ok')"`
Expected: `import ok`（無 ImportError / SyntaxError）

- [ ] **Step 4: 確認測試仍綠**

Run: `C:\Python314\python.exe -m pytest -v`
Expected: PASS（doc_classifier 與 fill_in_draft 測試全綠）

- [ ] **Step 5: Commit**

```bash
git add pending_doc_handler.py fill_in_draft.py
git commit -m "把 4-2 fill_in_draft chain 進 handle_opened_document 並補 standalone 入口"
```

---

## Task 6: README 更新 + 整合測試（實機手動）

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 README 專案結構樹**

在 `README.md` 的 `[4-1-1] summarize_doc.py` 條目下新增 4-2 條目：

```
└─[4-1]─ pending_doc_handler.py — ...
         │
         ├─[4-1-1]─ summarize_doc.py — ...
         │
         └─[4-2]─ fill_in_draft.py — 讀總結標記 → 套 fill_in_draft.yaml 模板填辦理文字 →
                   儲存 → 依標記決定不動作/陳會(備選動作預留)
```

並在「其他資源」區補一行：

```
fill_in_draft.yaml — 標記→辦理文字模板+動作 對應表(人工維護,改規則只動此檔)
```

- [ ] **Step 2: 更新 README 故障排除表**

在故障排除表新增列：

```
| 4-2 沒填辦理文字 / 沒按鈕 | 跑 fill_in_draft 的 _dump_candidates 重新鎖定選擇器;確認公文閱覽器分頁已載入辦理區 |
| 4-2 填了字但動作不對 | 檢查 fill_in_draft.yaml 標記與優先序;確認 summarize_doc 已產出總結檔(無 API key 會無標記走 default) |
```

- [ ] **Step 3: 整合測試（實機手動,先 none 後陳會）**

確保 Chrome 未鎖屏、id.txt 就位。先暫時把 yaml 命中規則的 `動作` 全設 `none`，跑：

Run: `C:\Python314\python.exe fill_in_draft.py`
Expected: 流程跑到公文閱覽器,印出 `標記=... → 動作=none`,辦理文字被填入、儲存成功,
不點任何動作鈕；log 顯示 `4-2 擬辦完成`。人工檢查公文系統內辦理文字正確、狀態未被送出。

確認無誤後，再把需要陳會的規則改回 `動作: 陳會`，重跑一次驗證陳會鈕被點且公文流轉正確。

- [ ] **Step 4: 提交前全測試**

Run: `C:\Python314\python.exe -m pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "README 補上 4-2 fill_in_draft 結構說明與故障排除"
```

---

## 風險與備註

- **選擇器是最大未知**：Task 4 必須實機探查；計畫中的 CSS 選擇器為示意，實作以 `_dump_candidates` 結果為準。辦理區可能位於 iframe，需先切 frame。
- **陳會不可復原性**：整合測試務必先用 `動作: none` 驗證填字+儲存無誤，再開 `陳會`。
- **無 API key**：summarize_doc 被跳過時無總結檔 → `_read_marks` 回 []→ default 模板 + 不動作，符合設計的安全 fallback。
