"""
讀取 data/history/*.json 與 data/fund.json，計算每檔技術與籌碼指標，
輸出 docs/data/latest.json 給網頁使用。評分與價位在網頁端依使用者設定即時計算。
"""
import json, math, os, glob
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "data", "history")
OUT = os.path.join(ROOT, "docs", "data", "latest.json")
LOOKBACK = 250
SPARK = 60


def r(x, n=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), n)


def ema(a, n):
    k = 2 / (n + 1)
    out = np.empty_like(a)
    out[0] = a[0]
    for i in range(1, len(a)):
        out[i] = a[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(c, n=14):
    if len(c) <= n:
        return None
    d = np.diff(c)
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    au, ad = up[:n].mean(), dn[:n].mean()
    for i in range(n, len(d)):
        au = (au * (n - 1) + up[i]) / n
        ad = (ad * (n - 1) + dn[i]) / n
    return 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)


def kd(h, l, c, n=9):
    if len(c) < n:
        return None, None
    k = d = 50.0
    for i in range(n - 1, len(c)):
        hh, ll = h[i - n + 1:i + 1].max(), l[i - n + 1:i + 1].min()
        rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
    return k, d


def streak(arr):
    """由最近一天往回數連續買超（正）或賣超（負）天數。"""
    s = 0
    for x in reversed(arr):
        if x is None or x == 0:
            break
        if s == 0:
            s = 1 if x > 0 else -1
        elif (x > 0) == (s > 0):
            s += 1 if s > 0 else -1
        else:
            break
    return s


def main():
    files = sorted(glob.glob(os.path.join(HIST, "*.json")))[-LOOKBACK:]
    if not files:
        raise SystemExit("沒有歷史資料，請先執行 fetch.py --backfill 90")
    days = []
    for fn in files:
        with open(fn, encoding="utf-8") as fp:
            days.append((os.path.basename(fn)[:8], json.load(fp)))
    last_date, last = days[-1]
    fund = {}
    fp_ = os.path.join(ROOT, "data", "fund.json")
    if os.path.exists(fp_):
        with open(fp_, encoding="utf-8") as fp:
            fund = json.load(fp)

    kdir = os.path.join(ROOT, "docs", "data", "k")
    os.makedirs(kdir, exist_ok=True)
    dates = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d, _ in days]
    stocks = []
    for code, cur in last.items():
        # 每檔的日K資料（給網頁畫 K 線、KD、MACD 等）
        k = {"t": [], "o": [], "h": [], "l": [], "c": [], "v": [], "f": [], "tr": [], "dl": []}
        for dstr, (_, dd) in zip(dates, days):
            x = dd.get(code)
            if not x:
                continue
            k["t"].append(dstr); k["c"].append(x["c"])
            k["o"].append(x.get("o") or x["c"]); k["h"].append(x.get("h") or x["c"]); k["l"].append(x.get("l") or x["c"])
            k["v"].append(round((x.get("v") or 0) / 1000))
            for a, b in (("f", "f"), ("tr", "t"), ("dl", "d")):
                k[a].append(round(x[b] / 1000) if x.get(b) is not None else None)
        with open(os.path.join(kdir, code + ".json"), "w", encoding="utf-8") as fp:
            json.dump(k, fp, separators=(",", ":"))
        seq = [dd[code] for _, dd in days if code in dd]
        if len(seq) < 2:
            continue
        c = np.array([x["c"] for x in seq], float)
        h = np.array([x.get("h") or x["c"] for x in seq], float)
        l = np.array([x.get("l") or x["c"] for x in seq], float)
        v = np.array([x.get("v") or 0 for x in seq], float)
        ma = lambda n: c[-n:].mean() if len(c) >= n else None
        macd_h = None
        if len(c) >= 35:
            dif = ema(c, 12) - ema(c, 26)
            macd_h = (dif - ema(dif, 9))[-1]
        k, d = kd(h, l, c)
        lr = np.diff(np.log(c[-61:]))
        vol = lr.std(ddof=1) * math.sqrt(252) * 100 if len(lr) >= 10 else None
        f_ = [x.get("f") for x in seq]
        t_ = [x.get("t") for x in seq]
        inst5 = None
        if len(seq) >= 5:
            net = sum((x.get("f") or 0) + (x.get("t") or 0) + (x.get("d") or 0) for x in seq[-5:])
            vv = v[-5:].sum()
            inst5 = net / vv * 100 if vv > 0 else None
        margin5 = None
        mg = [x.get("mg") for x in seq]
        if len(mg) >= 6 and mg[-1] is not None and mg[-6]:
            margin5 = (mg[-1] - mg[-6]) / mg[-6] * 100
        fd = fund.get(code, {})
        pe, pb = fd.get("pe"), fd.get("pb")
        roe = pb / pe * 100 if pe and pb and pe > 0 else None
        prev = c[-2]
        stocks.append({
            "code": code, "name": cur["n"], "mkt": cur["m"], "ind": fd.get("ind") or ("ETF" if code.startswith("00") else ""),
            "etf": code.startswith("00"),
            "close": r(c[-1]), "chg": r((c[-1] / prev - 1) * 100),
            "ma5": r(ma(5)), "ma20": r(ma(20)), "ma60": r(ma(60)),
            "rsi": r(rsi(c), 1), "k": r(k, 1), "d": r(d, 1), "macd": r(macd_h, 3),
            "vol": r(vol, 1), "lots": r(v[-20:].mean() / 1000, 0), "vr": r(v[-1] / v[-20:].mean(), 2) if v[-20:].mean() > 0 else None,
            "fs": streak(f_), "ts": streak(t_),
            "inst": r(inst5), "margin": r(margin5),
            "pe": r(pe), "pb": r(pb), "yld": r(fd.get("yld")), "roe": r(roe, 1),
            "rev": r(fd.get("rev"), 1), "revc": r(fd.get("revc"), 1),
            "hi60": r(c[-60:].max()), "lo60": r(c[-60:].min()),
            "spark": [r(x) for x in c[-SPARK:]],
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = {"date": f"{last_date[:4]}/{last_date[4:6]}/{last_date[6:]}", "days": len(days),
           "count": len(stocks), "stocks": stocks}
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
    print(f"輸出 {len(stocks)} 檔，資料日 {out['date']}，使用 {len(days)} 個交易日")


if __name__ == "__main__":
    main()
