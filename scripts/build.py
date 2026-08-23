#!/usr/bin/env python3
"""books.json から、全件が1ページに載るHTMLを生成する。

Ctrl+F を確実に効かせたいので、本文は折りたたまず全部DOMに置く(全体で約1.2MB)。
星での絞り込みと語での絞り込みはJSで行うが、初期状態は全件表示。
"""
import json, html, pathlib, collections, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"
DOCS = ROOT / "docs"

CSS = """
:root{--bg:#fbfaf8;--fg:#1d1c1a;--sub:#6d6a64;--line:#e2ded7;--accent:#8a6d3b;--card:#fff}
@media (prefers-color-scheme:dark){
 :root{--bg:#161513;--fg:#e6e3dd;--sub:#97928a;--line:#302e2a;--accent:#d4b483;--card:#1d1c1a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font-family:"Hiragino Mincho ProN","Yu Mincho",YuMincho,"Noto Serif JP",serif;
 line-height:1.9;font-size:16px;-webkit-text-size-adjust:100%}
header{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line);
 padding:.7rem 1rem;backdrop-filter:blur(6px)}
.wrap{max-width:44rem;margin:0 auto;padding:0 1rem}
h1{font-size:1.05rem;margin:0 0 .5rem;font-weight:600;letter-spacing:.04em}
h1 small{font-weight:400;color:var(--sub);font-size:.8rem;margin-left:.6rem;letter-spacing:0}
.controls{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}
button{font:inherit;font-size:.82rem;padding:.22rem .7rem;border:1px solid var(--line);
 border-radius:999px;background:var(--card);color:var(--sub);cursor:pointer}
button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
input[type=search]{font:inherit;font-size:.85rem;padding:.25rem .7rem;border:1px solid var(--line);
 border-radius:999px;background:var(--card);color:var(--fg);min-width:11rem;flex:1}
#count{font-size:.78rem;color:var(--sub);margin-left:auto;white-space:nowrap}
main{padding:1.5rem 0 6rem}
.year{font-size:.78rem;letter-spacing:.28em;color:var(--sub);margin:2.6rem 0 .8rem;
 border-bottom:1px solid var(--line);padding-bottom:.3rem}
.year:first-child{margin-top:0}
article{padding:1.3rem 0;border-bottom:1px solid var(--line)}
.meta{font-size:.75rem;color:var(--sub);display:flex;gap:.7rem;flex-wrap:wrap;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em}
.stars{color:var(--accent);letter-spacing:.1em;font-family:inherit}
h2{font-size:1.06rem;margin:.3rem 0 .15rem;font-weight:600;line-height:1.6}
.byline{font-size:.8rem;color:var(--sub);margin-bottom:.6rem}
.body{white-space:pre-wrap;overflow-wrap:anywhere}
.body a{color:var(--accent)}
.empty{color:var(--sub);font-size:.85rem;font-style:italic}
article.best{background:var(--card);border:1px solid var(--line);border-radius:.4rem;
 padding:1.3rem 1.2rem;margin:1.3rem 0}
.hide{display:none}
#nores{display:none;color:var(--sub);padding:3rem 0;text-align:center}
footer{color:var(--sub);font-size:.75rem;padding:2rem 0 4rem;border-top:1px solid var(--line)}
"""

JS = """
const arts=[...document.querySelectorAll('article')];
// 絞り込み用のテキストは、HTMLを二重に持たないよう読み込み時に組み立てる
for(const a of arts) a._find = a.textContent.toLowerCase();
const years=[...document.querySelectorAll('.year')];
const q=document.getElementById('q'), cnt=document.getElementById('count');
const nores=document.getElementById('nores');
let star=0;
function apply(){
  const t=q.value.trim().toLowerCase();
  let n=0;
  for(const a of arts){
    const okStar = star===0 || +a.dataset.rating===star;
    const okText = !t || a._find.includes(t);
    const ok = okStar && okText;
    a.classList.toggle('hide', !ok);
    if(ok) n++;
  }
  for(const y of years){
    let has=false;
    for(let e=y.nextElementSibling; e && e.tagName==='ARTICLE'; e=e.nextElementSibling)
      if(!e.classList.contains('hide')){has=true;break;}
    y.classList.toggle('hide', !has);
  }
  cnt.textContent = n + '件';
  nores.style.display = n ? 'none' : 'block';
}
document.querySelectorAll('[data-star]').forEach(b=>b.onclick=()=>{
  star = +b.dataset.star === star ? 0 : +b.dataset.star;
  document.querySelectorAll('[data-star]').forEach(x=>
    x.setAttribute('aria-pressed', +x.dataset.star===star));
  apply();
});
q.oninput=apply;
"""


def stars(n):
    return "★" * n + "☆" * (5 - n) if n else ""


def linkify_best(body, by_title):
    """年間ベストの本文のうち、書名と一致する行をその記事へのリンクにする。"""
    out = []
    for line in body.split("\n"):
        key = line.strip()
        hit = by_title.get(key)
        if hit:
            out.append(f'<a href="#{hit}">{html.escape(key)}</a>')
        else:
            out.append(html.escape(line))
    return "\n".join(out)


def main():
    books = json.loads(BOOKS.read_text(encoding="utf-8"))
    books.sort(key=lambda b: b["datetime"], reverse=True)

    # 年間ベストからのリンク先: 同じ書名の記事のうち一番新しいもの
    by_title = {}
    for b in sorted(books, key=lambda b: b["datetime"]):
        if b["kind"] == "book":
            by_title[b["title"]] = b["id"]

    parts, cur_year = [], None
    for b in books:
        y = b["date"][:4]
        if y != cur_year:
            cur_year = y
            parts.append(f'<div class="year">{y}</div>')

        meta = [b["date"]]
        if b["rating"]:
            meta.append(f'<span class="stars">{stars(b["rating"])}</span>')
        elif b["kind"] == "best":
            meta.append("年間ベスト")

        byline = " / ".join(x for x in [b.get("author"), b.get("publisher"), b.get("pubdate")] if x)

        if b["kind"] == "best":
            body_html = linkify_best(b["body"], by_title)
        elif b["body"]:
            body_html = html.escape(b["body"])
        else:
            body_html = '<span class="empty">（このときは感想を書き残していない）</span>'

        parts.append(
            f'<article id="{b["id"]}" class="{b["kind"]}" data-rating="{b["rating"] or 0}"'
            f'>'
            f'<div class="meta">{" ".join(meta)}</div>'
            f'<h2>{html.escape(b["title"])}</h2>'
            + (f'<div class="byline">{html.escape(byline)}</div>' if byline else "")
            + f'<div class="body">{body_html}</div></article>'
        )

    c = collections.Counter(b["rating"] for b in books if b["rating"])
    buttons = "".join(
        f'<button data-star="{n}" aria-pressed="false">{stars(n)[:n]} {c[n]}</button>'
        for n in (5, 4, 3, 2))

    built = datetime.date.today().isoformat()
    withauthor = sum(1 for b in books if b.get("author"))

    html_doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex">
<meta name="googlebot" content="noindex,nofollow">
<title>読書記録 by どぅ</title>
<style>{CSS}</style>
</head>
<body>
<header><div class="wrap">
<h1>読書記録 by どぅ<small>{len(books)}件 ／ {books[-1]["date"][:4]}–{books[0]["date"][:4]}</small></h1>
<div class="controls">
{buttons}
<input type="search" id="q" placeholder="書名・著者・本文で絞り込む" autocomplete="off">
<span id="count">{len(books)}件</span>
</div>
</div></header>
<main class="wrap">
{"".join(parts)}
<div id="nores">見つかりませんでした</div>
<footer>
FC2ブログ「読書記録 by どぅ」のアーカイブ。{built} 時点で {len(books)} 件。<br>
著者・出版社は <a href="https://openbd.jp/">openBD</a> と
<a href="https://ndlsearch.ndl.go.jp/">国立国会図書館サーチ</a> から補完（{withauthor} 件）。
</footer>
</main>
<script>{JS}</script>
</body>
</html>"""

    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html_doc, encoding="utf-8")
    (DOCS / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    size = (DOCS / "index.html").stat().st_size
    print(f"docs/index.html {size/1024/1024:.2f} MB / {len(books)}件 / 著者あり {withauthor}件")


if __name__ == "__main__":
    main()
