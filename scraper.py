#!/usr/bin/env python3
"""
香港銀行定期存款利率自動爬蟲（最終修正版）
- 加強過濾，避免抓到非利率數字（如 5.34% 回贈）
- 每間銀行加入 source URL，供用戶點擊驗證
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
MIN_REASONABLE_RATE = 0.01
MAX_REASONABLE_RATE = 15.0

# Fallback 數據（加入 url 供點擊驗證）
FALLBACK_RATES = {
    "HKD": [
        {"bank": "富融銀行", "type": "virtual", "bestRate": 2.90, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.fusionbank.com/zh-hk/deposit.html"},
        {"bank": "象象銀行", "type": "virtual", "bestRate": 2.90, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.elebank.com/"},
        {"bank": "匯立銀行", "type": "virtual", "bestRate": 2.80, "bestPeriod": "12個月", "minDeposit": "HKD 10", "note": "", "url": "https://www.welab.bank/"},
        {"bank": "Mox銀行", "type": "virtual", "bestRate": 2.70, "bestPeriod": "12個月", "minDeposit": "HKD 1", "note": "", "url": "https://mox.com/zh/promotions/time-deposit/"},
        {"bank": "富邦銀行", "type": "traditional", "bestRate": 2.70, "bestPeriod": "3-12個月", "minDeposit": "HKD 500,000", "note": "大額存款優惠", "url": "https://www.fubonbank.com.hk/"},
        {"bank": "理慧銀行", "type": "virtual", "bestRate": 2.50, "bestPeriod": "3-6個月", "minDeposit": "HKD 50,000", "note": "", "url": "https://www.livibank.com/"},
        {"bank": "建設銀行亞洲", "type": "traditional", "bestRate": 2.55, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.ccb.com.hk/personal/deposits/"},
        {"bank": "工銀亞洲", "type": "traditional", "bestRate": 2.55, "bestPeriod": "3個月", "minDeposit": "HKD 50,000", "note": "", "url": "https://www.icbcasia.com/ICBC/海外分行/工銀亞洲/en/About_Us/Interest_Rates/"},
        {"bank": "南洋商業銀行", "type": "traditional", "bestRate": 2.65, "bestPeriod": "3個月", "minDeposit": "HKD 100,000", "note": "", "url": "https://www.ncb.com.hk/personal/rates/"},
        {"bank": "上海商業銀行", "type": "traditional", "bestRate": 2.63, "bestPeriod": "3個月", "minDeposit": "HKD 1,000", "note": "", "url": "https://www.shacombank.com.hk/tch/interest-rates"},
        {"bank": "中信銀行(國際)", "type": "traditional", "bestRate": 2.60, "bestPeriod": "12個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.cncbi.com/banking/rates"},
        {"bank": "東亞銀行", "type": "traditional", "bestRate": 2.45, "bestPeriod": "3-6個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.hkbea.com/html/en/interest_rates.html"},
        {"bank": "渣打銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.sc.com/hk/deposits/"},
        {"bank": "中銀香港", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3-6個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.bochk.com/en/bank/rates/deposit-rates.html"},
        {"bank": "恒生銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.hangseng.com/en-hk/personal/banking/interest-rates/deposit-rates/"},
        {"bank": "滙豐銀行", "type": "traditional", "bestRate": 2.30, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.hsbc.com.hk/accounts/rates/deposits/"},
        {"bank": "大眾銀行", "type": "traditional", "bestRate": 2.35, "bestPeriod": "1-12個月", "minDeposit": "HKD 100,000", "note": "", "url": "https://www.publicbank.com.hk/personal/rates-deposits"},
        {"bank": "大新銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 200,000", "note": "", "url": "https://www.dahsing.com/html/en/interest_rates.html"},
        {"bank": "星展銀行", "type": "traditional", "bestRate": 2.40, "bestPeriod": "3個月", "minDeposit": "HKD 10,000", "note": "", "url": "https://www.dbs.com.hk/personal/rates/deposits.page"},
        {"bank": "招商永隆銀行", "type": "traditional", "bestRate": 2.00, "bestPeriod": "3-12個月", "minDeposit": "HKD 500,000", "note": "", "url": "https://www.cmbwinglungbank.com/wlb_corporate/hk/about-us/interest-rates/"},
        {"bank": "眾安銀行", "type": "virtual", "bestRate": 2.01, "bestPeriod": "12個月", "minDeposit": "HKD 1", "note": "", "url": "https://www.zabank.com/"}
    ],
    "USD": [
        {"bank": "富邦銀行", "type": "traditional", "bestRate": 4.00, "bestPeriod": "3個月", "minDeposit": "USD 65,000", "note": "新資金或網上開立優惠可達4%", "url": "https://www.fubonbank.com.hk/"},
        {"bank": "建設銀行亞洲", "type": "traditional", "bestRate": 3.80, "bestPeriod": "3-12個月", "minDeposit": "USD 10,000", "note": "", "url": "https://www.ccb.com.hk/personal/deposits/"},
        {"bank": "富融銀行", "type": "virtual", "bestRate": 3.60, "bestPeriod": "3個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.fusionbank.com/zh-hk/deposit.html"},
        {"bank": "恒生銀行", "type": "traditional", "bestRate": 3.50, "bestPeriod": "3-6個月", "minDeposit": "USD 2,000", "note": "", "url": "https://www.hangseng.com/en-hk/personal/banking/interest-rates/deposit-rates/"},
        {"bank": "中銀香港", "type": "traditional", "bestRate": 3.50, "bestPeriod": "3-6個月", "minDeposit": "USD 1,000", "note": "", "url": "https://www.bochk.com/en/bank/rates/deposit-rates.html"},
        {"bank": "工銀亞洲", "type": "traditional", "bestRate": 3.45, "bestPeriod": "3個月", "minDeposit": "USD 1,000,000", "note": "大額優惠", "url": "https://www.icbcasia.com/ICBC/海外分行/工銀亞洲/en/About_Us/Interest_Rates/"},
        {"bank": "Mox銀行", "type": "virtual", "bestRate": 3.35, "bestPeriod": "1個月", "minDeposit": "USD 1", "note": "", "url": "https://mox.com/zh/promotions/time-deposit/"},
        {"bank": "招商永隆銀行", "type": "traditional", "bestRate": 3.35, "bestPeriod": "3個月", "minDeposit": "USD 50,000", "note": "", "url": "https://www.cmbwinglungbank.com/wlb_corporate/hk/about-us/interest-rates/"},
        {"bank": "大眾銀行", "type": "traditional", "bestRate": 3.40, "bestPeriod": "3個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.publicbank.com.hk/personal/rates-deposits"},
        {"bank": "南洋商業銀行", "type": "traditional", "bestRate": 3.35, "bestPeriod": "3個月", "minDeposit": "USD 13,000", "note": "", "url": "https://www.ncb.com.hk/personal/rates/"},
        {"bank": "上海商業銀行", "type": "traditional", "bestRate": 3.33, "bestPeriod": "3個月", "minDeposit": "USD 10,000", "note": "", "url": "https://www.shacombank.com.hk/tch/interest-rates"},
        {"bank": "東亞銀行", "type": "traditional", "bestRate": 3.40, "bestPeriod": "3個月", "minDeposit": "USD 1,000", "note": "", "url": "https://www.hkbea.com/html/en/interest_rates.html"},
        {"bank": "滙豐銀行", "type": "traditional", "bestRate": 3.30, "bestPeriod": "3個月", "minDeposit": "USD 2,000", "note": "", "url": "https://www.hsbc.com.hk/accounts/rates/deposits/"},
        {"bank": "星展銀行", "type": "traditional", "bestRate": 3.35, "bestPeriod": "3個月", "minDeposit": "USD 6,000", "note": "", "url": "https://www.dbs.com.hk/personal/rates/deposits.page"},
        {"bank": "渣打銀行", "type": "traditional", "bestRate": 3.20, "bestPeriod": "3-6個月", "minDeposit": "USD 2,000", "note": "", "url": "https://www.sc.com/hk/deposits/"},
        {"bank": "象象銀行", "type": "virtual", "bestRate": 3.15, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.elebank.com/"},
        {"bank": "匯立銀行", "type": "virtual", "bestRate": 3.05, "bestPeriod": "3個月", "minDeposit": "HKD 10", "note": "", "url": "https://www.welab.bank/"}
    ],
    "RMB": [
        {"bank": "富融銀行", "type": "virtual", "bestRate": 1.55, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.fusionbank.com/zh-hk/deposit.html"},
        {"bank": "富邦銀行", "type": "traditional", "bestRate": 1.50, "bestPeriod": "3-12個月", "minDeposit": "RMB 500,000", "note": "", "url": "https://www.fubonbank.com.hk/"},
        {"bank": "南洋商業銀行", "type": "traditional", "bestRate": 1.50, "bestPeriod": "12個月", "minDeposit": "RMB 100,000", "note": "", "url": "https://www.ncb.com.hk/personal/rates/"},
        {"bank": "工銀亞洲", "type": "traditional", "bestRate": 1.40, "bestPeriod": "12個月", "minDeposit": "RMB 500,000", "note": "", "url": "https://www.icbcasia.com/ICBC/海外分行/工銀亞洲/en/About_Us/Interest_Rates/"},
        {"bank": "象象銀行", "type": "virtual", "bestRate": 1.35, "bestPeriod": "6個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.elebank.com/"},
        {"bank": "交通銀行", "type": "traditional", "bestRate": 1.35, "bestPeriod": "3個月", "minDeposit": "RMB 10,000", "note": "", "url": "https://www.bankcomm.com.hk/"},
        {"bank": "中銀香港", "type": "traditional", "bestRate": 1.30, "bestPeriod": "12個月", "minDeposit": "RMB 10,000", "note": "", "url": "https://www.bochk.com/en/bank/rates/deposit-rates.html"},
        {"bank": "滙豐銀行", "type": "traditional", "bestRate": 1.30, "bestPeriod": "3-12個月", "minDeposit": "RMB 10,000", "note": "", "url": "https://www.hsbc.com.hk/accounts/rates/deposits/"},
        {"bank": "大眾銀行", "type": "traditional", "bestRate": 1.30, "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "", "url": "https://www.publicbank.com.hk/personal/rates-deposits"},
        {"bank": "恒生銀行", "type": "traditional", "bestRate": 1.20, "bestPeriod": "3-6個月", "minDeposit": "RMB 10,000", "note": "", "url": "https://www.hangseng.com/en-hk/personal/banking/interest-rates/deposit-rates/"},
        {"bank": "渣打銀行", "type": "traditional", "bestRate": 1.20, "bestPeriod": "12個月", "minDeposit": "RMB 10,000", "note": "", "url": "https://www.sc.com/hk/deposits/"},
        {"bank": "招商永隆銀行", "type": "traditional", "bestRate": 1.25, "bestPeriod": "12個月", "minDeposit": "RMB 10,000", "note": "", "url": "https://www.cmbwinglungbank.com/wlb_corporate/hk/about-us/interest-rates/"}
    ]
}


def extract_rates_from_context(soup, keywords=None, max_rate_cap=5.0):
    """
    從 BeautifulSoup 提取利率，只保留在關鍵字（如"利率","定期"）附近出現嘅百分比。
    避免撈到網頁其他不相關嘅數字（如回贈百分比、進度條等）。
    """
    if keywords is None:
        keywords = ["年利率", "利率", "p.a.", "定期", "存款", "time deposit", "earn", "interest rate"]
    
    text = soup.get_text(separator='\n')
    lines = text.split('\n')
    rates = []
    
    for line in lines:
        line_lower = line.strip().lower()
        # 只處理包含利率相關關鍵字嘅行
        if any(kw in line_lower for kw in keywords):
            matches = re.findall(r'(\d+\.\d+)%', line)
            for m in matches:
                val = float(m)
                if MIN_REASONABLE_RATE <= val <= MAX_REASONABLE_RATE:
                    rates.append(val)
    
    # 如果抓到超過 cap 嘅數字（如 5.34% 回贈），就過濾掉
    if rates:
        reasonable = [r for r in rates if r <= max_rate_cap]
        if reasonable:
            return reasonable
        else:
            # 全部超過 cap，可能係真嘅高息，但保守起見攞最小嘅（避免 112.5 呢啲）
            return [min(rates)]
    return []


def scrape_fusion_bank():
    """爬富融銀行"""
    try:
        url = "https://www.fusionbank.com/zh-hk/deposit.html"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        rates = extract_rates_from_context(soup, max_rate_cap=5.0)
        if rates:
            return {"bank": "富融銀行", "type": "virtual", "bestRate": max(rates), "bestPeriod": "12個月", "minDeposit": "沒有最低", "note": "auto-scraped", "url": url}
    except Exception as e:
        print(f"Fusion Bank failed: {e}")
    return None


def scrape_mox_bank():
    """
    爬 Mox 銀行 - 使用指定定期存款頁面，避免 homepage 其他數字干擾
    """
    try:
        url = "https://mox.com/zh/promotions/time-deposit/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 使用關鍵字過濾，只攞 "利率" / "定期" 附近嘅數字
        rates = extract_rates_from_context(soup, max_rate_cap=5.0)
        
        if rates:
            max_rate = max(rates)
            return {
                "bank": "Mox銀行",
                "type": "virtual",
                "bestRate": max_rate,
                "bestPeriod": "12個月",
                "minDeposit": "HKD 1",
                "note": "auto-scraped",
                "url": url
            }
    except Exception as e:
        print(f"Mox Bank failed: {e}")
    return None


def merge_rates(existing, new_items):
    """合併新爬到的數據，保留原有 url 等欄位"""
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
                    # 保留原有 url 如果爬蟲冇提供
                    if not item.get("url") and bank.get("url"):
                        item["url"] = bank["url"]
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
