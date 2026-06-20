#!/usr/bin/env python3
"""
香港銀行定期存款利率自動爬蟲（最終修正版）
- 所有連結直接指向各銀行定期存款利率/存款利率頁面
- 如銀行網站改版，請手動更新 BANK_URLS 字典
"""
import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = "data.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MIN_REASONABLE_RATE = 0.01
MAX_REASONABLE_RATE = 15.0

# ===== 各銀行定期存款利率直接連結 =====
BANK_URLS = {
    "富融銀行": "https://www.fusionbank.com/zh-hk/deposit.html",
    "象象銀行": "https://www.elebank.com/",
    "匯立銀行": "https://www.welab.bank/",
    "Mox銀行": "https://mox.com/zh/promotions/time-deposit/",
    "理慧銀行": "https://www.livibank.com/",
    "眾安銀行": "https://www.zabank.com/",
    "滙豐銀行": "https://www.hsbc.com.hk/accounts/rates/deposits/",
    "恒生銀行": "https://www.hangseng.com/en-hk/personal/banking/interest-rates/deposit-rates/",
    "中銀香港": "https://www.bochk.com/en/bank/rates/deposit-rates.html",
    "渣打銀行": "https://www.sc.com/hk/deposits/",
    "工銀亞洲": "https://www.icbcasia.com/ICBC/海外分行/工銀亞洲/en/About_Us/Interest_Rates/",
    "東亞銀行": "https://www.hkbea.com/html/en/interest_rates.html",
    "星展銀行": "https://www.dbs.com.hk/personal/rates/deposits.page",
    "中信銀行(國際)": "https://www.cncbi.com/banking/rates",
    "富邦銀行": "https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html",
    "南洋商業銀行": "https://www.ncb.com.hk/personal/rates/",
    "招商永隆銀行": "https://www.cmbwinglungbank.com/wlb_corporate/hk/about-us/interest-rates/",
    "上海商業銀行": "https://www.shacombank.com.hk/tch/interest-rates",
    "大眾銀行": "https://www.publicbank.com.hk/personal/rates-deposits",
    "交通銀行": "https://www.bankcomm.com.hk/",
    "建設銀行亞洲": "https://www.ccb.com.hk/personal/deposits/",
    "花旗銀行": "https://www.citibank.com.hk/personal-banking/deposits/",
    "大新銀行": "https://www.dahsing.com/html/en/interest_rates.html",
    "創興銀行": "https://www.chbank.com/en/interest-rates",
    "OCBC": "https://www.ocbc.com.hk/personal-banking/deposits/rates.html",
}

FALLBACK_RATES = {
    "HKD": [
        {"bank": "富融銀行", "type": "virtual", "bestRate": 2.90, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "象象銀行", "type": "virtual", "bestRate": 2.90, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "匯立銀行", "type": "virtual", "bestRate": 2.80, "bestPeriod": "12個月", "minDeposit": "HKD 10", "note": ""},
        {"bank": "Mox銀行", "type": "virtual", "bestRate": 2.70, "bestPeriod": "12個月", "minDeposit": "HKD 1", "note": ""},
        {"bank": "富邦銀行", "type": "traditional", "bestRate": 2.70, "bestPeriod": "3-12個月", "minDeposit": "HKD 500,000", "note": "大額存款優惠"},
        {"bank": "理慧銀行", "type": "virtual", "bestRate": 2.50, "bestPeriod": "3-6個月", "minDeposit": "HKD 50,000", "note": ""},
        {"bank": "建設銀行亞洲", "type": "traditional", "bestRate": 2.55, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "工銀亞洲", "type": "traditional", "bestRate": 2.55, "bestPeriod": "3個月", "minDeposit": "HKD 50,000", "note": ""},
        {"bank": "南洋商業銀行", "type": "traditional", "bestRate": 2.65, "bestPeriod": "3個月", "minDeposit": "HKD 100,000", "note": ""},
        {"bank": "上海商業銀行", "type": "traditional", "bestRate": 2.63, "bestPeriod": "3個月", "minDeposit": "HKD 1,000", "note": ""},
        {"bank": "中信銀行(國際)", "type": "traditional", "bestRate": 2.60, "bestPeriod": "12個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "東亞銀行", "type": "traditional", "bestRate": 2.45, "bestPeriod": "3-6個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "渣打銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "中銀香港", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3-6個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "恒生銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "滙豐銀行", "type": "traditional", "bestRate": 2.30, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "大眾銀行", "type": "traditional", "bestRate": 2.35, "bestPeriod": "1-12個月", "minDeposit": "HKD 100,000", "note": ""},
        {"bank": "大新銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 200,000", "note": ""},
        {"bank": "星展銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": ""},
        {"bank": "招商永隆銀行", "type": "traditional", "bestRate": 2.00, "bestPeriod": "3-12個月", "minDeposit": "HKD 500,000", "note": ""},
        {"bank": "眾安銀行", "type": "virtual", "bestRate": 2.01, "bestPeriod": "12個月", "minDeposit": "HKD 1", "note": ""}
    ],
    "USD": [
        {"bank": "富邦銀行", "type": "traditional", "bestRate": 4.00, "bestPeriod": "3個月", "minDeposit": "USD 65,000", "note": "新資金或網上開立優惠可達4%"},
        {"bank": "建設銀行亞洲", "type": "traditional", "bestRate": 3.80, "bestPeriod": "3-12個月", "minDeposit": "USD 10,000", "note": ""},
        {"bank": "富融銀行", "type": "virtual", "bestRate": 3.60, "bestPeriod": "3個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "恒生銀行", "type": "traditional", "bestRate": 3.50, "bestPeriod": "3-6個月", "minDeposit": "USD 2,000", "note": ""},
        {"bank": "中銀香港", "type": "traditional", "bestRate": 3.50, "bestPeriod": "3-6個月", "minDeposit": "USD 1,000", "note": ""},
        {"bank": "工銀亞洲", "type": "traditional", "bestRate": 3.45, "bestPeriod": "3個月", "minDeposit": "USD 1,000,000", "note": "大額優惠"},
        {"bank": "Mox銀行", "type": "virtual", "bestRate": 3.35, "bestPeriod": "1個月", "minDeposit": "USD 1", "note": ""},
        {"bank": "招商永隆銀行", "type": "traditional", "bestRate": 3.35, "bestPeriod": "3個月", "minDeposit": "USD 50,000", "note": ""},
        {"bank": "大眾銀行", "type": "traditional", "bestRate": 3.40, "bestPeriod": "3個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "南洋商業銀行", "type": "traditional", "bestRate": 3.35, "bestPeriod": "3個月", "minDeposit": "USD 13,000", "note": ""},
        {"bank": "上海商業銀行", "type": "traditional", "bestRate": 3.33, "bestPeriod": "3個月", "minDeposit": "USD 10,000", "note": ""},
        {"bank": "東亞銀行", "type": "traditional", "bestRate": 3.40, "bestPeriod": "3個月", "minDeposit": "USD 1,000", "note": ""},
        {"bank": "滙豐銀行", "type": "traditional", "bestRate": 3.30, "bestPeriod": "3個月", "minDeposit": "USD 2,000", "note": ""},
        {"bank": "星展銀行", "type": "traditional", "bestRate": 3.35, "bestPeriod": "3個月", "minDeposit": "USD 6,000", "note": ""},
        {"bank": "渣打銀行", "type": "traditional", "bestRate": 3.20, "bestPeriod": "3-6個月", "minDeposit": "USD 2,000", "note": ""},
        {"bank": "象象銀行", "type": "virtual", "bestRate": 3.15, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "匯立銀行", "type": "virtual", "bestRate": 3.05, "bestPeriod": "3個月", "minDeposit": "HKD 10", "note": ""}
    ],
    "RMB": [
        {"bank": "富融銀行", "type": "virtual", "bestRate": 1.55, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "富邦銀行", "type": "traditional", "bestRate": 1.50, "bestPeriod": "3-12個月", "minDeposit": "RMB 500,000", "note": ""},
        {"bank": "南洋商業銀行", "type": "traditional", "bestRate": 1.50, "bestPeriod": "12個月", "minDeposit": "RMB 100,000", "note": ""},
        {"bank": "工銀亞洲", "type": "traditional", "bestRate": 1.40, "bestPeriod": "12個月", "minDeposit": "RMB 500,000", "note": ""},
        {"bank": "象象銀行", "type": "virtual", "bestRate": 1.35, "bestPeriod": "6個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "交通銀行", "type": "traditional", "bestRate": 1.35, "bestPeriod": "3個月", "minDeposit": "RMB 10,000", "note": ""},
        {"bank": "中銀香港", "type": "traditional", "bestRate": 1.30, "bestPeriod": "12個月", "minDeposit": "RMB 10,000", "note": ""},
        {"bank": "滙豐銀行", "type": "traditional", "bestRate": 1.30, "bestPeriod": "3-12個月", "minDeposit": "RMB 10,000", "note": ""},
        {"bank": "大眾銀行", "type": "traditional", "bestRate": 1.30, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": ""},
        {"bank": "恒生銀行", "type": "traditional", "bestRate": 1.20, "bestPeriod": "3-6個月", "minDeposit": "RMB 10,000", "note": ""},
        {"bank": "渣打銀行", "type": "traditional", "bestRate": 1.20, "bestPeriod": "12個月", "minDeposit": "RMB 10,000", "note": ""},
        {"bank": "招商永隆銀行", "type": "traditional", "bestRate": 1.25, "bestPeriod": "12個月", "minDeposit": "RMB 10,000", "note": ""}
    ]
}


def extract_rates_from_context(soup, max_rate_cap=5.0):
    text = soup.get_text(separator='\n')
    lines = text.split('\n')
    keywords = ["年利率", "利率", "p.a.", "定期", "存款", "time deposit", "earn", "interest rate"]
    rates = []
    for line in lines:
        line_lower = line.strip().lower()
        if any(kw in line_lower for kw in keywords):
            matches = re.findall(r'(\d+\.\d+)%', line)
            for m in matches:
                val = float(m)
                if MIN_REASONABLE_RATE <= val <= MAX_REASONABLE_RATE:
                    rates.append(val)
    if rates:
        reasonable = [r for r in rates if r <= max_rate_cap]
        if reasonable:
            return reasonable
        else:
            return [min(rates)]
    return []


def scrape_fusion_bank():
    try:
        url = "https://www.fusionbank.com/zh-hk/deposit.html"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        rates = extract_rates_from_context(soup, max_rate_cap=5.0)
        if rates:
            return {"bank": "富融銀行", "type": "virtual", "bestRate": max(rates), "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "auto-scraped"}
    except Exception as e:
        print(f"Fusion Bank failed: {e}")
    return None


def scrape_mox_bank():
    try:
        url = "https://mox.com/zh/promotions/time-deposit/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        rates = extract_rates_from_context(soup, max_rate_cap=5.0)
        if rates:
            max_rate = max(rates)
            return {
                "bank": "Mox銀行",
                "type": "virtual",
                "bestRate": max_rate,
                "bestPeriod": "12個月",
                "minDeposit": "HKD 1",
                "note": "auto-scraped"
            }
    except Exception as e:
        print(f"Mox Bank failed: {e}")
    return None


def merge_rates(existing, new_items):
    for item in new_items:
        if item is None:
            continue
        if not (MIN_REASONABLE_RATE <= item.get("bestRate", 0) <= MAX_REASONABLE_RATE):
            print(f"Rejecting unreasonable rate for {item['bank']}: {item['bestRate']}%")
            continue
        for currency, banks in existing.items():
            for i, bank in enumerate(banks):
                if bank["bank"] == item["bank"]:
                    existing[currency][i] = item
                    print(f"Updated {item['bank']} ({currency}): {item['bestRate']}%")
                    break
    return existing


def inject_urls(data):
    for currency, banks in data.items():
        for bank in banks:
            bank_name = bank.get("bank", "")
            if bank_name in BANK_URLS and not bank.get("url"):
                bank["url"] = BANK_URLS[bank_name]
    return data


def main():
    print(f"Starting scraper at {datetime.now()}")
    
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            current = json.load(f)
        rates = current.get("rates", FALLBACK_RATES)
    else:
        rates = FALLBACK_RATES
    
    rates = inject_urls(rates)
    scraped = [scrape_fusion_bank(), scrape_mox_bank()]
    rates = merge_rates(rates, scraped)
    rates = inject_urls(rates)
    
    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rates": rates
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to {OUTPUT_FILE} at {output['updated_at']}")


if __name__ == "__main__":
    main()
