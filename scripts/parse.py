#!/usr/bin/env python3
"""MT形式のエクスポート(data/dokushop.txt)を books.json に変換する。

残すもの: タイトル / 日付 / 星評価 / 著者・出版社の手掛かり / 本文
Amazonのアフィリエイトタグ・iframe・計測ピクセルは全部捨て、URL内のISBNだけ回収する。
"""
import re, json, html, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "dokushop.txt"
OUT = ROOT / "data" / "books.json"

# 12/14/1901 は明らかな入力ミス。前後の記事がいずれも 2022-12-31 なのでそこに寄せる。
DATE_FIXES = {"12/14/1901 05:45:52": "12/31/2022 05:45:52"}

# 本文中のURLからISBN-10 / Kindle ASIN を拾うパターン
ID_PATTERNS = [
    r"/dp/([0-9]{9}[0-9Xx])", r"asins=([0-9]{9}[0-9Xx])",
    r"gp/product/([0-9]{9}[0-9Xx])", r"creativeASIN=([0-9]{9}[0-9Xx])",
    r"[?&]a=([0-9]{9}[0-9Xx])",
]
ASIN_PATTERNS = [
    r"/dp/(B0[0-9A-Z]{8})", r"asins=(B0[0-9A-Z]{8})",
    r"gp/product/(B0[0-9A-Z]{8})", r"creativeASIN=(B0[0-9A-Z]{8})",
    r"[?&]a=(B0[0-9A-Z]{8})",
]
SHORT_RE = re.compile(r"https?://(?:amzn\.asia|amzn\.to)/[0-9A-Za-z/]+")
FC2_RE = re.compile(r"https?://dokushop\.blog134\.fc2\.com/blog-entry-(\d+)\.html?")

# 捨てるHTML
DROP_BLOCK = re.compile(
    r"<iframe\b.*?</iframe>|<script\b.*?</script>|<noscript\b.*?</noscript>", re.S | re.I)
AMAZON_HOST = re.compile(
    r"amazon\.co\.jp|amazon\.com|amzn\.|assoc-amazon|amazon-adsystem|rcm-jp|rcm-fe|blogranking\.fc2", re.I)


def field(block, key):
    m = re.search(r"^%s: (.*)$" % key, block, re.M)
    return m.group(1).strip() if m else ""


def parse_rating(cat):
    """PRIMARY CATEGORY から星の数を得る。未分類・ベストは None。"""
    n = cat.count("★")
    return n if n else None


def clean_body(raw):
    """Amazon関連の残骸を落として、素のテキストに戻す。"""
    t = DROP_BLOCK.sub("", raw)
    # Amazonへのアンカーは中身ごと削除（リンクテキストがURLそのものの場合が多い）
    t = re.sub(r"<a\b[^>]*>(.*?)</a>", lambda m: "" if AMAZON_HOST.search(m.group(0)) else m.group(1), t, flags=re.S | re.I)
    # 画像は全部捨てる（読書記録以外をやっていた頃の名残で、参照先もFC2上にある）
    t = re.sub(r"<img\b[^>]*>", "", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</?(p|div)\b[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)                    # 残りのタグを除去
    t = html.unescape(t)
    # 裸のAmazon URLが残っていれば消す
    t = re.sub(r"https?://\S*(?:amazon|amzn)\S*", "", t, flags=re.I)
    t = re.sub(r"[ \t　]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


BOOK_PREFIX = re.compile(r"^[ 　]*[【『\[（(][ 　]*本[ 　]*[】』\]）)][ 　]*")
BODY_TITLE = re.compile(r"^[ 　]*題名[：:][ 　]*(.+?)[ 　]*$", re.M)
BODY_AUTHOR = [
    re.compile(r"^[ 　]*(?:著者|作者)[：:][ 　]*(.+?)[ 　]*$", re.M),
    re.compile(r"^[ 　]*(.{2,30}?)[ 　]*[（(][ 　]*著[ 　]*[）)]", re.M),
]


def split_headline(title):
    """『本』 一言感想 / 書名 の形式なら、書名と一言感想に分ける。"""
    t = BOOK_PREFIX.sub("", title).strip()
    if " / " in t:
        note, _, name = t.rpartition(" / ")
        if len(name) >= 2:
            return name.strip(), note.strip() or None
    return t, None


def body_author(body):
    for p in BODY_AUTHOR:
        m = p.search(body)
        if m:
            a = re.sub(r"\s*[（(].*?[）)]\s*$", "", m.group(1)).strip()
            a = re.sub(r"[ 　]+", " ", a)
            if 1 < len(a) <= 40 and not re.search(r"[。、！？]", a):
                return a
    return None


def title_hints(title):
    """初期の記事は「書名（著者）出版社」形式。分解できれば著者と出版社を返す。"""
    m = re.match(r"^(.*?)[（(]([^（）()]{1,30})[）)]\s*(.{0,25})$", title)
    if not m:
        return title, None, None
    name, author, publisher = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    if not name or re.search(r"[0-9]{4}年", author):
        return title, None, None
    # 「書名（著者）出版社」は出版社が短い一語で終わる形。
    # 空白が入るもの、長いもの、閉じ括弧で続くものは、書名の一部でしかない。
    #   例: 科学的根拠（エビデンス）で子育て 教育経済学の最前線 / 男の「外見(ヴィジュアル)」コーチング
    if not publisher or " " in publisher or "　" in publisher or len(publisher) > 12:
        return title, None, None
    if publisher[0] in "」』】\"'":
        return title, None, None
    return name, author, publisher or None


def main():
    raw = SRC.read_text(encoding="utf-8")
    blocks = [b for b in raw.split("\n--------\n") if "TITLE:" in b]
    books, seen = [], set()

    for block in blocks:
        title = field(block, "TITLE")
        date_s = field(block, "DATE")
        date_s = DATE_FIXES.get(date_s, date_s)
        cat = field(block, "PRIMARY CATEGORY")
        m = re.search(r"\nBODY:\n(.*?)\n-----\nEXTENDED BODY:", block, re.S)
        body_raw = m.group(1) if m else ""

        mm, dd, rest = date_s.split("/")
        yyyy, time_s = rest.split(" ", 1)
        iso = f"{yyyy}-{mm}-{dd}T{time_s}"

        isbn, asin = set(), set()
        for p in ID_PATTERNS:
            isbn.update(x.upper() for x in re.findall(p, body_raw))
        for p in ASIN_PATTERNS:
            asin.update(re.findall(p, body_raw))

        body_text = clean_body(body_raw)

        # 書名は「本文の題名：」→「『本』一言 / 書名」→「書名（著者）出版社」の順に信用する
        headline, note = split_headline(title)
        m_bt = BODY_TITLE.search(body_text)
        clean_title, author, publisher = title_hints(headline)
        if m_bt:
            clean_title = m_bt.group(1)
        author = author or body_author(body_text)

        bid = f"{yyyy}{mm}{dd}"
        n = 1
        while f"{bid}-{n}" in seen:
            n += 1
        bid = f"{bid}-{n}"
        seen.add(bid)

        books.append({
            "id": bid,
            "title": clean_title,
            "raw_title": title,
            "date": f"{yyyy}-{mm}-{dd}",
            "datetime": iso,
            "rating": parse_rating(cat),
            "category": cat,
            "kind": "best" if cat == "ベスト" else "book",
            "isbn": sorted(isbn)[0] if isbn else None,
            "asin": sorted(asin)[0] if asin else None,
            "short_urls": sorted(set(SHORT_RE.findall(body_raw))),
            "fc2_entries": sorted(set(FC2_RE.findall(body_raw)), key=int),
            "author": author,
            "publisher": publisher,
            "pubdate": None,
            "note": note,
            "source": "元記事" if author else None,
            "body": body_text,
        })

    books.sort(key=lambda b: b["datetime"])
    OUT.write_text(json.dumps(books, ensure_ascii=False, indent=1), encoding="utf-8")

    c = collections.Counter()
    for b in books:
        c["ISBNあり" if b["isbn"] else ("短縮URLのみ" if b["short_urls"] else ("ASINのみ" if b["asin"] else "手掛かりなし"))] += 1
    print(f"{len(books)}件 -> {OUT.relative_to(ROOT)}")
    print("  ISBN手掛かり:", dict(c))
    print("  星の分布:", dict(collections.Counter(b["rating"] for b in books)))
    print("  著者が元記事から取れた:", sum(1 for b in books if b["author"]))
    print("  一言感想あり:", sum(1 for b in books if b["note"]))
    print("  本文が空:", sum(1 for b in books if not b["body"]))


if __name__ == "__main__":
    main()
