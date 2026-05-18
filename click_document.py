"""
click_document.py
TAIPEION 入口網儀表板 — 檢查「公文(學校)」方塊上方的待辦數字，依結果決定動作。

設計：
  - 若待辦數 = 0：停在儀表板，程式結束（不點方塊）
  - 若待辦數 > 0：點方塊 → 進入公文系統 → 呼叫 click_document() 做點選之後的後續工作

呼叫方式：
  1) 從 main.py 自然人憑證登入成功後串接：
       from click_document import click_document_card
       click_document_card(driver)   # 用既有 Selenium driver 繼續操作
  2) 單獨執行：
       C:\\Python314\\python.exe click_document.py
       → 會先呼叫 login_taipeion_selenium() 重新登入拿到 driver，再判讀數字
"""

import re
import sys
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

sys.stdout.reconfigure(encoding='utf-8')

# 「公文(學校)」方塊。實測該方塊由 div 包標籤文字 + 數字計數構成，整塊都可點。
DOCUMENT_XPATHS = [
    "//a[contains(normalize-space(), '公文(學校)')]",
    "//*[normalize-space()='公文(學校)']/ancestor::a[1]",
    "//*[normalize-space()='公文(學校)']/ancestor::*[@role='link' or @role='button'][1]",
    "//*[normalize-space()='公文(學校)']/ancestor::div[contains(@class, 'card') or contains(@class, 'tile') or contains(@class, 'block')][1]",
    "//*[normalize-space()='公文(學校)']",
    "//*[contains(normalize-space(), '公文(學校)')]",
]

# 「公文(學校)」label 元素本身（用來定位後再從附近找數字）。
DOCUMENT_LABEL_XPATH = "//*[normalize-space()='公文(學校)']"


def _ensure_driver(driver):
    """若 driver=None，自動呼叫 login_taipeion_selenium 重新登入取得 driver。
    回傳 driver 或 None（登入失敗）。"""
    if driver is not None:
        return driver
    print("[click_document] 未提供 driver，先呼叫 login_taipeion_selenium 取得登入 session...")
    from taipeion_login_selenium import login_taipeion_selenium
    driver = login_taipeion_selenium(return_driver=True)
    if driver is None:
        print("[ERROR] 登入失敗，無法處理公文")
    return driver


def _get_document_count(driver, timeout=10):
    """讀『公文(學校)』方塊上方的待辦數字。
    回傳：
        int >= 0 → 判讀成功
        -1       → 找不到 label 或無法 parse 數字（保守視為「不確定」）
    """
    wait = WebDriverWait(driver, timeout)
    try:
        label_el = wait.until(EC.presence_of_element_located((By.XPATH, DOCUMENT_LABEL_XPATH)))
    except TimeoutException:
        print("[WARN] 找不到『公文(學校)』label，無法判讀數字")
        return -1

    # 數字可能在：label 的父容器內的兄弟節點、祖父容器內、或同 card 內某個 span/div。
    # 由近到遠掃描，找第一個純數字（容許千分位逗號）的可見元素。
    relative_xpaths = [
        "./parent::*/*[self::span or self::div or self::strong or self::b or self::p]",
        "./parent::*/parent::*//*[self::span or self::div or self::strong or self::b or self::p]",
        "./ancestor::*[self::a or self::div][1]//*[self::span or self::div or self::strong or self::b or self::p]",
    ]
    seen_ids = set()
    for rel_xp in relative_xpaths:
        try:
            els = label_el.find_elements(By.XPATH, rel_xp)
        except Exception:
            continue
        for el in els:
            try:
                # 避開把 label 本身當數字
                el_id = el.id if hasattr(el, "id") else id(el)
                if el_id in seen_ids:
                    continue
                seen_ids.add(el_id)
                if not el.is_displayed():
                    continue
                txt = (el.text or "").strip()
                if not txt or txt == "公文(學校)":
                    continue
                m = re.fullmatch(r"[\d,]+", txt)
                if m:
                    n = int(txt.replace(",", ""))
                    print(f"      OK：讀到公文(學校) 待辦數 = {n}（來源文字「{txt}」）")
                    return n
            except Exception:
                continue

    print("[WARN] 找到『公文(學校)』label 但附近沒有純數字元素，無法判讀")
    return -1


def _click_document_card(driver, timeout=8):
    """點『公文(學校)』方塊（純點擊動作，不檢查數字）。回傳是否點到。"""
    wait = WebDriverWait(driver, timeout)
    for xp in DOCUMENT_XPATHS:
        try:
            el = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
            if not el.is_displayed():
                continue
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", el)
            print(f"      OK：點到 公文(學校) 方塊（XPath: {xp}）")
            return True
        except TimeoutException:
            continue
        except Exception as e:
            print(f"      x  公文(學校) 方塊點擊例外：{type(e).__name__}: {e}")
            continue
    print("[ERROR] 公文(學校) 方塊 全部 XPath 都失敗")
    return False


def click_document(driver):
    """『公文(學校)』方塊點選之後的後續工作。

    目前：等公文系統載入、若開新分頁切過去、印 URL/標題。
    未來：在此函式內擴充後續流程（瀏覽未讀公文、批次處理等）。
    """
    # 點完後系統可能跳新分頁或同分頁導向；給 3 秒緩衝再判讀狀態
    time.sleep(3)
    try:
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            print("[click_document] 已切換至新分頁")
        print(f"[click_document] 當前 URL：{driver.current_url}")
        print(f"[click_document] 當前標題：{driver.title}")
    except Exception as e:
        print(f"[click_document] 讀狀態失敗：{e}")

    # TODO: 點選之後的後續工作在此擴充
    print("[完成] 公文後續工作流程結束。")
    return True


def click_document_card(driver=None):
    """主入口：檢查『公文(學校)』方塊上方的待辦數字。
      - 數字 = 0：停在儀表板，程式結束（return False，不點方塊也不呼叫 click_document）
      - 數字 > 0：點方塊 → 呼叫 click_document() 做後續工作
      - 數字無法判讀（-1）：保守不點，請使用者手動處理

    參數：
        driver: 既有 Selenium WebDriver；若為 None 則自動呼叫 login_taipeion_selenium 重新登入。
    回傳：
        True 表示已點方塊並進入後續工作；False 表示沒點（待辦 0 或判讀失敗或點擊失敗）。
    """
    driver = _ensure_driver(driver)
    if driver is None:
        return False

    print("[click_document_card] 等儀表板載入後讀『公文(學校)』待辦數...")
    count = _get_document_count(driver)

    if count == 0:
        print("[click_document_card] 公文(學校) 待辦數 = 0，無待辦公文，停在儀表板，程式結束。")
        return False
    if count < 0:
        print("[click_document_card] 無法判讀公文(學校) 待辦數，保守不點，請手動處理。")
        return False

    print(f"[click_document_card] 公文(學校) 待辦數 = {count}，點方塊進入公文系統...")
    if not _click_document_card(driver):
        print("[click_document_card] 點擊失敗 — 列印目前頁面狀態以利除錯：")
        try:
            print(f"      URL：{driver.current_url}")
            print(f"      標題：{driver.title}")
        except Exception:
            pass
        return False

    # 點選之後才呼叫 click_document 做後續工作
    return click_document(driver)


if __name__ == "__main__":
    click_document_card()
