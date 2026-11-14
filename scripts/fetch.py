"""
抓取台股上市（TWSE）與上櫃（TPEx）全市場每日資料。

用法：
  python scripts/fetch.py                # 抓今天（若非交易日會自動略過）
  python scripts/fetch.py --date 20261113
  python scripts/fetch.py --backfill 90  # 回補最近 90 個日曆天（第一次部署用）

輸出：
  data/history/YYYYMMDD.json   每日價量、三大法人、融資餘額
  data/fund.json               最新基本面（本益比、殖利率、股價淨值比、月營收年增、產業）
"""
import argparse, datetime as dt, json, os, re, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "data", "history")
os.makedirs(HIST, exist_ok=True)

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
})
PAUSE = 3.5  # 證交所約每 5 秒 3 次上限，太快會被暫時封鎖


def log(*a):
    print(*a, flush=True)


def get(url, params=None, tries=3):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=40)
            time.sleep(PAUSE)
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    log("  非 JSON 回應:", url)
                    return None
            log(f"  HTTP {r.status_code}: {url}")
        except Exception as e:
            log(f"  連線錯誤 {e}: {url}")
        time.sleep(8 * (i + 1))
    return None


def clean(s):
    return re.sub(r"<[^>]+>", "", str(s)).strip()


def num(x):
    if x is None:
        return None
    s = clean(x).replace(",", "").replace("+", "").replace("%", "")
    if s in ("", "-", "--", "---", "X", "N/A", "除權", "除息"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def col(fields, *kws, prefer=None, avoid=None):
    """在欄位名稱中找出同時包含所有關鍵字的欄位索引。"""
    hits = []
    for i, f in enumerate(fields):
        f2 = clean(f)
        if all(k in f2 for k in kws) and not (avoid and any(a in f2 for a in avoid)):
            hits.append((i, f2))
    if not hits:
        return None
    if prefer:
        for i, f2 in hits:
            if prefer in f2:
                return i
    return hits[0][0]


def first(*xs):
    for x in xs:
        if x is not None:
            return x
    return None


def tables(js):
    """把證交所 / 櫃買各種 JSON 格式統一成 [(fields, rows)]。"""
    out = []
    if not isinstance(js, dict):
        return out
    if "tables" in js and isinstance(js["tables"], list):
        for t in js["tables"]:
            if isinstance(t, dict) and t.get("fields") and t.get("data"):
                out.append((t["fields"], t["data"]))
    if js.get("fields") and js.get("data"):
        out.append((js["fields"], js["data"]))
    for k in list(js.keys()):
        if re.match(r"fields\d+", k) and js.get("data" + k[6:]):
            out.append((js[k], js["data" + k[6:]]))
    return out


def find_table(js, *must):
    for f, d in tables(js):
        if all(col(f, m) is not None for m in must):
            return f, d
    return None, None


def is_target(code):
    # 一般股票（4 碼）與 ETF（00 開頭）；排除權證等
    return bool(re.fullmatch(r"[1-9]\d{3}", code) or re.fullmatch(r"00\d{2,3}[A-Z]?", code))


def pick(rec, *subs):
    """OpenAPI 回傳 dict：找出鍵名包含任一關鍵字的值。"""
    for s in subs:
        for k, v in rec.items():
            if s.lower() in k.lower():
                return v
    return None


# ---------------- 上市 TWSE ----------------
def twse_day(d):
    ds = d.strftime("%Y%m%d")
    out = {}
    js = get("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
             {"date": ds, "type": "ALLBUT0999", "response": "json"})
    if not js or js.get("stat") not in (None, "OK"):
        return {}
    f, rows = find_table(js, "證券代號", "收盤價")
    if not f:
        return {}
    ic, inm = col(f, "證券代號"), col(f, "證券名稱")
    io, ih, il, icl = col(f, "開盤價"), col(f, "最高價"), col(f, "最低價"), col(f, "收盤價")
    iv = col(f, "成交股數")
    for r in rows:
        code = clean(r[ic])
        if not is_target(code):
            continue
        c = num(r[icl])
        if c is None:
            continue
        out[code] = {"n": clean(r[inm]), "m": "L", "o": num(r[io]), "h": num(r[ih]),
                     "l": num(r[il]), "c": c, "v": num(r[iv]) or 0}
    # 三大法人
    js = get("https://www.twse.com.tw/rwd/zh/fund/T86",
             {"date": ds, "selectType": "ALLBUT0999", "response": "json"})
    f, rows = find_table(js, "證券代號", "投信")
    if f:
        ic = col(f, "證券代號")
        ifo = first(col(f, "外陸資買賣超股數"), col(f, "外資", "買賣超", prefer="不含"))
        itr = col(f, "投信買賣超")
        ide = first(col(f, "自營商買賣超股數", avoid=["自行", "避險", "外資"]), col(f, "自營商", "買賣超", avoid=["外資"]))
        for r in rows:
            code = clean(r[ic])
            if code in out:
                out[code]["f"] = num(r[ifo]) if ifo is not None else None
                out[code]["t"] = num(r[itr]) if itr is not None else None
                out[code]["d"] = num(r[ide]) if ide is not None else None
    # 融資
    js = get("https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN",
             {"date": ds, "selectType": "ALL", "response": "json"})
    f, rows = find_table(js, "代號", "今日餘額")
    if f:
        ic, im = col(f, "代號"), col(f, "今日餘額")  # 第一個「今日餘額」是融資
        for r in rows:
            code = clean(r[ic])
            if code in out:
                out[code]["mg"] = num(r[im])
    return out


# ---------------- 上櫃 TPEx ----------------
def tpex_day(d):
    ds = d.strftime("%Y/%m/%d")
    out = {}
    roc = f"{d.year - 1911}/{d:%m/%d}"
    js = get("https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php",
             {"l": "zh-tw", "d": roc, "se": "EW", "o": "json"})
    if not find_table(js, "代號", "收盤")[0]:
        js = get("https://www.tpex.org.tw/www/zh-tw/afterTrading/otc",
                 {"date": ds, "type": "EW", "response": "json"})
    f, rows = find_table(js, "代號", "收盤")
    if not f:
        return {}
    ic, inm = col(f, "代號"), col(f, "名稱")
    io, ih, il, icl = col(f, "開盤"), col(f, "最高"), col(f, "最低"), col(f, "收盤")
    iv = col(f, "成交股數")
    for r in rows:
        code = clean(r[ic])
        if not is_target(code):
            continue
        c = num(r[icl])
        if c is None:
            continue
        out[code] = {"n": clean(r[inm]), "m": "O", "o": num(r[io]), "h": num(r[ih]),
                     "l": num(r[il]), "c": c, "v": num(r[iv]) if iv is not None else 0}
    js = get("https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade",
             {"type": "Daily", "sect": "EW", "date": ds, "response": "json"})
    f, rows = find_table(js, "代號", "買賣超股數")
    if f:
        ic = col(f, "代號")
        # 欄位名稱重複，依位置：外資(不含外資自營商)、外資自營商、外資合計、投信、自營商自行、自營商避險、自營商合計
        occ = [i for i, x in enumerate(f) if "買賣超股數" in clean(x) and "合計" not in clean(x)]
        ifo, itr, ide = (occ[0], occ[3], occ[6]) if len(occ) >= 7 else (None, None, None)
        for r in rows:
            code = clean(r[ic])
            if code in out:
                out[code]["f"] = num(r[ifo]) if ifo is not None else None
                out[code]["t"] = num(r[itr]) if itr is not None else None
                out[code]["d"] = num(r[ide]) if ide is not None else None
    js = get("https://www.tpex.org.tw/www/zh-tw/margin/balance",
             {"date": ds, "response": "json"})
    f, rows = find_table(js, "代號", "資餘額")
    if f:
        ic = col(f, "代號")
        im = col(f, "資餘額", avoid=["前資", "前日"])
        for r in rows:
            code = clean(r[ic])
            if code in out and im is not None:
                out[code]["mg"] = num(r[im])
    return out


# ---------------- 基本面（只抓最新） ----------------
def fundamentals(d):
    fund = {}

    def put(code, **kw):
        code = clean(code)
        if not is_target(code):
            return
        rec = fund.setdefault(code, {})
        for k, v in kw.items():
            if v is not None:
                rec[k] = v

    # 上市 本益比/殖利率/淨值比
    js = get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL")
    if isinstance(js, list):
        for r in js:
            put(pick(r, "Code", "證券代號") or "", pe=num(pick(r, "PEratio", "本益比")),
                yld=num(pick(r, "DividendYield", "殖利率")), pb=num(pick(r, "PBratio", "淨值比")))
    # 上櫃 本益比
    js = get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis")
    if isinstance(js, list):
        for r in js:
            put(pick(r, "SecuritiesCompanyCode", "Code", "代號") or "",
                pe=num(pick(r, "PriceEarningRatio", "PEratio", "本益比")),
                yld=num(pick(r, "YieldRatio", "DividendYield", "殖利率")),
                pb=num(pick(r, "PriceBookRatio", "PBratio", "淨值比")))
    # 月營收（上市 + 上櫃）
    for url in ("https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
                "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"):
        js = get(url)
        if isinstance(js, list):
            for r in js:
                put(pick(r, "公司代號", "Code") or "",
                    rev=num(pick(r, "去年同月增減")), revc=num(pick(r, "前期比較增減")),
                    ind=clean(pick(r, "產業別") or "") or None)
    # 產業別補充（上市/上櫃公司基本資料）
    for url in ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
                "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"):
        js = get(url)
        if isinstance(js, list):
            for r in js:
                code = clean(pick(r, "公司代號", "Code") or "")
                if code in fund and fund[code].get("ind"):
                    continue
                put(code, ind=clean(pick(r, "產業別") or "") or None)
    return fund


def fetch_date(d):
    log(f"== {d:%Y-%m-%d} ==")
    a = twse_day(d)
    log(f"  上市 {len(a)} 檔")
    b = tpex_day(d)
    log(f"  上櫃 {len(b)} 檔")
    if not a and not b:
        log("  無資料（休市或尚未公布）")
        return False
    a.update(b)
    with open(os.path.join(HIST, d.strftime("%Y%m%d") + ".json"), "w", encoding="utf-8") as fp:
        json.dump(a, fp, ensure_ascii=False, separators=(",", ":"))
    return True


def taipei_today():
    return (dt.datetime.utcnow() + dt.timedelta(hours=8)).date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--backfill", type=int, default=0)
    ap.add_argument("--skip-fund", action="store_true")
    a = ap.parse_args()
    today = dt.datetime.strptime(a.date, "%Y%m%d").date() if a.date else taipei_today()
    got = 0
    if a.backfill:
        for i in range(a.backfill, -1, -1):
            d = today - dt.timedelta(days=i)
            if d.weekday() >= 5:
                continue
            if os.path.exists(os.path.join(HIST, d.strftime("%Y%m%d") + ".json")):
                continue
            got += fetch_date(d)
    elif today.weekday() < 5:
        got += fetch_date(today)
    if not a.skip_fund:
        fund = fundamentals(today)
        if fund:
            with open(os.path.join(ROOT, "data", "fund.json"), "w", encoding="utf-8") as fp:
                json.dump(fund, fp, ensure_ascii=False, separators=(",", ":"))
            log(f"基本面 {len(fund)} 檔")
    # 只保留最近 200 個檔案
    files = sorted(os.listdir(HIST))
    for fn in files[:-200]:
        os.remove(os.path.join(HIST, fn))
    log(f"完成，新增 {got} 個交易日")


if __name__ == "__main__":
    main()
