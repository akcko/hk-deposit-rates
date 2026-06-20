#!/usr/bin/env python3
"""
香港銀行定期存款利率自動爬蟲（改良版）
加強過濾，避免抓到非利率數字
"""
import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = "data.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 利率合理範圍（過濾垃圾數據）
MIN_REASONABLE_RATE = 0.01
MAX_REASONABLE_RATE = 15.0

FALLBACK_RATES = {
    # ... 同之前一樣 ...
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


def extract_rates(html_text, max_rate=10.0):
    """從 HTML 提取合理範圍內的利率數字"""
    # 搵 "X.XX%" 格式
    matches = re.findall(r'(\d+\.\d+)%', html_text)
    rates = []
    for m in matches:
        val = float(m)
        # 過濾明顯垃圾數據（利率應該喺 0.01% 到 15% 之間）
        if MIN_REASONABLE_RATE <= val <= MAX_REASONABLE_RATE:
            rates.append(val)
    return rates


def scrape_fusion_bank():
    """爬富融銀行"""
    try:
        url = "https://www.fusionbank.com/zh-hk/deposit.html"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        rates = extract_rates(r.text)
        if rates:
            max_rate = max(rates)
            return {"bank": "富融銀行", "type": "virtual", "bestRate": max_rate, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "auto-scraped"}
    except Exception as e:
        print(f"Fusion Bank failed: {e}")
    return None


def scrape_mox_bank():
    """爬 Mox 銀行（用更嚴格過濾）"""
    try:
        url = "https://www.mox.com/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        
        # 用 BeautifulSoup 搵文字附近嘅利率，避免亂抓
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text()
        
        # 搵 "X%" 或 "X.XX%" 附近嘅利率相關文字
        rates = extract_rates(text)
        if rates:
            # 對 Mox 特別保守，只取最高但合理嘅（通常唔會超過 5-6%）
            max_rate = max(rates)
            if max_rate > 6.0:
                # 如果超過 6%，可能係垃圾數據，攞次高或 fallback
                reasonable = [r for r in rates if r <= 6.0]
                if reasonable:
                    max_rate = max(reasonable)
                else:
                    return None  # 唔更新，用 fallback
            return {"bank": "Mox銀行", "type": "virtual", "bestRate": max_rate, "bestPeriod": "12個月", "minDeposit": "HKD 1", "note": "auto-scraped"}
    except Exception as e:
        print(f"Mox Bank failed: {e}")
    return None


def merge_rates(existing, new_items):
    """合併新爬到的數據，但只更新合理範圍內嘅利率"""
    for item in new_items:
        if item is None:
            continue
        # 驗證利率合理性
        if not (MIN_REASONABLE_RATE <= item.get("bestRate", 0) <= MAX_REASONABLE_RATE):
            print(f"Rejecting unreasonable rate for {item['bank']}: {item['bestRate']}%")
            continue
            
        for currency, banks in existing.items():
            for i, bank in enumerate(banks):
                if bank["bank"] == item["bank"]:
                    # 只更新如果新利率高過舊嘅（或同樣合理）
                    if item.get("bestRate", 0) > 0:
                        existing[currency][i] = item
                        print(f"Updated {item['bank']} ({currency}): {item['bestRate']}%")
                    break
    return existing


def main():
    print(f"Starting scraper at {datetime.now()}")
    
    # 載入現有數據（如果存在）
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            current = json.load(f)
        rates = current.get("rates", FALLBACK_RATES)
    else:
        rates = FALLBACK_RATES
    
    # 嘗試爬蟲
    scraped = [scrape_fusion_bank(), scrape_mox_bank()]
    
    # 合併結果（有過濾）
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
