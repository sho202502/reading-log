#!/usr/bin/env python3
"""books.json に著者・出版社・出版年を補完する。

順番:
  1. 短縮URLの展開結果(data/cache/short_urls.json)を取り込んでISBNを確定させる
  2. ISBNがあるものは openBD で引く
  3. まだ著者が埋まらないものは 国立国会図書館サーチ をタイトルで引く

外部から取ったものは data/cache/ に全部貯める。二度目からは通信しない。
Amazonは短縮URLの展開にしか使わず、書誌そのものは openBD と NDL からしか取らない。
"""
import json, re, sys, time, pathlib, urllib.request, urllib.parse, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
OPENBD, NDL, SHORT = CACHE / "openbd.json", CACHE / "ndl.json", CACHE / "short_urls.json"

UA = {"User-Agent": "reading-log/1.0 (personal archive script)"}


def load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def tidy_author(s):
    """openBD/NDLの「姓,名,生年-」形式を人が読める形に直す。"""
    if not s:
        return None
    names = []
    for chunk in re.split(r"[ 　]+(?=[^ 　]*,)|,(?=[^,]*\s著)", s) if False else s.split(" "):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p for p in chunk.split(",") if p and not re.fullmatch(r"\d{4}-?\d{0,4}", p.strip())]
        names.append("".join(p.strip() for p in parts))
    out = " / ".join(dict.fromkeys(n for n in names if n))
    out = re.sub(r"\s*(著|編著|編|監修|訳)$", "", out).strip()
    return out or None


def isbn13_to_10(i):
    return i


def step_openbd(books, cache):
    want = sorted({b["isbn"] for b in books if b["isbn"] and b["isbn"] not in cache})
    print(f"openBD: {len(want)}件を照会 (キャッシュ {len(cache)})", flush=True)
    for i in range(0, len(want), 80):
        batch = want[i:i + 80]
        try:
            data = json.loads(fetch("https://api.openbd.jp/v1/get?isbn=" + ",".join(batch)))
        except Exception as e:
            print("  NG", type(e).__name__, flush=True)
            continue
        for isbn, rec in zip(batch, data):
            if not rec:
                cache[isbn] = None
                continue
            s = rec.get("summary", {}) or {}
            cache[isbn] = {"title": s.get("title"), "author": tidy_author(s.get("author")),
                           "publisher": s.get("publisher"), "pubdate": (s.get("pubdate") or "")[:4] or None}
        OPENBD.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {min(i+80, len(want))}/{len(want)}", flush=True)
        time.sleep(0.4)
    return cache


def ndl_search(title):
    """タイトルで引く。0件なら末尾の語を落として短くしながら再挑戦する。"""
    words = title.split()
    for cut in range(len(words), 0, -1):
        q = " ".join(words[:cut]).strip()
        if len(q) < 2:
            break
        url = "https://ndlsearch.ndl.go.jp/api/opensearch?" + urllib.parse.urlencode({"title": q, "cnt": 5})
        try:
            xml = fetch(url)
        except Exception:
            time.sleep(2)
            continue
        items = re.findall(r"<item>(.*?)</item>", xml, re.S)
        if not items:
            continue
        best = None
        for it in items:
            g = lambda t: (re.search(r"<%s[^>]*>(.*?)</%s>" % (re.escape(t), re.escape(t)), it, re.S) or [None, None])[1]
            t = (g("title") or "").strip()
            cand = {"title": t, "author": tidy_author(g("author")), "publisher": g("dc:publisher"),
                    "pubdate": ((g("dcterms:issued") or "")[:4] or None),
                    "isbn": (re.findall(r"<dc:identifier[^>]*ISBN[^>]*>([^<]*)</dc:identifier>", it) or [None])[0]}
            if not cand["author"]:
                continue
            if t == q or t.startswith(q):     # 完全一致・前方一致を優先
                return cand
            best = best or cand
        if best:
            return best
    return None


def step_ndl(books, cache):
    want = [b for b in books if not b["author"] and b["kind"] == "book" and b["title"] not in cache]
    print(f"NDL: {len(want)}件を照会 (キャッシュ {len(cache)})", flush=True)
    for i, b in enumerate(want, 1):
        cache[b["title"]] = ndl_search(b["title"])
        if i % 20 == 0:
            NDL.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {i}/{len(want)} 当たり{sum(1 for v in cache.values() if v)}", flush=True)
        time.sleep(1.0)
    NDL.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


def main():
    # --offline: 外部に一切問い合わせず、data/cache/ に貯めた分だけを反映する。
    # GitHub Actions はこちらで動かす（pushのたびにopenBDやNDLを叩かないため）。
    offline = "--offline" in sys.argv
    books = load(BOOKS, [])
    short = load(SHORT, {})

    # 1. 短縮URLからISBN/ASINを確定
    for b in books:
        if b["isbn"]:
            continue
        for u in b["short_urls"]:
            v = short.get(u)
            if not v:
                continue
            if v.startswith("B0"):
                b["asin"] = b["asin"] or v
            else:
                b["isbn"] = v
                break

    # 2. openBD
    ob = load(OPENBD, {})
    if not offline:
        ob = step_openbd(books, ob)
    for b in books:
        rec = ob.get(b["isbn"]) if b["isbn"] else None
        if rec and rec.get("author"):
            b["author"], b["publisher"], b["pubdate"], b["source"] = \
                rec["author"], rec.get("publisher"), rec.get("pubdate"), "openBD"

    # 3. NDL
    nd = load(NDL, {})
    if not offline:
        nd = step_ndl(books, nd)
    for b in books:
        if b["author"]:
            continue
        rec = nd.get(b["title"])
        if rec and rec.get("author"):
            b["author"], b["publisher"], b["pubdate"], b["source"] = \
                rec["author"], rec.get("publisher"), rec.get("pubdate"), "NDL"
            b["isbn"] = b["isbn"] or (rec.get("isbn") or "").replace("-", "") or None

    BOOKS.write_text(json.dumps(books, ensure_ascii=False, indent=1), encoding="utf-8")
    c = collections.Counter(b["source"] or "なし" for b in books)
    print("著者の出どころ:", dict(c))
    print(f"著者あり {sum(1 for b in books if b['author'])} / {len(books)}")


if __name__ == "__main__":
    main()
