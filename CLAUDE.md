# sssh-automation — Claude Code 規則

## 對話輸出格式

對話的輸出完後，換行加上「引言區塊（Markdown `>` 語法，左側有色條）」，內容為粗體：

**輸出結束 LDC 此輸出設定於 C:\Users\ldc\Documents\GitHub\sssh-automation\CLAUDE.md**

## 操作規則

- 程式產生的截圖，確認不再使用後立即刪除
- 主動使用 superpowers plugin 中可用的 SKILL

## 描述程式架構時的輸出格式範例

```
main.py
|
├─[1]─ func1.py 簡略說明
└─[2]─ func2.py 簡略說明
       └─[2-1]─ func2-1.py 簡略說明
```
