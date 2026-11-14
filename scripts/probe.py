"""測試櫃買中心各網址是否可用，印出欄位名稱（除錯用）。"""
import requests, json, time
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"
D, R = "2026/11/13", "115/11/13"
U = [
 ("q_new_otc", "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc", {"date": D, "type": "EW", "response": "json"}),
 ("q_new_dailyQ", "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQ", {"date": D, "type": "EW", "response": "json"}),
 ("q_legacy", "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php", {"l": "zh-tw", "d": R, "se": "EW", "o": "json"}),
 ("i_new", "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade", {"type": "Daily", "sect": "EW", "date": D, "response": "json"}),
 ("i_legacy", "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php", {"l": "zh-tw", "se": "EW", "t": "D", "d": R, "o": "json"}),
 ("m_new", "https://www.tpex.org.tw/www/zh-tw/margin/balance", {"date": D, "response": "json"}),
 ("m_legacy", "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php", {"l": "zh-tw", "d": R, "o": "json"}),
 ("oa_quotes", "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes", None),
 ("oa_3insti", "https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading", None),
 ("oa_margin", "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance", None),
 ("twse_t86", "https://www.twse.com.tw/rwd/zh/fund/T86", {"date": "20261113", "selectType": "ALLBUT0999", "response": "json"}),
]
for name, url, p in U:
    try:
        r = S.get(url, params=p, timeout=30); time.sleep(3)
        print(f"### {name} HTTP {r.status_code} final={r.url[:140]}")
        try:
            js = r.json()
        except Exception:
            print("   not json:", r.text[:200].replace("\n", " ")); continue
        if isinstance(js, list):
            print("   list", len(js), "keys:", list(js[0].keys()) if js else None)
            if js: print("   row0:", json.dumps(js[0], ensure_ascii=False)[:400])
        else:
            print("   keys:", list(js.keys())[:20])
            for t in (js.get("tables") or []):
                print("   table fields:", t.get("fields"), "rows:", len(t.get("data") or []))
                if t.get("data"): print("   row0:", t["data"][0])
            for k in ("fields", "aaData", "data"):
                if k in js and js[k]:
                    print(f"   {k}:", (js[k] if k == "fields" else js[k][0]))
    except Exception as e:
        print(f"### {name} ERR {e}")
