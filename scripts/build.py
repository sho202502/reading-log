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
 --bg:#fbfaf7;--fg:#1a1917;--body:#2b2926;--sub:#79756d;--line:#e8e4dc;
 --hair:#f0ece4;--accent:#8a6d3b;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font-family:"Hiragino Mincho ProN","Yu Mincho",YuMincho,"Noto Serif JP",serif;
 line-height:1.9;font-size:16px;-webkit-text-size-adjust:100%;
 font-feature-settings:"palt"}
.wrap{max-width:54rem;margin:0 auto;padding:0 1.4rem}

header{position:sticky;top:0;z-index:10;background:rgba(251,250,247,.94);
 backdrop-filter:saturate(180%) blur(10px);border-bottom:1px solid var(--line);
 padding:.85rem 0 .8rem}
h1{font-size:1.52rem;margin:0 0 .7rem;font-weight:500;letter-spacing:.18em;line-height:1.4}
h1 a{color:inherit;text-decoration:none}
/* 件数は、絞り込んでいるときだけ出す（全部出しているときは下の表の合計が同じ数） */
#count{font-size:.76rem;color:var(--sub);margin-left:auto;white-space:nowrap;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}
#count:empty{display:none}

.controls{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}
button{font:inherit;font-size:.8rem;line-height:1.6;padding:.2rem .8rem;
 border:1px solid var(--line);border-radius:999px;background:var(--card);
 color:var(--sub);cursor:pointer;display:inline-flex;align-items:baseline;
 justify-content:space-between;gap:.5rem;min-width:7.6rem;
 transition:background .12s,border-color .12s,color .12s}
button:hover{border-color:#d6d0c4}
button .n{font-size:.72rem;opacity:.7;font-variant-numeric:tabular-nums}
button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
button[aria-pressed=true] .n{opacity:.65}
input[type=search]{font:inherit;font-size:.84rem;padding:.24rem .9rem;
 border:1px solid var(--line);border-radius:999px;background:var(--card);
 color:var(--fg);flex:1;min-width:8rem}
input[type=search]:focus{outline:none;border-color:var(--accent)}

main{padding:2.2rem 0 7rem}

/* 年月ごとの冊数 */
#archive{border-top:1px solid var(--line);border-bottom:1px solid var(--line);
 padding:1rem .1rem 1.1rem;margin-bottom:3.4rem;overflow-x:auto}
#archive h2{font-size:.7rem;letter-spacing:.3em;color:var(--sub);margin:0 0 .8rem;
 font-weight:400}
#archive table{border-collapse:collapse;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
 font-size:.74rem;white-space:nowrap;min-width:100%;font-variant-numeric:tabular-nums}
#archive th,#archive td{padding:.16rem .34rem;text-align:right;font-weight:400}
#archive thead th{color:#a8a29a;border-bottom:1px solid var(--hair);font-size:.68rem}
#archive tbody th,#archive tfoot th{text-align:left;color:var(--fg);padding-right:.8rem;
 letter-spacing:.04em}
#archive tbody tr:hover td{background:#f6f3ec}
#archive a,#archive .cell{color:var(--fg);text-decoration:none;display:block;
 padding:.06rem .2rem;border-radius:.2rem}
#archive a:hover{background:var(--accent);color:#fff}
#archive .zero .cell{color:#d8d2c6}
#archive .sum{color:var(--accent);border-left:1px solid var(--hair);padding-left:.7rem}
#archive tfoot th,#archive tfoot td{border-top:1px solid var(--line);padding-top:.4rem;
 color:var(--accent)}
#archive tfoot .all{font-weight:600}

.year{font-size:1.85rem;letter-spacing:.14em;color:var(--fg);margin:4.2rem 0 0;
 font-weight:400;line-height:1;scroll-margin-top:7rem}
.month{font-size:.98rem;letter-spacing:.14em;color:var(--fg);font-weight:500;
 margin:2.4rem 0 1rem;padding-bottom:.5rem;border-bottom:1px solid var(--hair);
 scroll-margin-top:7rem}
.year+.month{margin-top:1.1rem}

article{padding:1.7rem 0;border-bottom:1px solid var(--hair)}
.meta{font-size:.72rem;color:var(--sub);display:flex;gap:.85rem;flex-wrap:wrap;
 align-items:baseline;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
 letter-spacing:.04em}
.stars{color:var(--accent);letter-spacing:.14em;font-family:inherit;font-size:1rem}
h2{font-size:1.14rem;margin:.34rem 0 .18rem;font-weight:600;line-height:1.65;
 letter-spacing:.01em}
.note{font-size:.86rem;color:var(--accent);margin:.15rem 0 .4rem;letter-spacing:.02em}
.byline{font-size:.78rem;color:var(--sub);margin-bottom:.8rem;letter-spacing:.03em}
.body{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--body);line-height:2.02}
.body a{color:var(--accent);text-underline-offset:.2em}
.empty{color:#a8a29a;font-size:.84rem;font-style:italic}
article.best{background:var(--card);border:1px solid var(--line);border-radius:.5rem;
 padding:1.6rem 1.5rem;margin:1.6rem 0}
article.best h2{letter-spacing:.1em}
.hide{display:none}
#nores{display:none;color:var(--sub);padding:4rem 0;text-align:center;letter-spacing:.1em}
footer{color:#a8a29a;font-size:.72rem;padding:2.6rem 0 5rem;margin-top:3rem;
 border-top:1px solid var(--line);line-height:2}
footer a{color:var(--sub)}
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
  cnt.textContent = (sel || t) ? n + '件' : '';   // 絞り込み中だけ出す
  nores.style.display = n ? 'none' : 'block';
}
document.querySelectorAll('[data-sel]').forEach(b=>b.onclick=()=>{
  sel = b.dataset.sel === sel ? '' : b.dataset.sel;   // 同じものをもう一度押すと解除
  document.querySelectorAll('[data-sel]').forEach(x=>
    x.setAttribute('aria-pressed', x.dataset.sel===sel));
  apply();
});
q.oninput=apply;
// サイトタイトルを押したら本当の先頭に戻す。
// 月へのリンクで飛んだあとは URL に #m2018-03 のような指定が残っていて、そのまま
// 読み込み直すとまたそこへ飛んでしまうので、# を外した行き先を自分で指定する。
// （href="./" のままだと、手元でファイルとして開いたときにフォルダ一覧になってしまう）
document.getElementById('home').onclick=e=>{
  e.preventDefault();
  location.replace(location.pathname + location.search);
};
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
            body_html = '<span class="empty">（本文が残っていない）</span>'

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
                cells.append('<td class="zero"><span class="cell">0</span></td>')
            else:
                cells.append("<td></td>")
        total = sum(n for (yy, _), n in per.items() if yy == y)
        # リンクの有無で字の位置がずれないよう、リンクでない年も同じ入れ物に入れる
        anchor = f'<a href="#y{y}">{y}</a>' if total else f'<span class="cell">{y}</span>'
        rows.append(f'<tr><th>{anchor}</th>{"".join(cells)}'
                    f'<td class="sum"><span class="cell">{total}</span></td></tr>')

    # 一番下に月ごとの合計、右下が全部の合計
    month_sum = [sum(n for (_, mm), n in per.items() if mm == f"{m:02d}") for m in range(1, 13)]
    foot = ('<tfoot><tr><th><span class="cell">計</span></th>'
            + "".join(f'<td><span class="cell">{n}</span></td>' for n in month_sum)
            + f'<td class="sum all"><span class="cell">{sum(month_sum)}</span></td></tr></tfoot>')

    archive = (
        '<section id="archive"><h2>年月ごとの冊数</h2><table>'
        '<thead><tr><th></th>'
        # 見出しも数字と同じ入れ物に入れる（入れないと余白のぶんだけ右にずれる）
        + "".join(f'<th><span class="cell">{m}</span></th>' for m in range(1, 13))
        + '<th class="sum"><span class="cell">計</span></th></tr></thead><tbody>'
        + "".join(rows) + "</tbody>" + foot + "</table></section>")

    c = collections.Counter(b["rating"] for b in books if b["rating"])
    nbest = sum(1 for b in books if b["kind"] == "best")
    buttons = (f'<button data-sel="best" aria-pressed="false">ベスト<span class="n">{nbest}</span></button>'
               + "".join(f'<button data-sel="{n}" aria-pressed="false">'
                         f'{stars(n)[:n]}<span class="n">{c[n]}</span></button>'
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
<title>遠藤翔の読書記録</title>
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<style>{CSS}</style>
</head>
<body>
<header><div class="wrap">
<h1><a href="./" id="home">遠藤翔の読書記録</a></h1>
<div class="controls">
{buttons}
<input type="search" id="q" placeholder="検索" autocomplete="off">
<span id="count"></span>
</div>
</div></header>
<main class="wrap">
{archive}
{"".join(parts)}
<div id="nores">見つかりませんでした</div>
<footer>
もとはFC2ブログ「読書記録 by どぅ」。{built} 時点で {len(books)} 件（うち本の記事 {nread} 冊）。<br>
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
    # ファビコン: 「本」を丸で囲んだもの
    (DOCS / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<circle cx="32" cy="32" r="30" fill="#8a6d3b"/>'
        '<text x="32" y="32" text-anchor="middle" dominant-baseline="central"'
        ' font-family="Hiragino Sans,Hiragino Kaku Gothic ProN,Noto Sans JP,sans-serif"'
        ' font-weight="700" font-size="38" fill="#fbfaf7">本</text></svg>\n', encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    size = (DOCS / "index.html").stat().st_size
    print(f"docs/index.html {size/1024/1024:.2f} MB / {len(books)}件 / 著者あり {withauthor}件")


if __name__ == "__main__":
    main()
