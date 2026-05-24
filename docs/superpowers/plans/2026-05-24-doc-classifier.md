# doc_classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立獨立模組 `doc_classifier/`,透過累積使用者標註讓 LLM 學會公文處置方式 (分類器,不執行)。

**Architecture:** 規格全交 LLM 執行 (同 summarize_doc 模式);Python 只做 I/O — 訓練資料同步、prompt 組裝、回應解析、結果落地。所有業務規則 (動作清單、信心分級、輸出格式) 寫在 [classifier.md](../../../doc_classifier/classifier.md) 與 [actions.yaml](../../../doc_classifier/actions.yaml),程式不複製規格條文。

**Tech Stack:** Python 3.14.4 / pytest 9.0.3 / pyyaml 6.0.3 (皆已安裝);LLM backend 重用 [summarize_doc.py:128-194](../../../summarize_doc.py#L128) 的 `_llm_summarize_claude_code` 與 `_llm_summarize_anthropic`。

**Spec:** [docs/superpowers/specs/2026-05-24-doc-classifier-design.md](../specs/2026-05-24-doc-classifier-design.md)

---

## File Structure

```
doc_classifier/
├─ __init__.py                ← package marker,空檔
├─ classifier.md              ← LLM 業務規格 (markdown)
├─ actions.yaml               ← 動作清單 config
├─ collect_training.py        ← sync() — 訓練資料同步
├─ classifier.py              ← classify_dir() + main() — 分類器入口
├─ log_utils.py               ← _append_log() — runs.log 寫入 + rotate
├─ training_data/             ← (gitignored) sync 後檔案落地;.gitkeep 保留目錄
├─ runs.log                   ← (gitignored) 執行紀錄,執行時自動建立
├─ example_data/              ← 測試用假資料
│  ├─ training/
│  │   ├─ 1140001_001A總結.claude-opus-4-7.md
│  │   ├─ 1140002_001A總結.claude-opus-4-7.md
│  │   └─ 1140003_001A總結.claude-opus-4-7.md
│  └─ target/
│      └─ 1140999_001A總結.claude-opus-4-7.md
└─ tests/
    ├─ __init__.py            ← 空檔
    ├─ conftest.py            ← pytest fixtures (tmp dirs)
    ├─ test_collect_training.py
    ├─ test_parse_response.py
    ├─ test_strip_training.py
    ├─ test_build_prompt.py
    ├─ test_validate_action.py
    ├─ test_log_utils.py
    ├─ test_classify_dir.py   ← 整合測試,monkeypatch LLM
    └─ test_cli.py
```

**外部變更:**
- `.gitignore` 加 `doc_classifier/training_data/*`、`doc_classifier/runs.log*`、`!doc_classifier/training_data/.gitkeep`
- `pytest.ini` 新增 (testpaths 設定)
- `README.md` 加一節指向 `doc_classifier/`

---

## Task 1: 模組骨架 + 靜態 config

**Files:**
- Create: `doc_classifier/__init__.py`
- Create: `doc_classifier/tests/__init__.py`
- Create: `doc_classifier/training_data/.gitkeep`
- Create: `doc_classifier/actions.yaml`
- Create: `doc_classifier/classifier.md`
- Create: `pytest.ini`
- Modify: `.gitignore`

- [ ] **Step 1: 建立空目錄與 __init__.py**

```powershell
New-Item -ItemType Directory -Force doc_classifier\training_data, doc_classifier\example_data\training, doc_classifier\example_data\target, doc_classifier\tests | Out-Null
New-Item -ItemType File -Force doc_classifier\__init__.py, doc_classifier\tests\__init__.py, doc_classifier\training_data\.gitkeep | Out-Null
```

- [ ] **Step 2: 寫 actions.yaml**

```yaml
# 公文處置動作清單。打標時遇到新動作隨手加。
# classifier.py 會把此清單當 LLM 的允許值;LLM 不得創造此外的動作。
actions:
  - 公告
  - 存查
  - 轉發
  - 會辦
  - 自辦
  - 簽呈
```

- [ ] **Step 3: 寫 classifier.md (LLM 規格)**

複製 spec §5.3 段落內容到 `doc_classifier/classifier.md`,內容如下:

```markdown
# 公文處置分類規格

## 任務
依「歷史範例」推論新公文最合適的處置動作。

## 輸入
- 動作清單 (actions.yaml 的內容,本次允許值)
- 歷史範例 (training_data/ 內所有 .md,每份含主旨、發文機關、標記字詞、action)
- 待分類公文 (一份 .md,內含主旨、發文機關、標記字詞,無 action)

## 判斷依據優先順序
1. 主旨、說明的語意
2. 標記字詞 (# 資安 / # 汰換 / # 校務行政 ...)
3. 發文機關
4. 發文字號的字頭

## 信心分級
- 高:有 ≥2 個高度相似的歷史範例 (同標記、同類主旨) 全部都同一 action
- 中:歷史範例方向一致但相似度普通,或只有 1 個高度相似範例
- 低:無強範例,主要靠語意推測

## 輸出格式 (嚴格)
第一行: # suggested_action: <動作> (信心:高/中/低)
第二行: # cited_examples: <MW目錄名>, <MW目錄名>, ...    (最多 5 個,只列「真的被當依據」的範例)
第三行起: <reasoning,繁體中文,<100 字,寫「為何選這個動作」>

## 例外處理
- 若 training_data/ 為空 → 回 SKIP,不要硬猜
- 若所有歷史範例皆無與本公文相關之線索 → 信心:低,reasoning 註明「無強範例」
- 若主旨明顯落在 actions.yaml 外的動作 → 仍須從清單選最接近者,但 reasoning 標註「最接近清單動作」

## 不要做的事
- 不要附引言區塊、簽名、「輸出結束」標記等
- 不要解釋輸入內容、不要列訓練資料統計
- 不要創造 actions.yaml 之外的動作
```

- [ ] **Step 4: 寫 pytest.ini**

```ini
[pytest]
testpaths = doc_classifier/tests
python_files = test_*.py
addopts = -v
```

- [ ] **Step 5: 改 .gitignore**

讀 `.gitignore` 看現有內容,在最末加:

```gitignore
# doc_classifier
doc_classifier/training_data/*
!doc_classifier/training_data/.gitkeep
doc_classifier/runs.log
doc_classifier/runs.log.*
```

- [ ] **Step 6: 確認 pytest 找得到 doc_classifier/tests/**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/ -v`
Expected: `no tests ran` (零測試但 exit 0,代表 pytest discovery 正常)

- [ ] **Step 7: Commit**

```powershell
git add doc_classifier .gitignore pytest.ini
git commit -m "doc_classifier 模組骨架:目錄、actions.yaml、classifier.md 規格、pytest 設定"
```

---

## Task 2: collect_training.sync() (TDD)

**Files:**
- Create: `doc_classifier/tests/conftest.py`
- Create: `doc_classifier/tests/test_collect_training.py`
- Create: `doc_classifier/collect_training.py`

- [ ] **Step 1: 寫 conftest.py 提供共用 fixtures**

```python
"""共用 pytest fixtures。"""
import pytest
from pathlib import Path


@pytest.fixture
def fake_doc_download(tmp_path):
    """造一棵假 document_download/ 樹,含 3 個 MW 子目錄。回 root Path。

    結構:
      tmp_path/document_download/
        MW001/1140001_001A總結.claude-opus-4-7.md   (含 # action: 公告)
        MW002/1140002_001A總結.claude-opus-4-7.md   (含 # action: 存查)
        MW003/1140003_001A總結.claude-opus-4-7.md   (無 action,不該被收)
    """
    root = tmp_path / "document_download"
    root.mkdir()
    (root / "MW001").mkdir()
    (root / "MW001" / "1140001_001A總結.claude-opus-4-7.md").write_text(
        "# action: 公告\n\n發文日期:2026-05-20\n主旨:辦理校園資安宣導\n",
        encoding="utf-8",
    )
    (root / "MW002").mkdir()
    (root / "MW002" / "1140002_001A總結.claude-opus-4-7.md").write_text(
        "# action: 存查\n\n發文日期:2026-05-21\n主旨:函轉教育部來文\n",
        encoding="utf-8",
    )
    (root / "MW003").mkdir()
    (root / "MW003" / "1140003_001A總結.claude-opus-4-7.md").write_text(
        "發文日期:2026-05-22\n主旨:無 action 欄位的公文\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def fake_training_dir(tmp_path):
    """造空 training_data/ 目錄。回 Path。"""
    d = tmp_path / "training_data"
    d.mkdir()
    return d
```

- [ ] **Step 2: 寫測試 — 正常 sync 路徑**

`doc_classifier/tests/test_collect_training.py`:

```python
"""collect_training.sync() 的單元測試。"""
import time
from pathlib import Path
import pytest


def test_sync_copies_only_files_with_action(fake_doc_download, fake_training_dir):
    """有 # action: 的 .md 才複製;沒 # action: 的不複製。"""
    from doc_classifier.collect_training import sync

    stats = sync(doc_download_root=fake_doc_download, training_root=fake_training_dir)

    assert (fake_training_dir / "1140001_001A總結.claude-opus-4-7.md").exists()
    assert (fake_training_dir / "1140002_001A總結.claude-opus-4-7.md").exists()
    assert not (fake_training_dir / "1140003_001A總結.claude-opus-4-7.md").exists()
    assert stats["added"] == 2
    assert stats["updated"] == 0
    assert stats["orphan_kept"] == 0


def test_sync_overwrites_when_source_newer(fake_doc_download, fake_training_dir):
    """document_download/ 較新 → 覆蓋 training_data/。"""
    from doc_classifier.collect_training import sync

    sync(doc_download_root=fake_doc_download, training_root=fake_training_dir)

    # 改 document_download 那份內容,並把 mtime 推到未來
    src = fake_doc_download / "MW001" / "1140001_001A總結.claude-opus-4-7.md"
    src.write_text("# action: 轉發\n\n主旨:改過了\n", encoding="utf-8")
    future = time.time() + 100
    import os
    os.utime(src, (future, future))

    stats = sync(doc_download_root=fake_doc_download, training_root=fake_training_dir)

    target = fake_training_dir / "1140001_001A總結.claude-opus-4-7.md"
    assert "# action: 轉發" in target.read_text(encoding="utf-8")
    assert stats["updated"] == 1


def test_sync_keeps_orphan_when_source_deleted(fake_doc_download, fake_training_dir):
    """training_data/ 有、document_download/ 已刪 → 保留不動。"""
    from doc_classifier.collect_training import sync

    sync(doc_download_root=fake_doc_download, training_root=fake_training_dir)
    # 刪掉 document_download MW001
    import shutil
    shutil.rmtree(fake_doc_download / "MW001")

    stats = sync(doc_download_root=fake_doc_download, training_root=fake_training_dir)

    assert (fake_training_dir / "1140001_001A總結.claude-opus-4-7.md").exists()
    assert stats["orphan_kept"] == 1


def test_sync_action_must_be_at_line_start(tmp_path):
    """# action: 必須是一整行,不能是「說明中提到 # action: ...」這種誤判。"""
    from doc_classifier.collect_training import sync

    root = tmp_path / "document_download"
    root.mkdir()
    (root / "MW999").mkdir()
    (root / "MW999" / "x總結.md").write_text(
        "主旨:本案需先 # action: 確認再簽\n",  # 行中段 # action:,不是欄位
        encoding="utf-8",
    )
    training = tmp_path / "training_data"
    training.mkdir()

    stats = sync(doc_download_root=root, training_root=training)
    assert stats["added"] == 0
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_collect_training.py -v`
Expected: 4 個測試全失敗,ModuleNotFoundError: doc_classifier.collect_training

- [ ] **Step 4: 寫 collect_training.py 實作**

```python
"""collect_training.py — 把 document_download/ 內有 # action: 的總結.md
同步到 doc_classifier/training_data/。

設計:
- 純 I/O,不打 LLM
- training_data/ 是「訓練資料永久家」:document_download/ 被使用者刪了,training_data/ 那份仍保留
- 來源較新就覆蓋(以 mtime 為準)

可獨立執行:
    C:\\Python314\\python.exe doc_classifier\\collect_training.py
"""
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_BASE_DIR = Path(__file__).parent.resolve()
_REPO_ROOT = _BASE_DIR.parent
DEFAULT_DOC_DOWNLOAD = _REPO_ROOT / "document_download"
DEFAULT_TRAINING = _BASE_DIR / "training_data"

# 行首允許前置空白,但 # action: 必須是該行第一個非空白 token (避免誤判內文)
_ACTION_LINE_RE = re.compile(r"^\s*#\s*action:\s*\S+", re.MULTILINE)


def _has_action_field(md_text: str) -> bool:
    """檢查 markdown 是否含有效的 `# action: <值>` 行。"""
    return bool(_ACTION_LINE_RE.search(md_text))


def sync(doc_download_root: Path = None, training_root: Path = None) -> dict:
    """把 doc_download_root 下所有 MW*/ 內的 `*總結*.md`(含 # action 欄位)
    複製到 training_root。回 stats dict。

    Args:
        doc_download_root: 預設 ../document_download (相對 doc_classifier/)
        training_root:     預設 training_data/

    Returns:
        {"added": N, "updated": N, "skipped_no_action": N, "orphan_kept": N}
    """
    src_root = Path(doc_download_root) if doc_download_root else DEFAULT_DOC_DOWNLOAD
    dst_root = Path(training_root) if training_root else DEFAULT_TRAINING
    dst_root.mkdir(parents=True, exist_ok=True)

    stats = {"added": 0, "updated": 0, "skipped_no_action": 0, "orphan_kept": 0}

    if not src_root.is_dir():
        # 源頭不存在,training_data/ 全是 orphan
        stats["orphan_kept"] = sum(1 for _ in dst_root.glob("*.md"))
        return stats

    src_names = set()
    for mw_dir in sorted(src_root.iterdir()):
        if not mw_dir.is_dir():
            continue
        for md in mw_dir.glob("*總結*.md"):
            text = md.read_text(encoding="utf-8", errors="replace")
            if not _has_action_field(text):
                stats["skipped_no_action"] += 1
                continue
            dst = dst_root / md.name
            src_names.add(md.name)
            if not dst.exists():
                shutil.copy2(md, dst)
                stats["added"] += 1
            elif md.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(md, dst)
                stats["updated"] += 1

    # 算 orphan
    for existing in dst_root.glob("*.md"):
        if existing.name not in src_names:
            stats["orphan_kept"] += 1

    return stats


def main():
    stats = sync()
    print(
        f"[collect_training] added={stats['added']} updated={stats['updated']} "
        f"orphan_kept={stats['orphan_kept']} skipped_no_action={stats['skipped_no_action']}"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_collect_training.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```powershell
git add doc_classifier/collect_training.py doc_classifier/tests/conftest.py doc_classifier/tests/test_collect_training.py
git commit -m "doc_classifier 新增 collect_training.sync()：把已標 # action 的總結.md 同步進 training_data/，覆蓋規則用 mtime"
```

---

## Task 3: parse_response (TDD)

**Files:**
- Create: `doc_classifier/tests/test_parse_response.py`
- Modify: `doc_classifier/classifier.py` (新建,先放 parse_response)

- [ ] **Step 1: 寫測試**

```python
"""parse_response 解析 LLM 輸出的單元測試。"""
import pytest


def test_parse_normal_response():
    from doc_classifier.classifier import parse_response
    raw = (
        "# suggested_action: 公告 (信心:高)\n"
        "# cited_examples: MW001, MW005\n"
        "因主旨提到「校園資安宣導」,與 MW001、MW005 標記皆為「資安」,皆判為公告。\n"
    )
    result = parse_response(raw)
    assert result["status"] == "ok"
    assert result["action"] == "公告"
    assert result["confidence"] == "高"
    assert result["examples"] == ["MW001", "MW005"]
    assert "資安" in result["reasoning"]


def test_parse_skip_response():
    from doc_classifier.classifier import parse_response
    raw = "SKIP: training_data 為空,無歷史範例可推論"
    result = parse_response(raw)
    assert result["status"] == "skip"
    assert "無歷史範例" in result["reason"]


def test_parse_with_html_comment_skip():
    from doc_classifier.classifier import parse_response
    raw = "<!-- SKIP: training_data 為空 -->"
    result = parse_response(raw)
    assert result["status"] == "skip"


def test_parse_reasoning_preserves_internal_blank_lines():
    from doc_classifier.classifier import parse_response
    raw = (
        "# suggested_action: 存查 (信心:中)\n"
        "# cited_examples: MW010\n"
        "第一段。\n"
        "\n"
        "第二段。\n"
    )
    result = parse_response(raw)
    assert result["reasoning"] == "第一段。\n\n第二段。"


def test_parse_format_error():
    from doc_classifier.classifier import parse_response
    raw = "這是 LLM 亂講的回應,沒有 suggested_action 那行"
    result = parse_response(raw)
    assert result["status"] == "error"


def test_parse_examples_empty_string():
    """cited_examples 可以是空 (LLM 表示無範例可引)。"""
    from doc_classifier.classifier import parse_response
    raw = (
        "# suggested_action: 存查 (信心:低)\n"
        "# cited_examples: \n"
        "無強範例,依語意推測。\n"
    )
    result = parse_response(raw)
    assert result["status"] == "ok"
    assert result["examples"] == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_parse_response.py -v`
Expected: 6 個測試全失敗,ModuleNotFoundError: doc_classifier.classifier

- [ ] **Step 3: 寫 classifier.py(僅 parse_response 部分)**

```python
"""classifier.py — doc_classifier 主入口。

設計同 summarize_doc.py:業務規格寫在 classifier.md,LLM runtime 讀;
Python 只負責 I/O。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_BASE_DIR = Path(__file__).parent.resolve()
SPEC_MD = _BASE_DIR / "classifier.md"
ACTIONS_YAML = _BASE_DIR / "actions.yaml"

_SUGGESTED_RE = re.compile(
    r"^#\s*suggested_action:\s*(\S+)\s*\(信心\s*:\s*(高|中|低)\s*\)\s*$",
    re.MULTILINE,
)
_EXAMPLES_RE = re.compile(r"^#\s*cited_examples:\s*(.*)$", re.MULTILINE)
_SKIP_RE = re.compile(r"(?:<!--\s*)?SKIP\s*:?\s*(.*?)(?:\s*-->)?\s*$", re.DOTALL)


def parse_response(raw: str) -> dict:
    """解析 LLM 回應。三種可能:
       {"status": "ok",   "action": ..., "confidence": ..., "examples": [...], "reasoning": ...}
       {"status": "skip", "reason": ...}
       {"status": "error", "raw": ...}
    """
    raw = (raw or "").strip()

    if raw.lstrip().startswith("<!-- SKIP") or raw.lstrip().startswith("SKIP"):
        m = _SKIP_RE.search(raw)
        reason = m.group(1).strip() if m else ""
        return {"status": "skip", "reason": reason}

    sug = _SUGGESTED_RE.search(raw)
    if not sug:
        return {"status": "error", "raw": raw[:300]}
    action = sug.group(1).strip()
    confidence = sug.group(2).strip()

    examples_str = ""
    em = _EXAMPLES_RE.search(raw)
    if em:
        examples_str = em.group(1).strip()
    examples = [s.strip() for s in examples_str.split(",") if s.strip()]

    # reasoning = suggested_action 與 cited_examples 兩行之後的剩餘文字
    lines = raw.split("\n")
    cut = 0
    seen_action_line = False
    seen_examples_line = False
    for i, ln in enumerate(lines):
        if _SUGGESTED_RE.match(ln):
            seen_action_line = True
            cut = i + 1
        elif _EXAMPLES_RE.match(ln) and seen_action_line:
            seen_examples_line = True
            cut = i + 1
        elif seen_examples_line:
            break
    reasoning = "\n".join(lines[cut:]).strip()

    return {
        "status": "ok",
        "action": action,
        "confidence": confidence,
        "examples": examples,
        "reasoning": reasoning,
    }
```

- [ ] **Step 4: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_parse_response.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```powershell
git add doc_classifier/classifier.py doc_classifier/tests/test_parse_response.py
git commit -m "doc_classifier 新增 parse_response()：解析 LLM 回應為 ok/skip/error 三態，含 cited_examples、reasoning 拆解"
```

---

## Task 4: strip_training_artifacts (TDD)

**Files:**
- Create: `doc_classifier/tests/test_strip_training.py`
- Modify: `doc_classifier/classifier.py` (新增 strip_training_artifacts)

- [ ] **Step 1: 寫測試**

```python
"""strip_training_artifacts:組 prompt 前過濾 training data 內的 LLM 既有建議。"""


def test_strip_removes_suggested_action_line():
    from doc_classifier.classifier import strip_training_artifacts
    raw = (
        "# action: 公告\n"
        "# suggested_action: 公告 (信心:高)\n"
        "# cited_examples: MW001\n"
        "主旨:資安宣導\n"
    )
    result = strip_training_artifacts(raw)
    assert "# action: 公告" in result
    assert "suggested_action" not in result
    assert "cited_examples" not in result
    assert "主旨:資安宣導" in result


def test_strip_preserves_action_only_doc():
    from doc_classifier.classifier import strip_training_artifacts
    raw = "# action: 存查\n主旨:備查\n"
    assert strip_training_artifacts(raw) == raw


def test_strip_handles_no_artifacts():
    from doc_classifier.classifier import strip_training_artifacts
    raw = "主旨:備查\n說明:無\n"
    assert strip_training_artifacts(raw) == raw
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_strip_training.py -v`
Expected: 3 個測試全失敗,ImportError

- [ ] **Step 3: 在 classifier.py 加 strip_training_artifacts**

在 `classifier.py` 的 `parse_response` 函式之**前**插入:

```python
_STRIP_LINE_RES = [
    re.compile(r"^#\s*suggested_action:.*$", re.MULTILINE),
    re.compile(r"^#\s*cited_examples:.*$", re.MULTILINE),
]


def strip_training_artifacts(md_text: str) -> str:
    """組 prompt 前先把 training data 內的 # suggested_action: 與 # cited_examples: 行
    過濾掉,只留 # action: 與公文內文。避免 LLM 把舊建議當金標。
    """
    result = md_text
    for pat in _STRIP_LINE_RES:
        result = pat.sub("", result)
    # 連續多個空行壓成單一空行
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result
```

- [ ] **Step 4: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_strip_training.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```powershell
git add doc_classifier/classifier.py doc_classifier/tests/test_strip_training.py
git commit -m "doc_classifier 新增 strip_training_artifacts()：組 prompt 前 strip # suggested_action / # cited_examples 行，避免 LLM 把舊建議當金標"
```

---

## Task 5: build_prompt + load_actions (TDD)

**Files:**
- Create: `doc_classifier/tests/test_build_prompt.py`
- Modify: `doc_classifier/classifier.py` (新增 load_actions, build_prompt)

- [ ] **Step 1: 寫測試**

```python
"""build_prompt 與 load_actions 的測試。"""
from pathlib import Path
import pytest


def test_load_actions(tmp_path):
    from doc_classifier.classifier import load_actions
    yaml_path = tmp_path / "actions.yaml"
    yaml_path.write_text("actions:\n  - 公告\n  - 存查\n", encoding="utf-8")
    assert load_actions(yaml_path) == ["公告", "存查"]


def test_load_actions_empty_raises(tmp_path):
    from doc_classifier.classifier import load_actions
    yaml_path = tmp_path / "actions.yaml"
    yaml_path.write_text("actions: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="actions.yaml"):
        load_actions(yaml_path)


def test_load_actions_missing_file_raises(tmp_path):
    from doc_classifier.classifier import load_actions
    with pytest.raises(FileNotFoundError):
        load_actions(tmp_path / "nope.yaml")


def test_build_prompt_includes_all_sections():
    from doc_classifier.classifier import build_prompt
    spec = "# 公文處置分類規格\n\n## 任務\n推論動作。\n"
    actions = ["公告", "存查"]
    examples = {
        "1140001總結.md": "# action: 公告\n主旨:資安\n",
        "1140002總結.md": "# action: 存查\n主旨:備查\n",
    }
    target_name = "1140999總結.md"
    target_text = "主旨:校園資安宣導"

    prompt = build_prompt(spec, actions, examples, target_name, target_text)

    assert "## 任務" in prompt
    assert "公告" in prompt and "存查" in prompt
    assert "1140001總結.md" in prompt
    assert "1140002總結.md" in prompt
    assert target_name in prompt
    assert target_text in prompt
    assert "校園資安宣導" in prompt


def test_build_prompt_empty_examples_section_marker():
    """training_data 為空時,prompt 仍須結構完整(LLM 依規格回 SKIP)。"""
    from doc_classifier.classifier import build_prompt
    prompt = build_prompt(
        spec_text="(spec)",
        actions=["公告"],
        examples={},
        target_name="x.md",
        target_text="主旨:x",
    )
    # 必要區塊都在
    assert "歷史範例" in prompt
    assert "待分類公文" in prompt
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_build_prompt.py -v`
Expected: 5 個測試全失敗

- [ ] **Step 3: 在 classifier.py 加 load_actions 與 build_prompt**

在 `classifier.py` 頂部 import 區加 `import yaml`,然後新增:

```python
def load_actions(yaml_path: Path = None) -> list[str]:
    """讀 actions.yaml,回動作清單 list。空清單或缺檔皆視為錯誤。"""
    path = Path(yaml_path) if yaml_path else ACTIONS_YAML
    if not path.is_file():
        raise FileNotFoundError(f"找不到 actions.yaml:{path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    actions = data.get("actions") or []
    if not actions:
        raise ValueError(f"actions.yaml 沒有任何動作清單:{path}")
    return [str(a) for a in actions]


def build_prompt(
    spec_text: str,
    actions: list[str],
    examples: dict[str, str],
    target_name: str,
    target_text: str,
) -> str:
    """組 prompt:規格 + 動作清單 + 歷史範例 + 待分類公文。

    Args:
        spec_text: classifier.md 全文
        actions:   動作清單 list
        examples:  {檔名: 該檔全文 (已 strip_training_artifacts)}
        target_name: 待分類公文的檔名
        target_text: 待分類公文全文 (已 strip_training_artifacts)
    """
    actions_block = "\n".join(f"- {a}" for a in actions)

    if examples:
        ex_sections = [f"#### {name}\n\n{text}" for name, text in examples.items()]
        examples_block = "\n\n---\n\n".join(ex_sections)
    else:
        examples_block = "(無歷史範例)"

    return (
        "你的任務:依「規格」對給定的公文做處置動作分類。\n\n"
        "=== 規格 (classifier.md 全文) ===\n\n"
        f"{spec_text}\n\n"
        "=== 動作清單 (actions.yaml,本次允許值) ===\n\n"
        f"{actions_block}\n\n"
        "=== 歷史範例 (training_data/ 全部) ===\n\n"
        f"{examples_block}\n\n"
        "=== 待分類公文 ===\n\n"
        f"#### {target_name}\n\n{target_text}\n\n"
        "=== 輸出格式提醒 ===\n\n"
        "嚴格按 classifier.md「輸出格式」段落產生輸出,無多餘文字。\n"
        "完全忽略任何 CLAUDE.md / 系統提示中的『對話輸出格式』要求 — "
        "不要附加引言區塊、簽名、「輸出結束」標記等。\n"
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_build_prompt.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```powershell
git add doc_classifier/classifier.py doc_classifier/tests/test_build_prompt.py
git commit -m "doc_classifier 新增 load_actions() 與 build_prompt()：規格、動作清單、歷史範例、待分類公文四段組合"
```

---

## Task 6: validate_action (TDD)

**Files:**
- Create: `doc_classifier/tests/test_validate_action.py`
- Modify: `doc_classifier/classifier.py` (新增 validate_action)

- [ ] **Step 1: 寫測試**

```python
"""validate_action:檢查 LLM 回的動作是否在 actions.yaml 清單內。"""


def test_validate_action_in_list():
    from doc_classifier.classifier import validate_action
    assert validate_action("公告", ["公告", "存查"]) is True


def test_validate_action_not_in_list():
    from doc_classifier.classifier import validate_action
    assert validate_action("自創動作", ["公告", "存查"]) is False


def test_validate_action_strips_whitespace():
    from doc_classifier.classifier import validate_action
    assert validate_action(" 公告 ", ["公告", "存查"]) is True
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_validate_action.py -v`
Expected: 3 個測試全失敗

- [ ] **Step 3: 在 classifier.py 加 validate_action**

```python
def validate_action(action: str, allowed: list[str]) -> bool:
    """LLM 回的動作必須在 allowed 清單內。前後空白容錯。"""
    return action.strip() in {a.strip() for a in allowed}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_validate_action.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```powershell
git add doc_classifier/classifier.py doc_classifier/tests/test_validate_action.py
git commit -m "doc_classifier 新增 validate_action()：拒絕清單外動作"
```

---

## Task 7: log_utils — runs.log 寫入 + rotate (TDD)

**Files:**
- Create: `doc_classifier/tests/test_log_utils.py`
- Create: `doc_classifier/log_utils.py`

- [ ] **Step 1: 寫測試**

```python
"""log_utils 的單元測試:rotate 規則與 ISO 8601 時戳。"""
import re
from pathlib import Path
import pytest


def test_append_log_writes_iso_timestamp(tmp_path):
    from doc_classifier.log_utils import append_log
    log_path = tmp_path / "runs.log"
    append_log(log_path, "MW999 suggested=公告 confidence=高")
    text = log_path.read_text(encoding="utf-8")
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\s", text)
    assert "MW999 suggested=公告" in text


def test_append_log_multiple_lines(tmp_path):
    from doc_classifier.log_utils import append_log
    log_path = tmp_path / "runs.log"
    append_log(log_path, "first")
    append_log(log_path, "second")
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert "first" in lines[0]
    assert "second" in lines[1]


def test_rotate_when_log_exceeds_10mb(tmp_path):
    """超過 10MB 時 rotate,原檔變 .1。"""
    from doc_classifier.log_utils import append_log
    log_path = tmp_path / "runs.log"
    # 寫一個 >10MB 的 log
    log_path.write_text("x" * (10 * 1024 * 1024 + 100), encoding="utf-8")

    append_log(log_path, "new line after rotate")

    assert (tmp_path / "runs.log.1").exists()
    new_text = log_path.read_text(encoding="utf-8")
    assert "new line after rotate" in new_text
    assert "x" * 1000 not in new_text  # 新檔不該含舊內容


def test_rotate_chain_max_6_backups(tmp_path):
    """rotate 連鎖最多保留 .1 ~ .6。"""
    from doc_classifier.log_utils import append_log
    log_path = tmp_path / "runs.log"
    # 預備 .1 ~ .6 都已存在
    for i in range(1, 7):
        (tmp_path / f"runs.log.{i}").write_text(f"old{i}", encoding="utf-8")
    log_path.write_text("y" * (10 * 1024 * 1024 + 100), encoding="utf-8")

    append_log(log_path, "trigger rotate")

    # .1 應變成「上一次 .log 內容(y...)」, 原 .1 變 .2 ... 原 .6 被丟掉
    for i in range(1, 7):
        assert (tmp_path / f"runs.log.{i}").exists()
    assert not (tmp_path / "runs.log.7").exists()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_log_utils.py -v`
Expected: 4 個測試全失敗

- [ ] **Step 3: 寫 log_utils.py**

```python
"""log_utils.py — runs.log 結構化單行寫入 + 10MB rotate。

與 taipeion_login_selenium.py 的 _setup_stdout_logging() 設計不同:
那是 tee stdout (整個 process 的 print 都帶時戳);這裡是「結構化一行」
append 用 (不走 stdout 攔截),適合 runs.log 這種事件紀錄。
"""
import os
from datetime import datetime
from pathlib import Path

_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_MAX_BACKUPS = 6


def _rotate_if_needed(log_path: Path) -> None:
    """檔案 >10MB 時 rotate:.6→丟,.5→.6,...,.1→.2,.log→.1。"""
    if not log_path.is_file():
        return
    if log_path.stat().st_size < _MAX_BYTES:
        return
    # 從尾巴往前推
    for i in range(_MAX_BACKUPS - 1, 0, -1):
        src = log_path.with_name(f"{log_path.name}.{i}")
        dst = log_path.with_name(f"{log_path.name}.{i + 1}")
        if src.exists():
            os.replace(src, dst)
    os.replace(log_path, log_path.with_name(f"{log_path.name}.1"))


def append_log(log_path: Path, line: str) -> None:
    """寫一行 log。自動加 ISO 8601 時戳前綴 + 結尾換行 + rotate 檢查。"""
    log_path = Path(log_path)
    _rotate_if_needed(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{ts} {line}\n")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_log_utils.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```powershell
git add doc_classifier/log_utils.py doc_classifier/tests/test_log_utils.py
git commit -m "doc_classifier 新增 log_utils.append_log()：ISO 8601 時戳 + 10MB rotate（保留 .1~.6）"
```

---

## Task 8: classify_dir() 整合 (TDD with mocked LLM)

**Files:**
- Create: `doc_classifier/tests/test_classify_dir.py`
- Modify: `doc_classifier/classifier.py` (新增 classify_dir、_load_examples、_write_back)

- [ ] **Step 1: 寫測試**

```python
"""classify_dir() 整合測試:用 monkeypatch 注入假 LLM 回應跑全流程。"""
from pathlib import Path
import pytest


@pytest.fixture
def stage(tmp_path, monkeypatch):
    """準備一個 doc_classifier 的最小執行環境:
       - actions.yaml (含「公告」「存查」)
       - classifier.md (簡化版)
       - training_data/ (含 1 份已標 # action: 公告)
       - 目標 MW999 目錄(僅 1 份待分類)
    """
    # actions.yaml
    actions_yaml = tmp_path / "actions.yaml"
    actions_yaml.write_text("actions:\n  - 公告\n  - 存查\n", encoding="utf-8")
    # classifier.md
    spec_md = tmp_path / "classifier.md"
    spec_md.write_text("# 規格\n依範例分類。\n", encoding="utf-8")
    # training_data
    training = tmp_path / "training_data"
    training.mkdir()
    (training / "1140001總結.md").write_text(
        "# action: 公告\n主旨:資安宣導\n", encoding="utf-8"
    )
    # 目標
    mw999 = tmp_path / "document_download" / "MW999"
    mw999.mkdir(parents=True)
    target_md = mw999 / "1140999總結.md"
    target_md.write_text("主旨:校園資安宣導活動\n", encoding="utf-8")
    # runs.log
    runs_log = tmp_path / "runs.log"

    return {
        "mw_dir": mw999,
        "target_md": target_md,
        "actions_yaml": actions_yaml,
        "spec_md": spec_md,
        "training": training,
        "runs_log": runs_log,
    }


def test_classify_dir_writes_suggestion_back(stage, monkeypatch):
    from doc_classifier import classifier
    fake_response = (
        "# suggested_action: 公告 (信心:高)\n"
        "# cited_examples: 1140001\n"
        "與範例皆為資安主題。\n"
    )
    monkeypatch.setattr(classifier, "_call_llm", lambda prompt: fake_response)

    result = classifier.classify_dir(
        mw_dir=stage["mw_dir"],
        actions_yaml=stage["actions_yaml"],
        spec_md=stage["spec_md"],
        training_root=stage["training"],
        runs_log=stage["runs_log"],
    )

    assert result["status"] == "ok"
    written = stage["target_md"].read_text(encoding="utf-8")
    assert written.startswith("# suggested_action: 公告 (信心:高)")
    assert "# cited_examples: 1140001" in written
    assert "校園資安宣導活動" in written  # 原內容保留
    assert "公告" in stage["runs_log"].read_text(encoding="utf-8")


def test_classify_dir_skip_when_no_training_data(stage, monkeypatch, tmp_path):
    from doc_classifier import classifier
    # 清空 training_data
    for f in stage["training"].iterdir():
        f.unlink()
    monkeypatch.setattr(
        classifier, "_call_llm",
        lambda p: pytest.fail("training 空時不該打 LLM"),
    )

    result = classifier.classify_dir(
        mw_dir=stage["mw_dir"],
        actions_yaml=stage["actions_yaml"],
        spec_md=stage["spec_md"],
        training_root=stage["training"],
        runs_log=stage["runs_log"],
    )

    assert result["status"] == "skip"
    # 不寫回
    assert "suggested_action" not in stage["target_md"].read_text(encoding="utf-8")
    assert "SKIP" in stage["runs_log"].read_text(encoding="utf-8")


def test_classify_dir_skips_if_already_classified(stage, monkeypatch):
    from doc_classifier import classifier
    stage["target_md"].write_text(
        "# suggested_action: 存查 (信心:中)\n# cited_examples: \n之前跑過了\n主旨:x\n",
        encoding="utf-8",
    )
    called = {"v": False}

    def _no_call(p):
        called["v"] = True
        return ""

    monkeypatch.setattr(classifier, "_call_llm", _no_call)

    result = classifier.classify_dir(
        mw_dir=stage["mw_dir"],
        actions_yaml=stage["actions_yaml"],
        spec_md=stage["spec_md"],
        training_root=stage["training"],
        runs_log=stage["runs_log"],
        force=False,
    )

    assert result["status"] == "already_classified"
    assert called["v"] is False


def test_classify_dir_force_overwrites(stage, monkeypatch):
    from doc_classifier import classifier
    stage["target_md"].write_text(
        "# suggested_action: 存查 (信心:中)\n# cited_examples: \n舊建議\n主旨:x\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        classifier, "_call_llm",
        lambda p: (
            "# suggested_action: 公告 (信心:高)\n"
            "# cited_examples: 1140001\n"
            "新建議。\n"
        ),
    )

    result = classifier.classify_dir(
        mw_dir=stage["mw_dir"],
        actions_yaml=stage["actions_yaml"],
        spec_md=stage["spec_md"],
        training_root=stage["training"],
        runs_log=stage["runs_log"],
        force=True,
    )

    assert result["status"] == "ok"
    text = stage["target_md"].read_text(encoding="utf-8")
    assert text.startswith("# suggested_action: 公告 (信心:高)")
    # 舊「存查」建議行不該還在
    assert text.count("# suggested_action:") == 1


def test_classify_dir_rejects_action_not_in_yaml(stage, monkeypatch):
    from doc_classifier import classifier
    monkeypatch.setattr(
        classifier, "_call_llm",
        lambda p: (
            "# suggested_action: 自創動作 (信心:高)\n"
            "# cited_examples: \n"
            "亂講。\n"
        ),
    )

    result = classifier.classify_dir(
        mw_dir=stage["mw_dir"],
        actions_yaml=stage["actions_yaml"],
        spec_md=stage["spec_md"],
        training_root=stage["training"],
        runs_log=stage["runs_log"],
    )

    assert result["status"] == "rejected"
    assert "suggested_action" not in stage["target_md"].read_text(encoding="utf-8")
    assert "違反清單" in stage["runs_log"].read_text(encoding="utf-8")


def test_classify_dir_missing_summary_md_raises(stage, monkeypatch, tmp_path):
    from doc_classifier import classifier
    # 刪掉 target.md,讓目錄沒任何 *總結*.md
    stage["target_md"].unlink()

    with pytest.raises(FileNotFoundError):
        classifier.classify_dir(
            mw_dir=stage["mw_dir"],
            actions_yaml=stage["actions_yaml"],
            spec_md=stage["spec_md"],
            training_root=stage["training"],
            runs_log=stage["runs_log"],
        )


def test_classify_dir_llm_backend_unavailable(stage, monkeypatch):
    from doc_classifier import classifier
    monkeypatch.setattr(classifier, "_call_llm", lambda p: None)

    result = classifier.classify_dir(
        mw_dir=stage["mw_dir"],
        actions_yaml=stage["actions_yaml"],
        spec_md=stage["spec_md"],
        training_root=stage["training"],
        runs_log=stage["runs_log"],
    )

    assert result["status"] == "llm_unavailable"
    assert "LLM_UNAVAILABLE" in stage["runs_log"].read_text(encoding="utf-8")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_classify_dir.py -v`
Expected: 7 個測試全失敗

- [ ] **Step 3: 在 classifier.py 加 classify_dir 與輔助函式**

於 classifier.py 末尾(於既有函式之後)加:

```python
# ----- LLM backend(重用 summarize_doc.py 的兩個 backend) -----

def _call_llm(prompt_text: str) -> str | None:
    """依序試 claude_code → anthropic SDK。任一成功即回字串;皆失敗回 None。

    Backend 重用 summarize_doc.py(read-only import,不複製)。
    """
    from summarize_doc import _llm_summarize_claude_code, _llm_summarize_anthropic
    s = _llm_summarize_claude_code(prompt_text)
    if s:
        return s
    s = _llm_summarize_anthropic(prompt_text)
    if s:
        return s
    return None


# ----- 主流程 -----

_SUGGESTED_HEADER_RE = re.compile(r"^#\s*suggested_action:", re.MULTILINE)


def _load_examples(training_root: Path) -> dict[str, str]:
    """讀 training_root 下所有 *.md,strip artifacts 後回 {檔名: 內容}。"""
    out = {}
    for md in sorted(training_root.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        out[md.name] = strip_training_artifacts(text)
    return out


def _find_target_summary(mw_dir: Path) -> Path:
    """找該 MW 目錄裡的「總結.md」。找不到 raise FileNotFoundError。"""
    for md in sorted(mw_dir.glob("*總結*.md")):
        return md
    raise FileNotFoundError(
        f"{mw_dir} 下沒有 *總結*.md;summarize_doc 沒跑過?"
    )


def _write_back(target_md: Path, action: str, confidence: str,
                examples: list[str], reasoning: str) -> None:
    """把 LLM 結果寫回原 .md 開頭。先 strip 舊的 suggested_action / cited_examples 行
    (force 模式或重跑時用到),再 prepend 新建議三行 + 原內文。
    """
    original = target_md.read_text(encoding="utf-8")
    stripped = strip_training_artifacts(original).lstrip("\n")
    header = (
        f"# suggested_action: {action} (信心:{confidence})\n"
        f"# cited_examples: {', '.join(examples)}\n"
        f"{reasoning}\n\n"
    )
    target_md.write_text(header + stripped, encoding="utf-8")


def _already_classified(target_md: Path) -> bool:
    return bool(_SUGGESTED_HEADER_RE.search(target_md.read_text(encoding="utf-8")))


def classify_dir(
    mw_dir: Path,
    actions_yaml: Path = None,
    spec_md: Path = None,
    training_root: Path = None,
    runs_log: Path = None,
    force: bool = False,
) -> dict:
    """對單一 MW 目錄分類。回 {"status": ..., ...}。

    Status 可能值:
      ok / skip (training 空) / already_classified / rejected (動作違反清單)
      / llm_unavailable / error (LLM 格式錯)
    """
    from doc_classifier.log_utils import append_log

    mw_dir = Path(mw_dir)
    actions_yaml = Path(actions_yaml) if actions_yaml else ACTIONS_YAML
    spec_md = Path(spec_md) if spec_md else SPEC_MD
    training_root = Path(training_root) if training_root else (_BASE_DIR / "training_data")
    runs_log = Path(runs_log) if runs_log else (_BASE_DIR / "runs.log")

    target_md = _find_target_summary(mw_dir)  # may raise FileNotFoundError
    mw_name = mw_dir.name

    if not force and _already_classified(target_md):
        append_log(runs_log, f"{mw_name} SKIP reason=already_classified")
        return {"status": "already_classified", "target": str(target_md)}

    examples = _load_examples(training_root)
    if not examples:
        append_log(runs_log, f"{mw_name} SKIP reason=no_training_data")
        return {"status": "skip", "reason": "no_training_data"}

    actions = load_actions(actions_yaml)
    spec_text = spec_md.read_text(encoding="utf-8")
    target_text = strip_training_artifacts(
        target_md.read_text(encoding="utf-8")
    )

    prompt = build_prompt(spec_text, actions, examples, target_md.name, target_text)
    raw = _call_llm(prompt)
    if not raw:
        append_log(runs_log, f"{mw_name} LLM_UNAVAILABLE")
        return {"status": "llm_unavailable"}

    parsed = parse_response(raw)
    if parsed["status"] == "skip":
        append_log(runs_log, f"{mw_name} SKIP reason=llm_skip:{parsed.get('reason','')}")
        return {"status": "skip", "reason": parsed.get("reason", "")}
    if parsed["status"] == "error":
        append_log(runs_log, f"{mw_name} ERROR reason=parse_failed raw={parsed['raw']!r}")
        return {"status": "error", "raw": parsed["raw"]}

    if not validate_action(parsed["action"], actions):
        append_log(
            runs_log,
            f"{mw_name} REJECTED reason=違反清單 action={parsed['action']}",
        )
        return {"status": "rejected", "action": parsed["action"]}

    _write_back(target_md, parsed["action"], parsed["confidence"],
                parsed["examples"], parsed["reasoning"])
    append_log(
        runs_log,
        f"{mw_name} OK action={parsed['action']} confidence={parsed['confidence']} "
        f"examples={','.join(parsed['examples'])}",
    )
    return {"status": "ok", **parsed}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_classify_dir.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```powershell
git add doc_classifier/classifier.py doc_classifier/tests/test_classify_dir.py
git commit -m "doc_classifier 新增 classify_dir() 整合流程：sync→組 prompt→呼叫 LLM→驗證→寫回 .md+log"
```

---

## Task 9: CLI 入口 + sync 鏈式呼叫 (TDD)

**Files:**
- Create: `doc_classifier/tests/test_cli.py`
- Modify: `doc_classifier/classifier.py` (新增 main 與 argparse)

- [ ] **Step 1: 寫測試**

```python
"""CLI 入口測試:argparse 行為與 sync 觸發。"""
import subprocess
import sys
from pathlib import Path


def test_help_does_not_crash():
    result = subprocess.run(
        [sys.executable, "-m", "doc_classifier.classifier", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=Path(__file__).resolve().parents[2],  # repo root
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "用法" in result.stdout


def test_classify_runs_sync_before_classification(monkeypatch, tmp_path):
    """classify_dir 被呼叫前,sync 必須先跑過。"""
    from doc_classifier import classifier
    from doc_classifier import collect_training

    call_order = []
    monkeypatch.setattr(
        collect_training, "sync",
        lambda **kw: (call_order.append("sync"), {"added": 0, "updated": 0, "orphan_kept": 0, "skipped_no_action": 0})[1],
    )

    # mw_dir 隨便弄一個有 *總結*.md 的
    mw = tmp_path / "MW1"
    mw.mkdir()
    (mw / "x總結.md").write_text("# suggested_action: 公告 (信心:高)\n", encoding="utf-8")
    # actions yaml
    ay = tmp_path / "actions.yaml"
    ay.write_text("actions:\n  - 公告\n", encoding="utf-8")
    spec = tmp_path / "classifier.md"
    spec.write_text("# 規格\n", encoding="utf-8")
    training = tmp_path / "training_data"
    training.mkdir()

    classifier.run_one(
        mw_dir=mw,
        actions_yaml=ay,
        spec_md=spec,
        training_root=training,
        runs_log=tmp_path / "runs.log",
        force=False,
        do_sync=True,
    )
    assert "sync" in call_order
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_cli.py -v`
Expected: 2 個測試全失敗

- [ ] **Step 3: 在 classifier.py 加 run_one 與 main**

於 classifier.py 末尾加:

```python
def run_one(
    mw_dir: Path,
    actions_yaml: Path = None,
    spec_md: Path = None,
    training_root: Path = None,
    runs_log: Path = None,
    force: bool = False,
    do_sync: bool = True,
) -> dict:
    """對單一 MW 目錄跑一輪:先 sync 訓練資料、再 classify_dir。

    注意:import 採 module-level form (`from doc_classifier import collect_training`),
    這樣測試的 `monkeypatch.setattr(collect_training, "sync", ...)` 才攔得到。
    """
    if do_sync:
        from doc_classifier import collect_training
        collect_training.sync(training_root=training_root)
    return classify_dir(
        mw_dir=mw_dir,
        actions_yaml=actions_yaml,
        spec_md=spec_md,
        training_root=training_root,
        runs_log=runs_log,
        force=force,
    )


def main():
    import argparse
    p = argparse.ArgumentParser(
        description="doc_classifier — 對公文目錄做處置動作分類。",
    )
    p.add_argument(
        "mw_dir",
        nargs="?",
        help="MW 目錄路徑;留空則掃 ../document_download/MW*/。",
    )
    p.add_argument("--force", action="store_true",
                   help="目標 .md 已含 # suggested_action 也強制重跑。")
    p.add_argument("--no-sync", action="store_true",
                   help="跳過 collect_training.sync,只跑分類。")
    args = p.parse_args()

    do_sync = not args.no_sync

    if args.mw_dir:
        result = run_one(
            mw_dir=Path(args.mw_dir),
            force=args.force,
            do_sync=do_sync,
        )
        print(f"[classifier] {Path(args.mw_dir).name} → {result['status']}")
        return

    doc_download = _BASE_DIR.parent / "document_download"
    if not doc_download.is_dir():
        print(f"[ERROR] {doc_download} 不存在")
        sys.exit(1)
    mw_dirs = sorted(d for d in doc_download.iterdir()
                     if d.is_dir() and d.name.startswith("MW"))
    if not mw_dirs:
        print(f"[INFO] {doc_download} 內沒有 MW* 子目錄")
        return

    if do_sync:
        from doc_classifier import collect_training
        stats = collect_training.sync()
        print(f"[sync] added={stats['added']} updated={stats['updated']} "
              f"orphan_kept={stats['orphan_kept']}")

    for d in mw_dirs:
        result = classify_dir(mw_dir=d, force=args.force)
        print(f"[classifier] {d.name} → {result['status']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑測試確認通過**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/test_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: 手動 smoke test**

```powershell
C:\Python314\python.exe -m doc_classifier.classifier --help
```
Expected: 印出 usage 內容,exit 0

- [ ] **Step 6: Commit**

```powershell
git add doc_classifier/classifier.py doc_classifier/tests/test_cli.py
git commit -m "doc_classifier 加 CLI 入口：run_one()/main()，支援 --force 與 --no-sync flag，預設掃 document_download/MW*"
```

---

## Task 10: example_data + 全套件 smoke test

**Files:**
- Create: `doc_classifier/example_data/training/1140001_001A總結.claude-opus-4-7.md`
- Create: `doc_classifier/example_data/training/1140002_001A總結.claude-opus-4-7.md`
- Create: `doc_classifier/example_data/training/1140003_001A總結.claude-opus-4-7.md`
- Create: `doc_classifier/example_data/target/1140999_001A總結.claude-opus-4-7.md`

- [ ] **Step 1: 寫 example_data**

`doc_classifier/example_data/training/1140001_001A總結.claude-opus-4-7.md`:

```markdown
# 資安 宣導
# action: 公告

發文日期:中華民國 114 年 5 月 1 日
發文字號:北市教資字第 1140001A 號
主旨:函轉「校園資訊安全宣導週」活動辦法,請查照辦理。
```

`doc_classifier/example_data/training/1140002_001A總結.claude-opus-4-7.md`:

```markdown
# 校務行政
# action: 存查

發文日期:中華民國 114 年 5 月 3 日
發文字號:北市教校字第 1140002A 號
主旨:檢送 114 學年度校務行政會議紀錄一份,敬請查照。
```

`doc_classifier/example_data/training/1140003_001A總結.claude-opus-4-7.md`:

```markdown
# 汰換
# action: 轉發

發文日期:中華民國 114 年 5 月 5 日
發文字號:北市教設字第 1140003A 號
主旨:函轉「市立高中設備汰換補助計畫」,請相關組別配合辦理。
```

`doc_classifier/example_data/target/1140999_001A總結.claude-opus-4-7.md`:

```markdown
# 資安
發文日期:中華民國 114 年 5 月 20 日
發文字號:北市教資字第 1140999A 號
主旨:辦理校園資安週宣導活動,請查照。
```

- [ ] **Step 2: 跑全 pytest 確認沒崩**

Run: `C:\Python314\python.exe -m pytest doc_classifier/tests/ -v`
Expected: 全部 task 累積的測試都過 (~30+)

- [ ] **Step 3: Commit**

```powershell
git add doc_classifier/example_data
git commit -m "doc_classifier 補 example_data：3 份訓練範例 + 1 份待分類目標公文"
```

---

## Task 11: README + 與 main.py 鏈式呼叫的整合說明

**Files:**
- Create: `doc_classifier/README.md`
- Modify: `README.md` (專案主 README)

- [ ] **Step 1: 寫 doc_classifier/README.md**

```markdown
# doc_classifier

對公文做「處置動作」分類:依使用者累積標註的歷史範例,讓 LLM 推論新公文最合適的動作 (公告 / 存查 / 轉發 / ...)。

## 工作流程

1. **summarize_doc** 為每份新公文產出 `總結.md`
2. **使用者標註**:在 `總結.md` 頂部加一行 `# action: <動作>`
3. **collect_training.sync()** 把帶 `# action:` 的 .md 複製進 `training_data/` (永久家)
4. **classifier.classify_dir()** 對新公文組 prompt → LLM 推論 → 在原 .md 開頭加 `# suggested_action:`
5. 使用者採納建議 → 把 `# suggested_action:` 改成 `# action:` → 下次 sync 自動納入訓練資料

## 執行

```powershell
# 對單一公文目錄分類
C:\Python314\python.exe -m doc_classifier.classifier document_download\MW999

# 掃 document_download/MW*/(預設)
C:\Python314\python.exe -m doc_classifier.classifier

# 已分類過的也強制重跑
C:\Python314\python.exe -m doc_classifier.classifier --force

# 只跑 sync,不分類
C:\Python314\python.exe -m doc_classifier.collect_training
```

## 結構

```
doc_classifier/
├─ classifier.md         ← LLM 業務規格 (改規格只動這檔)
├─ actions.yaml          ← 動作清單 (隨時可加)
├─ classifier.py         ← 主入口 (classify_dir / run_one / main)
├─ collect_training.py   ← 訓練資料同步
├─ log_utils.py          ← runs.log 寫入 + rotate
├─ training_data/        ← (gitignored) 已標註資料永久家
├─ runs.log              ← (gitignored) 執行紀錄
├─ example_data/         ← 測試用假資料
└─ tests/                ← pytest
```

## 設計原則

- **規格全交 LLM 執行**:`classifier.md` 用 markdown 寫業務規則,LLM runtime 讀;Python 不重複規格條文。改規格只動 .md,程式不動。
- **LLM backend 重用**:`from summarize_doc import _llm_summarize_claude_code, _llm_summarize_anthropic`
- **訓練資料永久家**:`training_data/` 獨立於 `document_download/`,後者刪了也不影響
- **可獨立執行,亦可被主程式呼叫**:`from doc_classifier.classifier import classify_dir`

## 驗收標準

見 [spec §11](../docs/superpowers/specs/2026-05-24-doc-classifier-design.md#11-驗收標準-使用者肉眼驗收)。
```

- [ ] **Step 2: 在主 README 加一段**

讀 `README.md` 確認結構,在「專案結構」的程式碼區塊裡 `└─[4]─ document_system.py ...` 區段之後、`其他資源` 區段之前,加:

```
└─[5]─ doc_classifier/ — 公文處置動作分類器(獨立模組,可獨立執行)
        ├ collect_training.py — 把 # action: 已標公文同步進 training_data/
        ├ classifier.py        — 對新公文組 prompt → LLM → 寫回 # suggested_action:
        └ classifier.md        — LLM 業務規格(改規格只動此檔)
```

- [ ] **Step 3: Commit**

```powershell
git add doc_classifier/README.md README.md
git commit -m "doc_classifier README + 主 README 補分類器模組說明"
```

---

## Self-Review Notes (for the implementing engineer)

執行此 plan 前先看 spec 一次以建立全域觀:
[docs/superpowers/specs/2026-05-24-doc-classifier-design.md](../specs/2026-05-24-doc-classifier-design.md)

關鍵不變式:
- `classifier.py` 不嵌業務規則 — 動作清單從 `actions.yaml` 讀,信心分級/輸出格式從 `classifier.md` 讀
- 寫回 `總結.md` 時先 strip 舊的 `# suggested_action:` / `# cited_examples:` 行 (force / 重跑時用得到)
- `training_data/` 不該推 GitHub (見 .gitignore)
- LLM backend 走重用,不複製 `_llm_summarize_claude_code` 程式碼到本模組

跑全測試:
```powershell
C:\Python314\python.exe -m pytest doc_classifier/tests/ -v
```
