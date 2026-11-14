import requests, time, json
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"
def show(name, url, p, code="6488"):
    try:
        r = S.get(url, params=p, timeout=30); time.sleep(3)
        js = r.json()
        rows = []
        for t in (js.get("tables") or []): rows += t.get("data") or []
        rows += js.get("aaData") or js.get("data") or []
        hit = [x for x in rows if isinstance(x, list) and x and str(x[0]).strip() == code]
        print(f"### {name} {p} HTTP {r.status_code} url={r.url[:120]} date={js.get('date') or js.get('reportDate')} rows={len(rows)} row={hit[0][:12] if hit else None}")
    except Exception as e:
        print(f"### {name} {p} ERR {e}")
for D, R in (("2026/07/20", "115/07/20"), ("2026/11/13", "115/11/13")):
    show("otc", "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc", {"date": D, "type": "EW", "response": "json"})
    show("otc_id", "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc", {"date": D, "id": "", "response": "json"})
    show("legacy", "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php", {"l": "zh-tw", "d": R, "se": "EW", "o": "json"})
    show("legacy_AL", "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php", {"l": "zh-tw", "d": R, "se": "AL", "o": "json"})
    show("insti", "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade", {"type": "Daily", "sect": "EW", "date": D, "response": "json"})
    show("insti_legacy", "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php", {"l": "zh-tw", "se": "EW", "t": "D", "d": R, "o": "json"})
    show("margin", "https://www.tpex.org.tw/www/zh-tw/margin/balance", {"date": D, "response": "json"})
    show("margin_legacy", "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php", {"l": "zh-tw", "d": R, "o": "json"})
    show("stk_month", "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock", {"code": "6488", "date": D, "response": "json"})
