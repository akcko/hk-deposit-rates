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
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MIN_RATE = 0.01
MAX_RATE = 15.0

BANK_URLS = {
    "富融銀行": "https://www.fusionbank.com/zh-hk/deposit.html",
    "象象銀行": "https://www.elebank.com/zh-hk/hkprime.html",
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

# 爬蟲配置：url, 關鍵字, 排除詞, 上限
CONFIGS = [
    {"bank": "富融銀行", "url": "https://www.fusionbank.com/zh-hk/deposit.html", "cap": 5.0},
    {"bank": "Mox銀行", "url": "https://mox.com/zh/promotions/time-deposit/", "cap": 5.0},
    {"bank": "眾安銀行", "url": "https://www.zabank.com/", "cap": 5.0},
    {"bank": "理慧銀行", "url": "https://www.livibank.com/", "cap": 5.0},
    {"bank": "匯立銀行", "url": "https://www.welab.bank/", "cap": 5.0},
    {"bank": "象象銀行", "url": "https://www.elebank.com/zh-hk/hkprime.html", "cap": 4.0},
    {"bank": "富邦銀行", "url": "https://www.fubonbank.com.hk/tc/deposit/latest-promotions/new-customers-promotion.html", "cap": 5.0},
    {"bank": "上海商業銀行", "url": "https://www.shacombank.com.hk/tch/interest-rates", "cap": 5.0},
    {"bank": "大眾銀行", "url": "https://www.publicbank.com.hk/personal/rates-deposits", "cap": 5.0},
    {"bank": "OCBC", "url": "https://www.ocbc.com.hk/personal-banking/deposits/rates.html", "cap": 5.0},
    {"bank": "渣打銀行", "url": "https://www.sc.com/hk/deposits/", "cap": 5.0},
    {"bank": "東亞銀行", "url": "https://www.hkbea.com/html/en/interest_rates.html", "cap": 5.0},
    {"bank": "星展銀行", "url": "https://www.dbs.com.hk/personal/rates/deposits.page", "cap": 5.0},
    {"bank": "大新銀行", "url": "https://www.dahsing.com/html/en/interest_rates.html", "cap": 5.0},
    {"bank": "創興銀行", "url": "https://www.chbank.com/en/interest-rates", "cap": 5.0},
    {"bank": "工銀亞洲", "url": "https://www.icbcasia.com/", "cap": 5.0},
    {"bank": "南洋商業銀行", "url": "https://www.ncb.com.hk/personal/rates/", "cap": 5.0},
    {"bank": "招商永隆銀行", "url": "https://www.cmbwinglungbank.com/wlb_corporate/hk/about-us/interest-rates/", "cap": 5.0},
    {"bank": "中信銀行(國際)", "url": "https://www.cncbi.com/banking/rates", "cap": 5.0},
    {"bank": "建設銀行亞洲", "url": "https://www.ccb.com.hk/personal/deposits/", "cap": 5.0},
    {"bank": "滙豐銀行", "url": "https://www.hsbc.com.hk/accounts/rates/deposits/", "cap": 5.0},
    {"bank": "恒生銀行", "url": "https://www.hangseng.com/en-hk/personal/banking/interest-rates/deposit-rates/", "cap": 5.0},
    {"bank": "中銀香港", "url": "https://www.bochk.com/en/bank/rates/deposit-rates.html", "cap": 5.0},
    {"bank": "交通銀行", "url": "https://www.bankcomm.com.hk/", "cap": 5.0},
    {"bank": "花旗銀行", "url": "https://www.citibank.com.hk/personal-banking/deposits/", "cap": 5.0},
]

EXCLUDE = ["回贈", "獎賞", "現金", "apr", "cash", "rebate", "reward", "優惠", "信用卡", "簽賬", "消費", "最優惠利率", "prime"]
INCLUDE = ["年利率", "利率", "p.a.", "定期", "存款", "time deposit"]


def scrape_bank(cfg):
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=20)
        r.raise_for_status()
        text = BeautifulSoup(r.text, "html.parser").get_text(separator="\n")
        rates = []
        for line in text.split("\n"):
            low = line.strip().lower()
            if any(ex.lower() in low for ex in EXCLUDE):
                continue
            if any(inc.lower() in low for inc in INCLUDE):
                for m in re.findall(r"(\d+\.\d+)", low):
                    v = float(m)
                    if MIN_RATE <= v <= MAX_RATE and v <= cfg["cap"]:
                        rates.append(v)
        if rates:
            return {c: max(rates) for c in ["HKD", "USD", "RMB"]}
    except Exception as e:
        print(f"  {cfg['bank']}: {e}")
    return None


def main():
    print(f"Scraper started {datetime.now()}")
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
    for cfg in CONFIGS:
        result = scrape_bank(cfg)
        if result:
            scraped[cfg["bank"]] = result
            print(f"  {cfg['bank']}: {result}")

    for bank_name, cur_rates in scraped.items():
        for cur, banks in existing.items():
            if cur not in cur_rates:
                continue
            for bank in banks:
                if bank["bank"] == bank_name:
                    bank["bestRate"] = cur_rates[cur]
                    bank["note"] = "auto-scraped"
                    break

    for cur, banks in existing.items():
        for bank in banks:
            name = bank.get("bank", "")
            if name in BANK_URLS and not bank.get("url"):
                bank["url"] = BANK_URLS[name]

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rates": existing,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
