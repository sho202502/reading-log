#!/usr/bin/env python3
"""books.json から、全件が1ページに載るHTMLを生成する。

Ctrl+F を確実に効かせたいので、本文は折りたたまず全部DOMに置く(全体で約1.2MB)。
星での絞り込みと語での絞り込みはJSで行うが、初期状態は全件表示。
"""
import json, html, re, unicodedata, pathlib, collections, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "books.json"
DOCS = ROOT / "docs"

CSS = """
/* 読むための画面なので配色は明るい方に固定する（端末の暗い設定に引きずられない） */
:root{color-scheme:light;
 --bg:#fdfcfa;--fg:#1c1b19;--sub:#6b6862;--line:#e6e2db;--accent:#8a6d3b;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font-family:"Hiragino Mincho ProN","Yu Mincho",YuMincho,"Noto Serif JP",serif;
 line-height:1.9;font-size:16px;-webkit-text-size-adjust:100%}
header{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line);
 padding:.7rem 1rem}
.wrap{max-width:54rem;margin:0 auto;padding:0 1.2rem}
h1{font-size:1.05rem;margin:0 0 .5rem;font-weight:600;letter-spacing:.04em}
h1 a{color:inherit;text-decoration:none}
h1 small{font-weight:400;color:var(--sub);font-size:.8rem;margin-left:.6rem;letter-spacing:0}
.controls{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}
button{font:inherit;font-size:.82rem;padding:.22rem .7rem;border:1px solid var(--line);
 border-radius:999px;background:var(--card);color:var(--sub);cursor:pointer}
button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
input[type=search]{font:inherit;font-size:.85rem;padding:.25rem .7rem;border:1px solid var(--line);
 border-radius:999px;background:var(--card);color:var(--fg);min-width:11rem;flex:1}
#count{font-size:.78rem;color:var(--sub);margin-left:auto;white-space:nowrap}
main{padding:1.5rem 0 6rem}

/* 年月ごとの冊数 */
#archive{border:1px solid var(--line);border-radius:.4rem;background:var(--card);
 padding:.8rem .9rem;margin-bottom:2.5rem;overflow-x:auto}
#archive h2{font-size:.78rem;letter-spacing:.22em;color:var(--sub);margin:0 0 .6rem;font-weight:400}
#archive table{border-collapse:collapse;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
 font-size:.76rem;white-space:nowrap;min-width:100%}
#archive th,#archive td{padding:.15rem .35rem;text-align:right;font-weight:400}
#archive thead th{color:var(--sub);border-bottom:1px solid var(--line)}
#archive tbody th{text-align:left;color:var(--fg);padding-right:.7rem}
#archive a{color:var(--fg);text-decoration:none;display:block;padding:.05rem .15rem;border-radius:.2rem}
#archive a:hover{background:var(--line)}
#archive .zero{color:#c9c3b8}
#archive .sum{color:var(--accent);border-left:1px solid var(--line);padding-left:.6rem}

.year{font-size:.95rem;letter-spacing:.2em;color:var(--fg);margin:3rem 0 .2rem;font-weight:600}
.month{font-size:.75rem;letter-spacing:.2em;color:var(--sub);margin:1.6rem 0 .6rem;
 border-bottom:1px solid var(--line);padding-bottom:.3rem;scroll-margin-top:6.5rem}
.year+.month{margin-top:.6rem}
article{padding:1.3rem 0;border-bottom:1px solid var(--line)}
.meta{font-size:.75rem;color:var(--sub);display:flex;gap:.7rem;flex-wrap:wrap;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em}
.stars{color:var(--accent);letter-spacing:.1em;font-family:inherit}
h2{font-size:1.06rem;margin:.3rem 0 .15rem;font-weight:600;line-height:1.6}
.note{font-size:.88rem;color:var(--accent);margin:.1rem 0 .35rem}
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
const heads=[...document.querySelectorAll('.year,.month')];
const q=document.getElementById('q'), cnt=document.getElementById('count');
const nores=document.getElementById('nores');
let sel='';                       // '' = 全部 / '2'..'5' = 星の数 / 'best' = 年間ベスト
function apply(){
  const t=q.value.trim().toLowerCase();
  let n=0;
  for(const a of arts){
    const okSel = !sel || (sel==='best' ? a.classList.contains('best')
                                        : a.dataset.rating===sel);
    const okText = !t || a._find.includes(t);
    const ok = okSel && okText;
    a.classList.toggle('hide', !ok);
    if(ok) n++;
  }
  // 見出しは、その下に残っている記事が1件も無ければ隠す
  for(let i=heads.length-1; i>=0; i--){
    const h=heads[i]; let has=false;
    for(let e=h.nextElementSibling; e; e=e.nextElementSibling){
      if(e.classList.contains('year')) break;
      if(e.classList.contains('month')){ if(h.classList.contains('month')) break; 
        if(!e.classList.contains('hide')){has=true;break;} continue; }
      if(e.tagName==='ARTICLE' && !e.classList.contains('hide')){has=true;break;}
    }
    h.classList.toggle('hide', !has);
  }
  document.getElementById('archive').classList.toggle('hide', !!t || !!sel);
  cnt.textContent = n + '件';
  nores.style.display = n ? 'none' : 'block';
}
document.querySelectorAll('[data-sel]').forEach(b=>b.onclick=()=>{
  sel = b.dataset.sel === sel ? '' : b.dataset.sel;   // 同じものをもう一度押すと解除
  document.querySelectorAll('[data-sel]').forEach(x=>
    x.setAttribute('aria-pressed', x.dataset.sel===sel));
  apply();
});
q.oninput=apply;
// 手元でファイルとして開いているときは "./" がフォルダ一覧になってしまうので、
// リンクをたどらせず、その場で読み込み直す（絞り込みも初期状態に戻る）。
document.getElementById('home').onclick=e=>{e.preventDefault();location.reload();};
"""


def stars(n):
    return "★" * n + "☆" * (5 - n) if n else ""


BLOG_SUFFIX = re.compile(r"\s*[-–—]\s*読書記録\s*by\s*どぅ\s*$")
PUNCT = re.compile(r"[\s!-/:-@\[-`{-~！-／：-＠［-｀｛-～、。「」『』・ー－―~〜]")


def norm(s):
    """表記ゆれ(全角半角・空白・記号)を吸収した照合用のキー。"""
    return PUNCT.sub("", unicodedata.normalize("NFKC", s)).lower()


def linkify_best(body, by_title, by_norm):
    """年間ベストの本文のうち、書名と一致する行をその記事へのリンクにする。

    元記事の書名とベスト側の書き方が微妙にずれている(空白・記号・副題の有無)ので、
    完全一致で駄目なら正規化して照合し、それでも駄目なら前方一致まで見る。
    """
    out = []
    for line in body.split("\n"):
        key = BLOG_SUFFIX.sub("", line.strip())
        hit = by_title.get(key)
        if not hit and len(key) >= 3:
            k = norm(key)
            hit = by_norm.get(k)
            if not hit and len(k) >= 5:
                hit = next((v for kk, v in by_norm.items()
                            if len(kk) >= 5 and (kk.startswith(k) or k.startswith(kk))), None)
        if hit:
            out.append(f'<a href="#{hit}">{html.escape(key)}</a>')
        else:
            out.append(html.escape(line))
    return "\n".join(out)


def main():
    books = json.loads(BOOKS.read_text(encoding="utf-8"))
    books.sort(key=lambda b: b["datetime"], reverse=True)

    # 年間ベストからのリンク先: 同じ書名の記事のうち一番新しいもの
    by_title, by_norm = {}, {}
    for b in sorted(books, key=lambda b: b["datetime"]):
        if b["kind"] == "book":
            by_title[b["title"]] = b["id"]
            by_norm[norm(b["title"])] = b["id"]

    parts, cur_year, cur_month = [], None, None
    for b in books:
        y, m = b["date"][:4], b["date"][5:7]
        if y != cur_year:
            cur_year = y
            parts.append(f'<div class="year" id="y{y}">{y}</div>')
        if (y, m) != cur_month:
            cur_month = (y, m)
            parts.append(f'<div class="month" id="m{y}-{m}">{y}年{int(m)}月</div>')

        meta = [b["date"]]
        if b["rating"]:
            meta.append(f'<span class="stars">{stars(b["rating"])}</span>')
        elif b["kind"] == "best":
            meta.append("年間ベスト")

        byline = " / ".join(x for x in [b.get("author"), b.get("publisher"), b.get("pubdate")] if x)

        if b["kind"] == "best":
            body_html = linkify_best(b["body"], by_title, by_norm)
        elif b["body"]:
            body_html = html.escape(b["body"])
        else:
            body_html = '<span class="empty">（このときは感想を書き残していない）</span>'

        parts.append(
            f'<article id="{b["id"]}" class="{b["kind"]}" data-rating="{b["rating"] or 0}"'
            f'>'
            f'<div class="meta">{" ".join(meta)}</div>'
            f'<h2>{html.escape(b["title"])}</h2>'
            + (f'<div class="note">{html.escape(b["note"])}</div>' if b.get("note") else "")
            + (f'<div class="byline">{html.escape(byline)}</div>' if byline else "")
            + f'<div class="body">{body_html}</div></article>'
        )

    # 年ごと・月ごとの冊数（FC2のときの月別アーカイブにあたるもの）
    # 数えるのは本の記事だけ（年間ベストは12/31付なので混ぜると先の月まで埋まってしまう）
    read = [b for b in books if b["kind"] == "book"]
    per = collections.Counter((b["date"][:4], b["date"][5:7]) for b in read)
    # 記録が始まる前と、最後の記録より先は空欄にする。あいだの0冊の月は0と出す。
    first = min(b["date"][:7] for b in read)
    last = max(b["date"][:7] for b in read)
    # 1冊も読んでいない年(2009年)も行として出したいので、年は範囲から作る
    years = [str(y) for y in range(int(last[:4]), int(first[:4]) - 1, -1)]
    rows = []
    for y in years:
        cells = []
        for m in range(1, 13):
            mm = f"{m:02d}"
            n = per.get((y, mm), 0)
            if n:
                cells.append(f'<td><a href="#m{y}-{mm}">{n}</a></td>')
            elif first <= f"{y}-{mm}" <= last:
                cells.append('<td class="zero">0</td>')
            else:
                cells.append("<td></td>")
        total = sum(n for (yy, _), n in per.items() if yy == y) or 0
        anchor = f'<a href="#y{y}">{y}</a>' if total else y
        rows.append(f'<tr><th>{anchor}</th>{"".join(cells)}'
                    f'<td class="sum">{total}</td></tr>')
    archive = (
        '<section id="archive"><h2>年月ごとの冊数</h2><table>'
        '<thead><tr><th></th>'
        + "".join(f"<th>{m}</th>" for m in range(1, 13))
        + '<th class="sum">計</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></section>")

    c = collections.Counter(b["rating"] for b in books if b["rating"])
    nbest = sum(1 for b in books if b["kind"] == "best")
    buttons = (f'<button data-sel="best" aria-pressed="false">ベスト {nbest}</button>'
               + "".join(f'<button data-sel="{n}" aria-pressed="false">{stars(n)[:n]} {c[n]}</button>'
                         for n in (5, 4, 3, 2)))

    built = datetime.date.today().isoformat()
    nread = len(read)
    withauthor = sum(1 for b in read if b.get("author"))

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
<h1><a href="./" id="home">読書記録 by どぅ</a><small>{len(books)}件 ／ {books[-1]["date"][:4]}–{books[0]["date"][:4]}</small></h1>
<div class="controls">
{buttons}
<input type="search" id="q" placeholder="書名・著者・本文で絞り込む" autocomplete="off">
<span id="count">{len(books)}件</span>
</div>
</div></header>
<main class="wrap">
{archive}
{"".join(parts)}
<div id="nores">見つかりませんでした</div>
<footer>
FC2ブログ「読書記録 by どぅ」のアーカイブ。{built} 時点で {len(books)} 件（うち本の記事 {nread} 件）。<br>
著者・出版社・出版年は、元記事の表記と
<a href="https://openbd.jp/">openBD</a>・<a href="https://ndlsearch.ndl.go.jp/">国立国会図書館サーチ</a>
から補った（著者が入っているのは {withauthor} 件）。
</footer>
</main>
<script>{JS}</script>
</body>
</html>"""

    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(html_doc, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    size = (DOCS / "index.html").stat().st_size
    print(f"docs/index.html {size/1024/1024:.2f} MB / {len(books)}件 / 著者あり {withauthor}件")


if __name__ == "__main__":
    main()
