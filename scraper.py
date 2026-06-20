#!/usr/bin/env python3
"""
香港銀行定期存款利率自動爬蟲
混合方案：requests (快) + Playwright (JS 渲染)
"""
import json
import re
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = "data.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh-TW;q=0.9,zh;q=0.8,en;q=0.7",
}
MIN_RATE = 0.01
MAX_RATE = 8.0

# ── 用戶 click 嘅銀行連結（顯示用） ────────────────────────
BANK_DISPLAY_URLS = {
    "富融銀行": "https://www.fusionbank.com/deposit.html?lang=tc",
    "象象銀行": "https://www.elebank.com/zh-hk/hkprime.html",
    "匯立銀行": "https://www.welab.bank/zh/feature/gosave_2/",
    "Mox銀行": "https://mox.com/zh/promotions/time-deposit/",
    "理慧銀行": "https://www.livibank.com/zh_HK/features/livisave.html",
    "眾安銀行": "https://bank.za.group/hk/deposit",
    "滙豐銀行": "https://www.hsbc.com.hk/zh-hk/accounts/offers/deposits/",
    "恒生銀行": "https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html",
    "中銀香港": "https://www.bochk.com/tc/deposits/promotion/timedeposits.html",
    "渣打銀行": "https://www.sc.com/hk/zh/deposits/online-time-deposit/",
    "工銀亞洲": "https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html",
    "東亞銀行": "https://www.hkbea.com/html/tc/bea-personal-banking-supremegold-time-deposit.html",
    "星展銀行": "https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo",
    "中信銀行(國際)": "https://www.cncbinternational.com/personal/e-banking/inmotion/tc/offers/time_deposit/index.html",
    "富邦銀行": "https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html",
    "南洋商業銀行": "https://www.ncb.com.hk/nanyang_bank/popup1/deposit.html",
    "招商永隆銀行": "https://www.cmbwinglungbank.com/wlb_corporate/hk/personal/investments/financial-information/interest-rates/deposit-interest-rates.html",
    "上海商業銀行": "https://www.shacombank.com.hk/tch/personal/promotion/fix-rate.jsp",
    "大眾銀行": "https://www.publicbank.com.hk/tc/usefultools/rates/depositinterestrates",
    "交通銀行": "https://www.bankcomm.com.hk/",
    "建設銀行亞洲": "https://www.asia.ccb.com/hongkong_tc/personal/accounts/dep_rates.html?cmpid=HKTCDTPSACTMG-ULDEPOSITRATE",
    "大新銀行": "https://www.dahsing.com/html/tc/deposit/fixed_deposit/hkd_fixed_deposit.html",
}

EXCLUDE = [
    "回贈", "獎賞", "現金", "apr", "cash", "rebate", "reward",
    "信用卡", "簽賬", "消費", "最優惠利率", "prime",
    "結構", "structured", "掛鈎", "linked", "槓桿",
    "保險", "insurance", "基金", "fund",
    "手續費", "fee", "佣金", "commission",
]


# ── 輔助函數 ──────────────────────────────────────────────

def has_exclude_words(text):
    low = text.lower()
    return any(ex.lower() in low for ex in EXCLUDE)


def fetch_page(url):
    """抓取頁面，自動修正編碼"""
    r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    r.raise_for_status()
    if r.apparent_encoding and r.apparent_encoding.lower() in ("utf-8", "utf8"):
        r.encoding = "utf-8"
    elif r.encoding and r.encoding.lower() in ("iso-8859-1", "latin-1", "ascii"):
        r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator="\n")
    return soup, text


# ══════════════════════════════════════════════════════════
#   PART A: requests 爬蟲（唔需要 JS 嘅銀行）
# ══════════════════════════════════════════════════════════

def parse_generic(url, cap):
    """通用：搵 x.xx% 取最大值"""
    _, text = fetch_page(url)
    rates = []
    for line in text.split("\n"):
        if has_exclude_words(line):
            continue
        for m in re.findall(r"(\d+\.?\d*)\s*%", line):
            v = float(m)
            if MIN_RATE <= v <= cap:
                rates.append(v)
    if rates:
        return {c: max(rates) for c in ["HKD", "USD", "RMB"]}
    return None


def parse_bea(url, cap):
    """東亞銀行：4 個 table，0=HKD, 1=USD, 2=RMB"""
    soup, _ = fetch_page(url)
    tables = soup.find_all("table")
    currency_map = {0: "HKD", 1: "USD", 2: "RMB"}
    result = {}
    for idx, cur in currency_map.items():
        if idx >= len(tables):
            continue
        rates = []
        for cell in tables[idx].find_all(["td", "th"]):
            for m in re.findall(r"(\d+\.\d+)", cell.get_text(strip=True)):
                v = float(m)
                if MIN_RATE <= v <= cap:
                    rates.append(v)
        if rates:
            result[cur] = max(rates)
    return result or None


def parse_icbc(url, cap):
    """工銀亞洲：Table 1 有 港幣/美元/人民幣 行"""
    soup, _ = fetch_page(url)
    tables = soup.find_all("table")
    if len(tables) < 2:
        return None
    result = {}
    for row in tables[1].find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if not cells:
            continue
        cur = None
        if "港" in cells[0]:
            cur = "HKD"
        elif "美" in cells[0]:
            cur = "USD"
        elif "人民" in cells[0]:
            cur = "RMB"
        if cur:
            rates = []
            for t in cells[1:]:
                for m in re.findall(r"(\d+\.\d+)%?", t):
                    v = float(m)
                    if MIN_RATE <= v <= cap:
                        rates.append(v)
            if rates:
                best = max(rates)
                if cur not in result or best > result[cur]:
                    result[cur] = best
    return result or None


def parse_shacom(url, cap):
    """上海商業銀行：分區"""
    _, text = fetch_page(url)
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = None
    for line in text.split("\n"):
        s = line.strip()
        if "港幣" in s or "港元" in s:
            current = "HKD"
        elif "美元" in s or "美金" in s:
            current = "USD"
        elif "人民幣" in s:
            current = "RMB"
        elif "其他" in s or "外幣" in s or "澳" in s:
            current = None
        if current and not has_exclude_words(s):
            for m in re.findall(r"(\d+\.\d+)%?", s):
                v = float(m)
                if MIN_RATE <= v <= cap:
                    sections[current].append(v)
    return {c: max(r) for c, r in sections.items() if r} or None


def parse_publicbank(url, cap):
    """大眾銀行：x.xxxx% 格式，第一個利率表=HKD，之後按標記切換"""
    _, text = fetch_page(url)
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = "HKD"
    found_first_rate = False
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        # 只喺見到利率之後先做貨幣切換（避免 menu 文字干擾）
        has_rate = bool(re.search(r"\d+\.\d+%", s))
        if has_rate:
            found_first_rate = True
        if found_first_rate:
            low = s.lower()
            # 真正嘅貨幣分區標題
            if re.match(r"^(港幣|港元|hkd)", low):
                current = "HKD"
            elif re.match(r"^(美元|usd)", low):
                current = "USD"
            elif re.match(r"^(人民幣|rmb|cny)", low):
                current = "RMB"
        if current and not has_exclude_words(s):
            for m in re.findall(r"(\d+\.\d+)%", s):
                v = float(m)
                if MIN_RATE <= v <= cap:
                    sections[current].append(v)
    return {c: max(r) for c, r in sections.items() if r} or None


def parse_hsbc(url, cap):
    """滙豐銀行：過濾結構性產品"""
    _, text = fetch_page(url)
    hsbc_cap = min(cap, 4.0)
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = "HKD"
    for line in text.split("\n"):
        s = line.strip()
        if has_exclude_words(s):
            continue
        if "港幣" in s or "港元" in s:
            current = "HKD"
        elif "美元" in s:
            current = "USD"
        elif "人民幣" in s:
            current = "RMB"
        if current:
            for m in re.findall(r"(\d+\.?\d*)\s*%", s):
                v = float(m)
                if MIN_RATE <= v <= hsbc_cap:
                    sections[current].append(v)
    return {c: max(r) for c, r in sections.items() if r} or None


def parse_bochk(url, cap):
    """中銀香港：過濾結構性存款"""
    _, text = fetch_page(url)
    bochk_cap = min(cap, 4.0)
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = "HKD"
    skip = False
    for line in text.split("\n"):
        s = line.strip()
        if "結構" in s or "掛鈎" in s:
            skip = True
            continue
        if "定期存款" in s and "結構" not in s:
            skip = False
        if skip or has_exclude_words(s):
            continue
        if "港幣" in s or "港元" in s:
            current = "HKD"
        elif "美元" in s:
            current = "USD"
        elif "人民幣" in s:
            current = "RMB"
        if current:
            for m in re.findall(r"(\d+\.?\d*)\s*%", s):
                v = float(m)
                if MIN_RATE <= v <= bochk_cap:
                    sections[current].append(v)
    return {c: max(r) for c, r in sections.items() if r} or None


def parse_ccb(url, cap):
    """建設銀行亞洲"""
    _, text = fetch_page(url)
    ccb_cap = min(cap, 4.0)
    rates = []
    for line in text.split("\n"):
        if has_exclude_words(line):
            continue
        for m in re.findall(r"(\d+\.?\d*)\s*%", line):
            v = float(m)
            if MIN_RATE <= v <= ccb_cap:
                rates.append(v)
    if rates:
        return {c: max(rates) for c in ["HKD", "USD", "RMB"]}
    return None


def parse_dbs(url, cap):
    """星展銀行"""
    _, text = fetch_page(url)
    dbs_cap = min(cap, 3.5)
    rates = []
    for line in text.split("\n"):
        if has_exclude_words(line):
            continue
        for m in re.findall(r"(\d+\.?\d*)\s*%", line):
            v = float(m)
            if MIN_RATE <= v <= dbs_cap:
                rates.append(v)
    if rates:
        return {c: max(rates) for c in ["HKD", "USD", "RMB"]}
    return None


def parse_dahsing(cap):
    """大新銀行：HKD/USD/RMB 各有獨立 URL"""
    urls = {
        "HKD": "https://www.dahsing.com/html/tc/deposit/fixed_deposit/hkd_fixed_deposit.html",
        "USD": "https://www.dahsing.com/html/tc/deposit/fixed_deposit/usd_fixed_deposit.html",
        "RMB": "https://www.dahsing.com/html/tc/deposit/fixed_deposit/rmb_fixed_deposit.html",
    }
    result = {}
    for cur, url in urls.items():
        try:
            _, text = fetch_page(url)
            rates = []
            for line in text.split("\n"):
                if has_exclude_words(line):
                    continue
                for m in re.findall(r"(\d+\.?\d*)\s*%", line):
                    v = float(m)
                    if MIN_RATE <= v <= cap:
                        rates.append(v)
            if rates:
                result[cur] = max(rates)
        except Exception as e:
            print(f"    大新銀行 {cur}: {e}")
    return result or None


# requests 爬蟲配置
REQUESTS_CONFIGS = [
    {"bank": "Mox銀行", "url": "https://mox.com/zh/promotions/time-deposit/", "cap": 5.0},
    {"bank": "眾安銀行", "url": "https://bank.za.group/hk/deposit", "cap": 2.0},
    {"bank": "象象銀行", "url": "https://www.elebank.com/zh-hk/hkprime.html", "cap": 2.0},
    {"bank": "匯立銀行", "url": "https://www.welab.bank/zh/feature/gosave_2/", "cap": 5.0},
    {"bank": "東亞銀行", "parser": "bea", "url": "https://www.hkbea.com/html/tc/bea-personal-banking-supremegold-time-deposit.html", "cap": 5.0},
    {"bank": "工銀亞洲", "parser": "icbc", "url": "https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html", "cap": 5.0},
    {"bank": "上海商業銀行", "parser": "shacom", "url": "https://www.shacombank.com.hk/tch/personal/promotion/fix-rate.jsp", "cap": 5.0},
    {"bank": "大眾銀行", "parser": "publicbank", "url": "https://www.publicbank.com.hk/tc/usefultools/rates/depositinterestrates", "cap": 5.0},
    {"bank": "渣打銀行", "url": "https://www.sc.com/hk/zh/deposits/online-time-deposit/", "cap": 5.0},
    {"bank": "大新銀行", "parser": "dahsing", "cap": 5.0},
    {"bank": "建設銀行亞洲", "parser": "ccb", "url": "https://www.asia.ccb.com/hongkong_tc/personal/accounts/dep_rates.html?cmpid=HKTCDTPSACTMG-ULDEPOSITRATE", "cap": 5.0},
    {"bank": "滙豐銀行", "parser": "hsbc", "url": "https://www.hsbc.com.hk/zh-hk/accounts/offers/deposits/", "cap": 5.0},
    {"bank": "中銀香港", "parser": "bochk", "url": "https://www.bochk.com/tc/deposits/promotion/timedeposits.html", "cap": 3.5},
    {"bank": "星展銀行", "parser": "dbs", "url": "https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo", "cap": 3.5},
]

PARSER_MAP = {
    "bea": parse_bea, "icbc": parse_icbc, "shacom": parse_shacom,
    "publicbank": parse_publicbank, "hsbc": parse_hsbc,
    "bochk": parse_bochk, "ccb": parse_ccb, "dbs": parse_dbs,
}


def scrape_with_requests(cfg):
    parser_name = cfg.get("parser")
    url = cfg.get("url", "")
    cap = cfg.get("cap", MAX_RATE)
    if parser_name == "dahsing":
        return parse_dahsing(cap)
    if parser_name in PARSER_MAP:
        return PARSER_MAP[parser_name](url, cap)
    return parse_generic(url, cap)


# ══════════════════════════════════════════════════════════
#   PART B: Playwright 爬蟲（需要 JS 渲染嘅銀行）
# ══════════════════════════════════════════════════════════

def scrape_playwright_banks():
    """用 Playwright 爬需要 JS 渲染嘅銀行"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ playwright 未安裝，跳過 JS 銀行")
        return {}

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── 恒生銀行 ──
        try:
            page = browser.new_page()
            page.goto("https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html",
                       timeout=60000, wait_until="domcontentloaded")
            # 等利率表出現（搵包含 "2." 或 "3." 嘅文字）
            try:
                page.wait_for_selector("text=/\\d+\\.\\d+/", timeout=15000)
            except:
                pass
            page.wait_for_timeout(3000)
            text = page.evaluate("() => document.body.innerText")
            page.close()

            sections = {"HKD": [], "USD": [], "RMB": []}
            current = None
            for line in text.split("\n"):
                s = line.strip()
                if "港元" in s:
                    current = "HKD"
                elif "美元" in s:
                    current = "USD"
                elif "人民幣" in s:
                    current = "RMB"
                elif "英鎊" in s or "澳元" in s or "加元" in s or "紐" in s:
                    current = None
                if current:
                    for m in re.findall(r"(\d+\.\d+)", s):
                        v = float(m)
                        if MIN_RATE <= v <= 5.0:
                            sections[current].append(v)
            r = {c: max(vs) for c, vs in sections.items() if vs}
            if r:
                results["恒生銀行"] = r
                print(f"  ✅ 恒生銀行: {r}")
            else:
                print(f"  ⚠️ 恒生銀行: 冇爬到利率")
        except Exception as e:
            print(f"  ❌ 恒生銀行: {e}")

        # ── 理慧銀行 ──
        try:
            page = browser.new_page()
            page.goto("https://www.livibank.com/zh_HK/features/livisave.html",
                       timeout=30000, wait_until="networkidle")
            text = page.inner_text("body")
            page.close()

            sections = {"HKD": [], "USD": []}
            current = None
            for line in text.split("\n"):
                s = line.strip()
                if "HKD" in s or "港幣" in s or "港元" in s:
                    current = "HKD"
                elif "USD" in s or "美元" in s:
                    current = "USD"
                if current and not has_exclude_words(s):
                    for m in re.findall(r"(\d+\.\d+)%?", s):
                        v = float(m)
                        if MIN_RATE <= v <= 5.0:
                            sections[current].append(v)
            r = {c: max(vs) for c, vs in sections.items() if vs}
            if r:
                results["理慧銀行"] = r
                print(f"  ✅ 理慧銀行: {r}")
            else:
                print(f"  ⚠️ 理慧銀行: 冇爬到利率")
        except Exception as e:
            print(f"  ❌ 理慧銀行: {e}")

        # ── 富邦銀行 ──
        try:
            page = browser.new_page()
            page.goto("https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html",
                       timeout=30000, wait_until="networkidle")
            text = page.inner_text("body")
            page.close()

            fubon_cap = 4.5  # 富邦有大額推廣，cap 唔好太低
            sections = {"HKD": [], "USD": [], "RMB": []}
            current = None
            for line in text.split("\n"):
                s = line.strip()
                if "港元" in s or ("港幣" in s and "存款" not in s):
                    current = "HKD"
                elif "美元" in s or "美金" in s:
                    current = "USD"
                elif "人民幣" in s:
                    current = "RMB"
                elif "澳元" in s or "澳幣" in s:
                    current = None
                if current and not has_exclude_words(s):
                    for m in re.findall(r"(\d+\.?\d*)\s*%?", s):
                        v = float(m)
                        if MIN_RATE <= v <= fubon_cap:
                            sections[current].append(v)
            r = {c: max(vs) for c, vs in sections.items() if vs}
            if r:
                results["富邦銀行"] = r
                print(f"  ✅ 富邦銀行: {r}")
            else:
                print(f"  ⚠️ 富邦銀行: 冇爬到利率")
        except Exception as e:
            print(f"  ❌ 富邦銀行: {e}")

        # ── 招商永隆銀行（iframe） ──
        try:
            page = browser.new_page()
            page.goto("https://www.cmbwinglungbank.com/wlb_corporate/hk/personal/investments/financial-information/interest-rates/deposit-interest-rates.html",
                       timeout=30000, wait_until="networkidle")
            frames = page.frames
            text = ""
            for frame in frames:
                try:
                    t = frame.inner_text("body", timeout=5000)
                    if t and len(t) > text.__len__():
                        text = t
                except:
                    pass
            page.close()

            sections = {"HKD": [], "USD": [], "RMB": []}
            current = None
            for line in text.split("\n"):
                s = line.strip()
                # 用 HKD/USD/CNY 做分區（iframe 用呢啲標識）
                if "HKD" in s and ("以下" in s or "以上" in s or "," in s):
                    current = "HKD"
                elif re.match(r".*USD.*\d", s):
                    current = "USD"
                elif re.match(r".*CNY.*\d", s) or re.match(r".*RMB.*\d", s):
                    current = "RMB"
                elif re.match(r".*(AUD|CAD|GBP|NZD|EUR|JPY|SGD|THB).*\d", s):
                    current = None  # skip other currencies

                if current and "定期存款年利率" not in s:
                    for m in re.findall(r"(\d+\.\d+)", s):
                        v = float(m)
                        if MIN_RATE <= v <= 5.0:
                            sections[current].append(v)
            r = {c: max(vs) for c, vs in sections.items() if vs}
            if r:
                results["招商永隆銀行"] = r
                print(f"  ✅ 招商永隆銀行: {r}")
            else:
                print(f"  ⚠️ 招商永隆銀行: 冇爬到利率")
        except Exception as e:
            print(f"  ❌ 招商永隆銀行: {e}")

        # ── 南洋商業銀行 ──
        # popup 頁面冇利率數字，暫時跳過
        print(f"  ⏭️ 南洋商業銀行: 頁面無利率數字，保留現有數據")

        # ── 中信銀行(國際) ──
        # CDN 反爬（Akamai），Playwright 都被攔截
        print(f"  ⏭️ 中信銀行(國際): CDN 反爬，保留現有數據")

        # ── 富融銀行 ──
        # SPA 頁面完全冇內容
        print(f"  ⏭️ 富融銀行: SPA 頁面無法爬取，保留現有數據")

        browser.close()

    return results


# ══════════════════════════════════════════════════════════
#   主程式
# ══════════════════════════════════════════════════════════

def main():
    print(f"Scraper started {datetime.now()}")
    print(f"{'='*50}")

    # 讀取現有 data
    existing = {}
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f).get("rates", {})
    if not existing:
        existing = {"HKD": [], "USD": [], "RMB": []}
    for cur in ["HKD", "USD", "RMB"]:
        if cur not in existing:
            existing[cur] = []

    scraped = {}

    # Part A: requests 爬蟲
    print("\n── Part A: requests 爬蟲 ──")
    for cfg in REQUESTS_CONFIGS:
        try:
            result = scrape_with_requests(cfg)
            if result:
                scraped[cfg["bank"]] = result
                print(f"  ✅ {cfg['bank']}: {result}")
            else:
                print(f"  ⚠️ {cfg['bank']}: 冇爬到利率")
        except Exception as e:
            print(f"  ❌ {cfg['bank']}: {e}")

    # Part B: Playwright 爬蟲
    print("\n── Part B: Playwright 爬蟲 (JS 渲染) ──")
    pw_results = scrape_playwright_banks()
    scraped.update(pw_results)

    # 更新現有數據
    print(f"\n{'='*50}")
    updated_count = 0
    for bank_name, cur_rates in scraped.items():
        for cur, banks in existing.items():
            if cur not in cur_rates:
                continue
            for bank in banks:
                if bank["bank"] == bank_name:
                    old_rate = bank.get("bestRate")
                    new_rate = cur_rates[cur]
                    bank["bestRate"] = new_rate
                    bank["note"] = "auto-scraped"
                    if old_rate != new_rate:
                        updated_count += 1
                    break

    # 確保顯示 URL 正確
    for cur, banks in existing.items():
        for bank in banks:
            name = bank.get("bank", "")
            if name in BANK_DISPLAY_URLS:
                bank["url"] = BANK_DISPLAY_URLS[name]

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rates": existing,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_banks = len(REQUESTS_CONFIGS) + 4  # +4 for playwright banks (恒生/理慧/富邦/招商永隆)
    print(f"爬取完成：{len(scraped)}/{total_banks} 間銀行成功")
    print(f"利率更新：{updated_count} 個變動")
    print(f"未能爬取：南洋商業銀行、中信銀行(國際)、富融銀行（保留現有數據）")
    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
