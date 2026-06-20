#!/usr/bin/env python3
"""
香港銀行定期存款利率自動爬蟲（擴充版）
使用配置式設計，每間銀行獨立設定 URL + 解析規則
注意：傳統大銀行（HSBC、BOC、Hang Seng）通常有反爬蟲/登入牆，
      免費方案未必能 100% 突破。虛擬銀行成功率較高。
運行環境：GitHub Actions（ubuntu-latest + Python 3.11）
"""
import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = "data.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
}

MIN_REASONABLE_RATE = 0.01
MAX_REASONABLE_RATE = 15.0

# 所有銀行官方連結（點擊驗證用）
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
    "工銀亞洲": "https://www.icbcasia.com/",
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

# ===== 爬蟲配置：每間銀行獨立設定 =====
# 如果某間銀行網站改咗，改呢度就得，唔使改主程式
BANK_SCRAPER_CONFIGS = [
    # 虛擬銀行（通常較易爬）
    {
        "bank": "富融銀行",
        "url": "https://www.fusionbank.com/zh-hk/deposit.html",
        "keywords": ["年利率", "利率", "定期", "存款"],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "Mox銀行",
        "url": "https://mox.com/zh/promotions/time-deposit/",
        "keywords": ["年利率", "利率", "定期", "存款", "time deposit"],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD"},
    },
    {
        "bank": "眾安銀行",
        "url": "https://www.zabank.com/",
        "keywords": ["年利率", "利率", "定期", "存款"],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD"},
    },
    {
        "bank": "理慧銀行",
        "url": "https://www.livibank.com/",
        "keywords": ["年利率", "利率", "定期", "存款"],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD"},
    },
    {
        "bank": "匯立銀行",
        "url": "https://www.welab.bank/",
        "keywords": ["年利率", "利率", "定期", "存款"],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD"},
    },
    {
        "bank": "象象銀行",
        "url": "https://www.elebank.com/",
        "keywords": ["年利率", "利率", "定期", "存款"],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    # 傳統銀行（嘗試爬，但成功率較低）
    {
        "bank": "富邦銀行",
        "url": "https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "上海商業銀行",
        "url": "https://www.shacombank.com.hk/tch/interest-rates",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "大眾銀行",
        "url": "https://www.publicbank.com.hk/personal/rates-deposits",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "OCBC",
        "url": "https://www.ocbc.com.hk/personal-banking/deposits/rates.html",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    # 以下大銀行通常有反爬蟲/複雜JS，成功率低，做後備嘗試
    {
        "bank": "渣打銀行",
        "url": "https://www.sc.com/hk/deposits/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "東亞銀行",
        "url": "https://www.hkbea.com/html/en/interest_rates.html",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "星展銀行",
        "url": "https://www.dbs.com.hk/personal/rates/deposits.page",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "大新銀行",
        "url": "https://www.dahsing.com/html/en/interest_rates.html",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "創興銀行",
        "url": "https://www.chbank.com/en/interest-rates",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "工銀亞洲",
        "url": "https://www.icbcasia.com/ICBC/海外分行/工銀亞洲/en/About_Us/Interest_Rates/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "南洋商業銀行",
        "url": "https://www.ncb.com.hk/personal/rates/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "招商永隆銀行",
        "url": "https://www.cmbwinglungbank.com/wlb_corporate/hk/about-us/interest-rates/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "中信銀行(國際)",
        "url": "https://www.cncbi.com/banking/rates",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "建設銀行亞洲",
        "url": "https://www.ccb.com.hk/personal/deposits/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    # HSBC / Hang Seng / BOC 通常封鎖爬蟲，以下做最後嘗試
    {
        "bank": "滙豐銀行",
        "url": "https://www.hsbc.com.hk/accounts/rates/deposits/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "恒生銀行",
        "url": "https://www.hangseng.com/en-hk/personal/banking/interest-rates/deposit-rates/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "中銀香港",
        "url": "https://www.bochk.com/en/bank/rates/deposit-rates.html",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "交通銀行",
        "url": "https://www.bankcomm.com.hk/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
    {
        "bank": "花旗銀行",
        "url": "https://www.citibank.com.hk/personal-banking/deposits/",
        "keywords": ["年利率", "利率", "定期", "存款", "p.a."],
        "max_rate_cap": 5.0,
        "currency_map": {"HKD": "HKD", "USD": "USD", "RMB": "RMB"},
    },
]


def scrape_bank(config):
    """
    通用爬蟲：嘗試從指定銀行頁面提取利率
    回傳：{currency: bestRate} 或 None
    """
    bank_name = config["bank"]
    url = config["url"]
    keywords = config.get("keywords", ["利率", "年利率", "定期"])
    max_cap = config.get("max_rate_cap", 5.0)
    currency_map = config.get("currency_map", {"HKD": "HKD"})

    try:
        print(f"  [嘗試] {bank_name} ...")
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(separator='\n')
        lines = text.split('\n')
        
        all_rates = []
        for line in lines:
            line_lower = line.strip().lower()
            if any(kw.lower() in line_lower for kw in keywords):
                matches = re.findall(r'(\d+\.\d+)%', line)
                for m in matches:
                    val = float(m)
                    if MIN_REASONABLE_RATE <= val <= MAX_REASONABLE_RATE:
                        all_rates.append(val)
        
        if not all_rates:
            print(f"  ⚠️ {bank_name}: 頁面搵唔到利率數字")
            return None
        
        # 過濾超高數字（通常係回贈/推廣百分比，唔係利率）
        reasonable = [r for r in all_rates if r <= max_cap]
        if not reasonable:
            reasonable = [min(all_rates)]  # 全部超過，攞最低嗰個
        
        best_rate = max(reasonable)
        
        # 簡化：暫時將所有貨幣都當做同一個利率回傳
        # 進階做法：可以按頁面內貨幣符號（HK$/US$/¥）分段，但每間銀行格式唔同
        result = {}
        for cur_key in ["HKD", "USD", "RMB"]:
            if cur_key in currency_map:
                result[cur_key] = best_rate
        
        print(f"  ✅ {bank_name}: 搵到 {best_rate}%")
        return result
        
    except Exception as e:
        print(f"  ❌ {bank_name}: 失敗 ({type(e).__name__})")
        return None


def merge_scraped_results(existing_rates, scraped_results):
    """將爬蟲結果合併入現有數據"""
    for bank_name, currency_rates in scraped_results.items():
        if not currency_rates:
            continue
        for currency, banks in existing_rates.items():
            if currency not in currency_rates:
                continue
            new_rate = currency_rates[currency]
            if not (MIN_REASONABLE_RATE <= new_rate <= MAX_REASONABLE_RATE):
                continue
            for i, bank in enumerate(banks):
                if bank["bank"] == bank_name:
                    if new_rate > 0:
                        # 只更新利率，保留其他欄位（period, minDeposit, note, url）
                        bank["bestRate"] = new_rate
                        bank["note"] = (bank.get("note", "").replace("auto-scraped", "").replace("; ", "") + "; auto-scraped").strip("; ")
                        print(f"  已更新: {bank_name} ({currency}) = {new_rate}%")
                    break
    return existing_rates


def inject_urls(data):
    """確保所有銀行都有 URL 供點擊驗證"""
    for currency, banks in data.items():
        for bank in banks:
            bank_name = bank.get("bank", "")
            if bank_name in BANK_URLS and not bank.get("url"):
                bank["url"] = BANK_URLS[bank_name]
    return data


def load_existing_data():
    if Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            current = json.load(f)
        return current.get("rates", {})
    return {}


def build_fallback_rates():
    """如果冇舊數據，用 fallback 初始化"""
    # 讀取舊 data.json 或建立新結構
    existing = load_existing_data()
    if existing:
        return existing
    
    # 最小 fallback（理論上唔會用到，因為第一次應該手動建立 data.json）
    return {
        "HKD": [],
        "USD": [],
        "RMB": []
    }


def main():
    print(f"=== 香港銀行利率爬蟲啟動 === {datetime.now()}\n")
    
    # 載入現有數據（作為基礎）
    rates = load_existing_data()
    if not rates:
        # 嘗試由舊 data.json 讀取，如果格式唔啱就建空結構
        print("⚠️ 冇舊數據，建立空結構。首次使用請先上傳 baseline data.json")
        rates = {"HKD": [], "USD": [], "RMB": []}
    
    # 確保所有貨幣 key 存在
    for cur in ["HKD", "USD", "RMB"]:
        if cur not in rates:
            rates[cur] = []
    
    # 逐間爬
    scraped_results = {}
    for config in BANK_SCRAPER_CONFIGS:
        result = scrape_bank(config)
        if result:
            scraped_results[config["bank"]] = result
    
    # 合併結果
    print("\n--- 合併數據 ---")
    rates = merge_scraped_results(rates, scraped_results)
    
    # 補充 URL
    rates = inject_urls(rates)
    
    # 輸出
    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rates": rates
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== 完成 === 儲存到 {OUTPUT_FILE} 於 {output['updated_at']}")
    print(f"成功爬取: {len(scraped_results)} / {len(BANK_SCRAPER_CONFIGS)} 間銀行")
    if len(scraped_results) < len(BANK_SCRAPER_CONFIGS):
        failed = [c["bank"] for c in BANK_SCRAPER_CONFIGS if c["bank"] not in scraped_results]
        print(f"失敗銀行（使用舊數據/Fallback）: {', '.join(failed)}")


if __name__ == "__main__":
    main()
