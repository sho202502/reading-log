#!/usr/bin/env python3
"""books.json に著者・出版社・出版年を補完する。

順番:
  1. 短縮URLの展開結果(data/cache/short_urls.json)を取り込んでISBNを確定させる
  2. ISBNがあるものは openBD で引く
  3. まだ著者が埋まらないものは 国立国会図書館サーチ をタイトルで引く

外部から取ったものは data/cache/ に全部貯める。二度目からは通信しない。
Amazonは短縮URLの展開にしか使わず、書誌そのものは openBD と NDL からしか取らない。
"""
import json, re, sys, time, subprocess, unicodedata, pathlib, urllib.request, urllib.parse, collections
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
OPENBD, NDL, SHORT = CACHE / "openbd.json", CACHE / "ndl.json", CACHE / "short_urls.json"
NDL_ISBN = CACHE / "ndl_isbn.json"

UA = {"User-Agent": "reading-log/1.0 (personal archive script)"}


def load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def fetch(url, timeout=45):
    """curl経由で取る。

    ndlsearch.ndl.go.jp は複数のIPを返し、urllib は掴んだ1つで待ち続けて
    ハングすることがある(1件あたり40秒のタイムアウト待ちになっていた)。
    curlは別のアドレスに切り替えてくれるので、こちらを使う。
    """
    r = subprocess.run(
        ["curl", "-s", "-S", "-L", "--max-time", str(timeout), "--retry", "2",
         "-A", UA["User-Agent"], url],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl {r.returncode}: {r.stderr.strip()[:80]}")
    return r.stdout


YEAR = re.compile(r"^\d{4}-?\d{0,4}$")
ROLE = re.compile(r"\s*(著者|編著|共著|編訳|監修|訳者|著|編|訳|画|作)\s*$")


def clean_name(s):
    """『沢村, 香苗, 1976-』『山田太郎 著』のような1人ぶんの表記を、名前だけにする。"""
    if not s:
        return None
    s = re.sub(r"[\[\]〔〕（）()]", " ", s)
    parts = []
    for p in s.split(","):
        p = ROLE.sub("", p.strip()).strip()
        if p and not YEAR.match(p):
            parts.append(p)
    if not parts:
        return None
    # 欧文は「姓, 名」の順で入っているので入れ替える
    if all(re.fullmatch(r"[A-Za-z .'\-]+", p) for p in parts):
        return " ".join(reversed(parts)).strip()
    return "".join(parts)


def join_authors(names):
    out = [n for n in (clean_name(x) for x in names) if n]
    return " / ".join(dict.fromkeys(out)) or None


def tidy_author(s):
    """openBDの author は「姓,名,生年- 姓,名,生年-」と空白で人が並ぶ。"""
    if not s:
        return None
    return join_authors(s.split(" ") if re.search(r"\d{4}-", s) else [s])


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


NDL_PUNCT = re.compile(r"[\s!-/:-@\[-`{-~！-／：-＠［-｀｛-～、。「」『』・ー－―~〜]")


def nkey(s):
    """書名の突き合わせ用キー。全角半角・空白・記号を落とす。"""
    return NDL_PUNCT.sub("", unicodedata.normalize("NFKC", s or "")).lower()


def ndl_items(xml):
    """OpenSearchのRSSを、候補のリストに変換する(選別は後段でやる)。"""
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        g = lambda t: (re.search(r"<%s[^>]*>(.*?)</%s>" % (re.escape(t), re.escape(t)), it, re.S) or [None, None])[1]
        out.append({
            "title": (g("title") or "").strip(),
            # <author> は複数の表記が混ざって潰れているので、1人ずつ入っている
            # <dc:creator> を使う。無いときだけ <author> にたよる。
            "author": (join_authors(re.findall(r"<dc:creator>(.*?)</dc:creator>", it, re.S))
                       or tidy_author(g("author"))),
            "publisher": g("dc:publisher"),
            "pubdate": ((g("dcterms:issued") or "")[:4] or None),
            "isbn": (re.findall(r"<dc:identifier[^>]*ISBN[^>]*>([^<]*)</dc:identifier>", it) or [None])[0],
            "cats": re.findall(r"<category>(.*?)</category>", it),
        })
    return out


def ndl_query(params):
    url = "https://ndlsearch.ndl.go.jp/api/opensearch?" + urllib.parse.urlencode(params)
    try:
        return ndl_items(fetch(url))
    except Exception:
        return []


def title_ok(cand_title, want):
    """NDL側の書名と、こちらの書名が同じ本を指していそうか。

    NDLの書名は「本題 : 副題」の形なので、本題だけでも突き合わせる
    (「バカと無知」と「バカと無知 : 人間、この不都合な生きもの」は同じ本)。
    逆に、短い書名がたまたま長い書名の一部に入っているだけのもの
    (「シフト」と「RPAで成功する会社…にシフト」)は落とす。
    """
    b = nkey(want)
    for t in (cand_title, re.split(r"\s*[:：]\s*", cand_title)[0]):
        a = nkey(t)
        if not a or not b or not (a in b or b in a):
            continue
        lo, hi = sorted((len(a), len(b)))
        if lo >= 4 and lo / hi >= 0.5:
            return True
    return False


def pick(cands, want_title=None):
    """候補から1件選ぶ。

    NDLのタイトル検索は、その本を論じた雑誌記事や書評まで拾ってくる
    (「シフト」で「アーカイブズ私論」が返るような外れ方をする)。
    なので図書のレコードに限り、さらに書名が実際に噛み合うものだけを採る。
    """
    for c in cands:
        if not c["author"]:
            continue
        if want_title is not None:
            if "図書" not in c["cats"]:
                continue
            if not title_ok(c["title"], want_title):
                continue
        return {k: c[k] for k in ("title", "author", "publisher", "pubdate", "isbn")}
    return None


def ndl_search(title):
    """タイトルで引いて候補を集める。

    NDLは全角英数(ＡＩ)や全角空白をそのままでは拾えないので、NFKCで正規化した形も試す。
    長い書名も当たらないため、頭から3語・1語と短くしながら順に投げる。
    当たった候補はそのまま貯めておき、選別はキャッシュを読み直すときに毎回やる。
    """
    norm = unicodedata.normalize("NFKC", title).replace("\u3000", " ").strip()
    words = norm.split()
    queries = [title]
    if norm != title:
        queries.append(norm)
    if len(words) > 3:
        queries.append(" ".join(words[:3]))
    if len(words) > 1:
        queries.append(words[0])
    found, seen = [], set()
    for q in dict.fromkeys(queries):
        if len(q) < 2:
            continue
        for c in ndl_query({"title": q, "cnt": 10}):
            k = (c["title"], c["author"])
            if k not in seen:
                seen.add(k)
                found.append(c)
        if pick(found, want_title=title):
            break
    return found


# NDLは1件あたり30〜40秒かかることがある(CloudFrontに乗っていない問い合わせ)。
# 逐次だと数時間になるので少しだけ並べて投げる。相手に負荷をかけすぎない範囲。
WORKERS = 6


def run_pool(keys, work, cache, path, label):
    """keys を並列に処理して cache に入れる。途中で落ちてもキャッシュは残す。"""
    print(f"{label}: {len(keys)}件を照会", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for key, val in zip(keys, ex.map(work, keys)):
            cache[key] = val
            done += 1
            if done % 20 == 0:
                path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  {done}/{len(keys)} 当たり{sum(1 for v in cache.values() if v)}", flush=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


def step_ndl_isbn(books, cache):
    """openBDが持っていなかったISBNを、NDLにISBNで問い合わせる(タイトル検索より確実)。"""
    ob = load(OPENBD, {})
    want = sorted({b["isbn"] for b in books
                   if b["isbn"] and not (ob.get(b["isbn"]) or {}).get("author") and b["isbn"] not in cache})
    return run_pool(want, lambda i: ndl_query({"isbn": i}), cache, NDL_ISBN, "NDL(ISBN)")


def step_ndl(books, cache, retry=False):
    # retry=True のときは、前回空振りした分(タイムアウト含む)をもう一度だけ引き直す
    want = sorted({b["title"] for b in books
                   if not b["author"] and b["kind"] == "book"
                   and (b["title"] not in cache or (retry and cache[b["title"]] is None))})
    return run_pool(want, ndl_search, cache, NDL, "NDL(タイトル)")


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

    # 3. openBDが取りこぼしたISBNを NDL にISBNで問い合わせる
    ni = load(NDL_ISBN, {})
    if not offline:
        ni = step_ndl_isbn(books, ni)
    for b in books:
        if b["author"]:
            continue
        rec = pick(ni.get(b["isbn"]) or []) if b["isbn"] else None
        if rec and rec.get("author"):
            b["author"], b["publisher"], b["pubdate"], b["source"] = \
                rec["author"], rec.get("publisher"), rec.get("pubdate"), "NDL"

    # 4. それでも残るものはタイトルで引く
    nd = load(NDL, {})
    if not offline:
        nd = step_ndl(books, nd, retry="--retry" in sys.argv)
    for b in books:
        if b["author"]:
            continue
        rec = pick(nd.get(b["title"]) or [], want_title=b["title"])
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
