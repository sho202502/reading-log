#!/usr/bin/env python3
"""読んだ本を1冊、data/books.json に足す。

本文は標準入力から読む。

  python3 scripts/add.py "父の生きる" 5 <<'EOF'
  P121.父の本質は、私を可愛がってくれて…
  EOF

日付は今日。別の日にしたいときは --date 2026-08-20。
ISBNが分かっていれば --isbn を付けると、著者を引くのが確実になる。

足したあとは
  python3 scripts/enrich.py   # 著者・出版社・出版年を引いてくる
  python3 scripts/build.py    # HTMLを作り直す
"""
import argparse, json, pathlib, sys, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"


def main():
    ap = argparse.ArgumentParser(description="読んだ本を1冊足す")
    ap.add_argument("title", help="書名")
    ap.add_argument("rating", type=int, choices=range(1, 6), help="星の数(1〜5)")
    ap.add_argument("--date", help="読んだ日 YYYY-MM-DD（既定は今日）")
    ap.add_argument("--isbn", help="分かっていれば。著者を引くのが確実になる")
    ap.add_argument("--note", help="一言感想（任意）")
    args = ap.parse_args()

    body = sys.stdin.read().strip()
    if not body:
        sys.exit("本文が空です。標準入力から渡してください。")

    day = args.date or datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(day)
    except ValueError:
        sys.exit(f"日付の形が違います: {day}（YYYY-MM-DD）")

    books = json.loads(BOOKS.read_text(encoding="utf-8"))
    if any(b["title"] == args.title and b["date"] == day for b in books):
        sys.exit(f"同じ日に同じ書名が既にあります: {day} {args.title}")

    stamp = day.replace("-", "")
    n = 1
    used = {b["id"] for b in books}
    while f"{stamp}-{n}" in used:
        n += 1

    now = datetime.datetime.now().strftime("%H:%M:%S")
    books.append({
        "id": f"{stamp}-{n}",
        "title": args.title,
        "raw_title": args.title,
        "date": day,
        "datetime": f"{day}T{now}",
        "rating": args.rating,
        "category": "★" * args.rating + f"（{args.rating}）",
        "kind": "book",
        "isbn": args.isbn,
        "asin": None,
        "short_urls": [],
        "fc2_entries": [],
        "author": None,
        "publisher": None,
        "pubdate": None,
        "note": args.note,
        "source": None,
        "body": body,
    })
    books.sort(key=lambda b: b["datetime"])
    BOOKS.write_text(json.dumps(books, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"足しました: {day} ★{args.rating} {args.title}（全{len(books)}件）")
    print("つぎに: python3 scripts/enrich.py && python3 scripts/build.py")


if __name__ == "__main__":
    main()
