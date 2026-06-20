#!/usr/bin/env python3
"""
香港銀行定期存款利率自動爬蟲
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

def extract_rates_from_text(text, cap):
    """從一段文字中提取所有合理利率數字"""
    rates = []
    for m in re.findall(r"(\d+\.?\d*)\s*%?", text):
        try:
            v = float(m)
            if MIN_RATE <= v <= cap:
                rates.append(v)
        except ValueError:
            pass
    return rates


def has_exclude_words(text):
    """檢查文字是否包含排除關鍵字"""
    low = text.lower()
    return any(ex.lower() in low for ex in EXCLUDE)


def fetch_page(url):
    """抓取頁面並返回 (soup, text)，自動修正編碼"""
    r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    r.raise_for_status()
    # 好多銀行網站 encoding 偵測錯誤，強制用 UTF-8
    if r.apparent_encoding and r.apparent_encoding.lower() in ("utf-8", "utf8"):
        r.encoding = "utf-8"
    elif r.encoding and r.encoding.lower() in ("iso-8859-1", "latin-1", "ascii"):
        r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator="\n")
    return soup, text


# ── 通用解析器 ──────────────────────────────────────────────

def parse_generic(url, cap):
    """通用：搵所有 x.xx% 格式嘅數字，過濾後取最大值，三幣相同"""
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
        best = max(rates)
        return {c: best for c in ["HKD", "USD", "RMB"]}
    return None


# ── 銀行專用解析器 ──────────────────────────────────────────

def parse_bea(url, cap):
    """東亞銀行：4 個 table，Table 0=HKD, 1=USD, 2=RMB, 3=其他外幣
       利率格式：'2.45 / 2.35'（新資金 / 現有資金），取第一個"""
    soup, _ = fetch_page(url)
    tables = soup.find_all("table")
    currency_map = {0: "HKD", 1: "USD", 2: "RMB"}
    result = {}

    for idx, cur in currency_map.items():
        if idx >= len(tables):
            continue
        table = tables[idx]
        rates = []
        for cell in table.find_all(["td", "th"]):
            text = cell.get_text(strip=True)
            # 格式如 "2.45 / 2.35"，取第一個（新資金利率）
            for m in re.findall(r"(\d+\.\d+)", text):
                v = float(m)
                if MIN_RATE <= v <= cap:
                    rates.append(v)
        if rates:
            result[cur] = max(rates)

    return result if result else None


def parse_icbc(url, cap):
    """工銀亞洲：Table 1 有完整利率表
       Row 0=header, Row 1=港幣, Row 2=美元, Row 3-4=人民幣, etc."""
    soup, _ = fetch_page(url)
    tables = soup.find_all("table")
    if len(tables) < 2:
        return None

    table = tables[1]  # 第二個 table 有標準利率
    rows = table.find_all("tr")
    result = {}

    for row in rows:
        cells = row.find_all(["td", "th"])
        cell_texts = [c.get_text(strip=True) for c in cells]
        if not cell_texts:
            continue

        first_cell = cell_texts[0]
        cur = None
        if "港" in first_cell:
            cur = "HKD"
        elif "美" in first_cell:
            cur = "USD"
        elif "人民" in first_cell:
            cur = "RMB"

        if cur:
            rates = []
            for text in cell_texts[1:]:
                for m in re.findall(r"(\d+\.\d+)%?", text):
                    v = float(m)
                    if MIN_RATE <= v <= cap:
                        rates.append(v)
            if rates:
                best = max(rates)
                # 保留最高利率（人民幣可能有多行）
                if cur not in result or best > result[cur]:
                    result[cur] = best

    return result if result else None


def parse_shacom(url, cap):
    """上海商業銀行：頁面有分區，按文字內容判斷貨幣"""
    _, text = fetch_page(url)
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = None

    for line in text.split("\n"):
        line_s = line.strip()
        if not line_s:
            continue
        # 用 encoded 嘅中文同英文判斷
        if "港幣" in line_s or "港元" in line_s or "HKD" in line_s.upper():
            current = "HKD"
        elif "美元" in line_s or "美金" in line_s or "USD" in line_s.upper():
            current = "USD"
        elif "人民幣" in line_s or "RMB" in line_s.upper() or "CNY" in line_s.upper():
            current = "RMB"
        elif "其他" in line_s or "外幣" in line_s or "澳" in line_s:
            current = None  # skip

        if current and not has_exclude_words(line_s):
            for m in re.findall(r"(\d+\.\d+)%?", line_s):
                v = float(m)
                if MIN_RATE <= v <= cap:
                    sections[current].append(v)

    result = {}
    for cur, rates in sections.items():
        if rates:
            result[cur] = max(rates)
    return result if result else None


def parse_publicbank(url, cap):
    """大眾銀行：利率用 x.xxxx% 格式，有 HKD/USD/RMB 分區"""
    soup, text = fetch_page(url)
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = "HKD"

    for line in text.split("\n"):
        line_s = line.strip()
        if not line_s:
            continue

        low = line_s.lower()
        if "hkd" in low or "港幣" in line_s or "港元" in line_s:
            current = "HKD"
        elif "usd" in low or "美元" in line_s or "美金" in line_s:
            current = "USD"
        elif "rmb" in low or "cny" in low or "人民幣" in line_s:
            current = "RMB"
        elif "其他" in line_s:
            current = None

        if current and not has_exclude_words(line_s):
            for m in re.findall(r"(\d+\.\d+)%", line_s):
                v = float(m)
                if MIN_RATE <= v <= cap:
                    sections[current].append(v)

    result = {}
    for cur, rates in sections.items():
        if rates:
            result[cur] = max(rates)
    return result if result else None


def parse_hsbc(url, cap):
    """滙豐銀行：頁面超大，有好多結構性產品（10-15%），只取 ≤4% 嘅定存利率"""
    _, text = fetch_page(url)
    hsbc_cap = min(cap, 4.0)  # HSBC 定存通常唔超過 4%
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = "HKD"

    for line in text.split("\n"):
        line_s = line.strip()
        if not line_s:
            continue
        if has_exclude_words(line_s):
            continue

        if "港幣" in line_s or "港元" in line_s:
            current = "HKD"
        elif "美元" in line_s or "美金" in line_s:
            current = "USD"
        elif "人民幣" in line_s:
            current = "RMB"

        if current:
            for m in re.findall(r"(\d+\.?\d*)\s*%", line_s):
                v = float(m)
                if MIN_RATE <= v <= hsbc_cap:
                    sections[current].append(v)

    result = {}
    for cur, rates in sections.items():
        if rates:
            result[cur] = max(rates)
    return result if result else None


def parse_bochk(url, cap):
    """中銀香港：有結構性存款嘅高利率（>5%），要過濾"""
    _, text = fetch_page(url)
    bochk_cap = min(cap, 4.0)  # 中銀定存通常唔超過 4%
    sections = {"HKD": [], "USD": [], "RMB": []}
    current = "HKD"
    skip = False

    for line in text.split("\n"):
        line_s = line.strip()
        if not line_s:
            continue
        # 跳過結構性產品區域
        if "結構" in line_s or "掛鈎" in line_s or "保本" in line_s:
            skip = True
            continue
        if "定期存款" in line_s and "結構" not in line_s:
            skip = False
        if skip or has_exclude_words(line_s):
            continue

        if "港幣" in line_s or "港元" in line_s:
            current = "HKD"
        elif "美元" in line_s or "美金" in line_s:
            current = "USD"
        elif "人民幣" in line_s:
            current = "RMB"

        if current:
            for m in re.findall(r"(\d+\.?\d*)\s*%", line_s):
                v = float(m)
                if MIN_RATE <= v <= bochk_cap:
                    sections[current].append(v)

    result = {}
    for cur, rates in sections.items():
        if rates:
            result[cur] = max(rates)
    return result if result else None


def parse_ccb(url, cap):
    """建設銀行亞洲：有大額推廣利率偏高，限制 cap"""
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
        best = max(rates)
        return {c: best for c in ["HKD", "USD", "RMB"]}
    return None


def parse_dbs(url, cap):
    """星展銀行：有新資金推廣利率偏高，限制 cap"""
    _, text = fetch_page(url)
    dbs_cap = min(cap, 4.0)
    rates = []
    for line in text.split("\n"):
        if has_exclude_words(line):
            continue
        for m in re.findall(r"(\d+\.?\d*)\s*%", line):
            v = float(m)
            if MIN_RATE <= v <= dbs_cap:
                rates.append(v)
    if rates:
        best = max(rates)
        return {c: best for c in ["HKD", "USD", "RMB"]}
    return None


def parse_dahsing(cap):
    """大新銀行：HKD/USD/RMB 有不同 URL"""
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
    return result if result else None


# ── 爬蟲配置 ────────────────────────────────────────────────
# parser: 函數名稱；冇指定就用 parse_generic
CONFIGS = [
    # ── 數字銀行 ──
    {"bank": "Mox銀行", "url": "https://mox.com/zh/promotions/time-deposit/", "cap": 5.0},
    {"bank": "眾安銀行", "url": "https://bank.za.group/hk/deposit", "cap": 2.0},
    {"bank": "象象銀行", "url": "https://www.elebank.com/zh-hk/hkprime.html", "cap": 2.0},
    {"bank": "匯立銀行", "url": "https://www.welab.bank/zh/feature/gosave_2/", "cap": 5.0},
    # ── 傳統銀行 ──
    {"bank": "東亞銀行", "parser": "bea", "url": "https://www.hkbea.com/html/tc/bea-personal-banking-supremegold-time-deposit.html", "cap": 5.0},
    {"bank": "工銀亞洲", "parser": "icbc", "url": "https://www.icbcasia.com/hk/tc/personal/latest-promotion/online-time-deposit.html", "cap": 5.0},
    {"bank": "上海商業銀行", "parser": "shacom", "url": "https://www.shacombank.com.hk/tch/personal/promotion/fix-rate.jsp", "cap": 5.0},
    {"bank": "大眾銀行", "parser": "publicbank", "url": "https://www.publicbank.com.hk/tc/usefultools/rates/depositinterestrates", "cap": 5.0},
    {"bank": "渣打銀行", "url": "https://www.sc.com/hk/zh/deposits/online-time-deposit/", "cap": 5.0},
    {"bank": "大新銀行", "parser": "dahsing", "cap": 5.0},
    {"bank": "建設銀行亞洲", "parser": "ccb", "url": "https://www.asia.ccb.com/hongkong_tc/personal/accounts/dep_rates.html?cmpid=HKTCDTPSACTMG-ULDEPOSITRATE", "cap": 5.0},
    {"bank": "滙豐銀行", "parser": "hsbc", "url": "https://www.hsbc.com.hk/zh-hk/accounts/offers/deposits/", "cap": 5.0},
    {"bank": "恒生銀行", "url": "https://cms.hangseng.com/cms/emkt/pmo/grp06/p04/chi/index.html", "cap": 5.0},
    {"bank": "中銀香港", "parser": "bochk", "url": "https://www.bochk.com/tc/deposits/promotion/timedeposits.html", "cap": 3.5},
    {"bank": "星展銀行", "parser": "dbs", "url": "https://www.dbs.com.hk/personal-zh/promotion/OnlineTD-promo", "cap": 3.5},
]

PARSER_MAP = {
    "bea": parse_bea,
    "icbc": parse_icbc,
    "shacom": parse_shacom,
    "publicbank": parse_publicbank,
    "hsbc": parse_hsbc,
    "bochk": parse_bochk,
    "ccb": parse_ccb,
    "dbs": parse_dbs,
}


# ── 主要爬蟲邏輯 ────────────────────────────────────────────

def scrape_bank(cfg):
    """爬取單間銀行嘅利率"""
    parser_name = cfg.get("parser")
    url = cfg.get("url", "")
    cap = cfg.get("cap", MAX_RATE)

    try:
        # 大新銀行有特殊處理（多個 URL）
        if parser_name == "dahsing":
            return parse_dahsing(cap)

        # 有自訂 parser
        if parser_name and parser_name in PARSER_MAP:
            return PARSER_MAP[parser_name](url, cap)

        # 通用 parser
        return parse_generic(url, cap)

    except Exception as e:
        print(f"  {cfg['bank']}: {e}")
    return None


def main():
    print(f"Scraper started {datetime.now()}")

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

    # 爬取每間銀行
    scraped = {}
    for cfg in CONFIGS:
        result = scrape_bank(cfg)
        if result:
            scraped[cfg["bank"]] = result
            print(f"  ✅ {cfg['bank']}: {result}")
        else:
            print(f"  ⚠️ {cfg['bank']}: 冇爬到利率")

    # 更新現有數據
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

    # 確保每間銀行都有顯示用 URL
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

    print(f"\n{'='*40}")
    print(f"爬取完成：{len(scraped)}/{len(CONFIGS)} 間銀行成功")
    print(f"利率更新：{updated_count} 個變動")
    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
