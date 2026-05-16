# sssh-automation

臺北市松山高中資訊組自動化工具集。

## 專案結構

```
main.py           # 主程式入口，顯示功能選單
taipeion_login.py # 功能：臺北市單一帳號認證平台 — 自然人憑證登入
browser_utils.py  # 共用工具庫：Chrome 視窗操作、截圖、像素偵測、滑鼠點擊
```

## 環境需求

- Windows 10
- Python 3.14（路徑：`C:\Python314\`）
- Google Chrome（路徑：`C:\Program Files\Google\Chrome\Application\chrome.exe`）
- 自然人憑證讀卡機（執行登入功能時需插入卡片）

### 安裝相依套件

```powershell
C:\Python314\python.exe -m pip install pillow pyautogui
```

## 執行方式

```powershell
C:\Python314\python.exe main.py
```

啟動後顯示功能選單，1 秒無操作自動執行功能 1。

## 功能說明

### 1. 臺北市單一帳號認證平台 — 自然人憑證登入

自動完成以下步驟：
1. 以 Chrome Profile 2 開啟 `https://login.gov.taipei/login.php`
2. 偵測並點選「自然人憑證」分頁（透過青綠色底線像素識別）
3. 偵測並點選「登入」按鈕（透過青綠色按鈕像素識別）

> 點擊位置採用顏色像素群集偵測，不依賴固定座標，可適應不同視窗大小。

## 新增功能

在 `main.py` 的 `FEATURES` 清單加入一列即可：

```python
FEATURES = [
    ("臺北市單一帳號認證平台 — 自然人憑證登入", login_taipeion),
    ("新功能名稱", 新功能函式),   # ← 加在這裡
]
```
