#!/usr/bin/env python3
"""amzn.asia / amzn.to の短縮URLを1回だけ展開して、ISBN(またはASIN)を回収する。

結果は data/cache/short_urls.json に貯める。キャッシュにあるURLは二度と叩かない。
著者・出版社の取得そのものは openBD / NDLサーチ が担当し、Amazonのページ内容は一切読まない。
"""
import json, re, time, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "short_urls.json"
CACHE.parent.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
ID_RE = re.compile(r"/(?:dp|gp/product)/([0-9]{9}[0-9Xx]|B0[0-9A-Z]{8})")


def main():
    books = json.loads((ROOT / "data" / "books.json").read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    todo = [u for b in books for u in b["short_urls"] if u not in cache]
    print(f"対象 {len(todo)} 件 (キャッシュ済み {len(cache)} 件)", flush=True)

    for i, url in enumerate(todo, 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                final = r.geturl()
            m = ID_RE.search(final)
            cache[url] = m.group(1).upper() if m else None
        except Exception as e:
            cache[url] = None
            print(f"  NG {url} {type(e).__name__}", flush=True)
        if i % 25 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            got = sum(1 for v in cache.values() if v)
            print(f"  {i}/{len(todo)} 取得済み{got}", flush=True)
        time.sleep(0.6)

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    isbn = sum(1 for v in cache.values() if v and not v.startswith("B0"))
    asin = sum(1 for v in cache.values() if v and v.startswith("B0"))
    print(f"完了: ISBN {isbn} / KindleASIN {asin} / 取得不可 {sum(1 for v in cache.values() if not v)}")


if __name__ == "__main__":
    main()
