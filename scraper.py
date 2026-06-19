#!/usr/bin/env python3
"""
香港銀行定期存款利率自動爬蟲
運行環境：GitHub Actions（伺服器端，冇 CORS 限制）
每日自動執行，更新 data.json

注意：銀行網站經常改版，爬蟲需要不定期維護。
如果某間銀行爬不到，會自動用 fallback 數據替代。
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ===== 設定 =====
OUTPUT_FILE = "data.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

# Fallback 數據（當爬蟲失敗時用）
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


def scrape_fusion_bank():
    """嘗試爬富融銀行"""
    try:
        url = "https://www.fusionbank.com/zh-hk/deposit.html"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        
        # 用 regex 搵利率數字
        matches = re.findall(r'(\d+\.\d+)%', r.text)
        if matches:
            rates = [float(m) for m in matches]
            max_rate = max(rates)
            # 搵對應期數（簡化處理）
            return {"bank": "富融銀行", "type": "virtual", "bestRate": max_rate, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "auto-scraped"}
    except Exception as e:
        print(f"Fusion Bank scrape failed: {e}")
    return None


def scrape_mox_bank():
    """嘗試爬 Mox 銀行"""
    try:
        url = "https://www.mox.com/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        
        matches = re.findall(r'(\d+\.\d+)%', r.text)
        if matches:
            rates = [float(m) for m in matches]
            max_rate = max(rates)
            return {"bank": "Mox銀行", "type": "virtual", "bestRate": max_rate, "bestPeriod": "12個月", "minDeposit": "HKD 1", "note": "auto-scraped"}
    except Exception as e:
        print(f"Mox Bank scrape failed: {e}")
    return None


def merge_rates(existing, new_items):
    """合併新爬到的數據到現有列表"""
    for item in new_items:
        if item is None:
            continue
        # 搵同名的銀行更新
        for currency, banks in existing.items():
            for i, bank in enumerate(banks):
                if bank["bank"] == item["bank"] and item.get("bestRate", 0) > bank["bestRate"]:
                    existing[currency][i] = item
                    print(f"Updated {item['bank']} ({currency}): {item['bestRate']}%")
                    break
    return existing


def main():
    print(f"Starting scraper at {datetime.now()}")
    
    # 先載入現有數據（如果存在）
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            current = json.load(f)
        rates = current.get("rates", FALLBACK_RATES)
    else:
        rates = FALLBACK_RATES
    
    # 嘗試爬蟲
    scraped = []
    scraped.append(scrape_fusion_bank())
    scraped.append(scrape_mox_bank())
    
    # 合併結果
    rates = merge_rates(rates, scraped)
    
    # 寫入文件
    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rates": rates
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to {OUTPUT_FILE} at {output['updated_at']}")


if __name__ == "__main__":
    main()
