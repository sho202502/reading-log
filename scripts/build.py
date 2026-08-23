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
 --bg:#f5f4f1;--fg:#111110;--body:#38352f;--sub:#96918a;--line:#ddd9d1;
 --hair:#e9e5dd;--accent:#111110;--card:#fbfaf8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font-family:"Helvetica Neue",Helvetica,Arial,"Hiragino Sans",
 "Hiragino Kaku Gothic ProN","Yu Gothic Medium","Noto Sans JP",sans-serif;
 line-height:1.95;font-size:16px;-webkit-text-size-adjust:100%;
 font-feature-settings:"palt"}
.wrap{max-width:58rem;margin:0 auto;padding:0 1.6rem}
/* 小さいラベルは字間を広く取る（雑誌の柱のような見え方にする） */
.label{font-size:.63rem;letter-spacing:.34em;color:var(--sub);font-weight:400}

header{position:sticky;top:0;z-index:10;background:rgba(245,244,241,.9);
 backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--line);
 padding:1rem 0 .9rem}
h1{font-size:1.72rem;margin:0 0 .9rem;font-weight:300;letter-spacing:.14em;line-height:1.3}
h1 a{color:inherit;text-decoration:none}
/* 件数は、絞り込んでいるときだけ出す（全部出しているときは下の表の合計が同じ数） */
#count{font-size:.68rem;color:var(--sub);margin-left:auto;white-space:nowrap;
 font-variant-numeric:tabular-nums;letter-spacing:.16em}
#count:empty{display:none}

.controls{display:flex;flex-wrap:wrap;gap:.36rem;align-items:center}
button{font:inherit;font-size:.72rem;line-height:1.7;padding:.22rem .85rem;
 border:1px solid var(--line);border-radius:0;background:transparent;
 color:var(--sub);cursor:pointer;display:inline-flex;align-items:baseline;
 justify-content:space-between;gap:.6rem;min-width:7.6rem;letter-spacing:.1em;
 transition:background .15s,border-color .15s,color .15s}
button:hover{border-color:var(--fg);color:var(--fg)}
button .n{font-size:.66rem;opacity:.65;font-variant-numeric:tabular-nums;letter-spacing:.06em}
button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
button[aria-pressed=true] .n{opacity:.6}
input[type=search]{font:inherit;font-size:.76rem;padding:.26rem .85rem;
 border:1px solid var(--line);border-radius:0;background:transparent;
 color:var(--fg);flex:1;min-width:8rem;letter-spacing:.1em}
input[type=search]:focus{outline:none;border-color:var(--fg)}

main{padding:2.6rem 0 7rem}

/* 年月ごとの冊数 */
#archive{border-top:1px solid var(--fg);border-bottom:1px solid var(--line);
 padding:1.1rem .1rem 1.2rem;margin-bottom:4rem;overflow-x:auto}
#archive h2{font-size:.63rem;letter-spacing:.34em;color:var(--sub);margin:0 0 1rem;
 font-weight:400}
#archive table{border-collapse:collapse;font-size:.73rem;white-space:nowrap;
 min-width:100%;font-variant-numeric:tabular-nums;letter-spacing:.06em}
#archive th,#archive td{padding:.17rem .34rem;text-align:right;font-weight:400}
#archive thead th{color:#b6b0a7;border-bottom:1px solid var(--hair);font-size:.63rem;
 letter-spacing:.1em}
#archive tbody th,#archive tfoot th{text-align:left;color:var(--fg);padding-right:.9rem;
 letter-spacing:.1em}
#archive tbody tr:hover td{background:#eeebe4}
#archive a,#archive .cell{color:var(--fg);text-decoration:none;display:block;
 padding:.06rem .2rem;border-radius:0}
#archive a:hover{background:var(--fg);color:var(--bg)}
#archive .zero .cell{color:#cfc9bf}
#archive .sum{border-left:1px solid var(--hair);padding-left:.8rem}
#archive tfoot th,#archive tfoot td{border-top:1px solid var(--line);padding-top:.45rem}
#archive tfoot .all{font-weight:600}

/* 年は大きく細く、月は柱のように小さく */
.year{font-size:3.6rem;letter-spacing:-.01em;color:var(--fg);margin:5rem 0 0;
 font-weight:200;line-height:1;scroll-margin-top:8.5rem;
 padding-bottom:.7rem;border-bottom:1px solid var(--fg)}
.month{margin:2.8rem 0 1.2rem;scroll-margin-top:8.5rem;line-height:1;
 display:flex;align-items:center;gap:1rem}
.month span{font-size:.63rem;letter-spacing:.34em;color:var(--sub);white-space:nowrap}
.month::after{content:"";flex:1;height:1px;background:var(--hair)}
.year+.month{margin-top:1.6rem}

article{padding:1.9rem 0;border-bottom:1px solid var(--hair);scroll-margin-top:8rem}
.meta{font-size:.66rem;color:var(--sub);display:flex;gap:1rem;flex-wrap:wrap;
 align-items:baseline;font-variant-numeric:tabular-nums;letter-spacing:.16em}
.stars{color:var(--fg);letter-spacing:.22em;font-family:inherit;font-size:.82rem}
h2{font-size:1.18rem;margin:.42rem 0 .2rem;font-weight:500;line-height:1.6;
 letter-spacing:.04em}
.note{font-size:.8rem;color:var(--sub);margin:.15rem 0 .4rem;letter-spacing:.08em}
.byline{font-size:.72rem;color:var(--sub);margin-bottom:.9rem;letter-spacing:.12em}
.body{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--body);line-height:2.05}
.body a{color:var(--fg);text-underline-offset:.2em}
.empty{color:#b6b0a7;font-size:.78rem;letter-spacing:.16em}
article.best{background:var(--card);border:none;border-left:2px solid var(--fg);
 border-radius:0;padding:1.6rem;margin:1.8rem 0}
article.best h2{letter-spacing:.1em}
.hide{display:none}
#nores{display:none;color:var(--sub);padding:4rem 0;text-align:center;letter-spacing:.3em;
 font-size:.7rem}
footer{color:#b6b0a7;font-size:.66rem;padding:2.8rem 0 5rem;margin-top:3.4rem;
 border-top:1px solid var(--line);line-height:2.2;letter-spacing:.1em}
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
    const okSel = !sel || (sel==='best' ? (a.classList.contains('best') || a.dataset.best)
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
// 記事へのリンク(年間ベストの中の書名)は、絞り込み中でも飛べるようにする。
// 絞り込みで隠れている記事は、先に絞り込みを解いてから移動する。
function jumpTo(id){
  const el=document.getElementById(id);
  if(!el) return false;
  if(el.classList.contains('hide')){
    sel=''; q.value='';
    document.querySelectorAll('[data-sel]').forEach(x=>x.setAttribute('aria-pressed','false'));
    apply();
  }
  el.scrollIntoView();
  history.replaceState(null,'','#'+id);
  return true;
}
document.addEventListener('click',e=>{
  // 別タブで開く操作(command/ctrl+クリックなど)は、そのままブラウザに任せる
  if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button!==0) return;
  const a=e.target.closest('a[href^="#"]');
  if(!a || a.id==='home') return;
  if(jumpTo(decodeURIComponent(a.getAttribute('href').slice(1)))) e.preventDefault();
});
if(location.hash) jumpTo(decodeURIComponent(location.hash.slice(1)));
// サイトタイトルを押したら本当の先頭に戻す。
// 月へのリンクで飛んだあとは URL に #m2018-03 のような指定が残っていて、そのまま
// 読み込み直すとまたそこへ飛んでしまうので、# を外した行き先を自分で指定する。
// （href="./" のままだと、手元でファイルとして開いたときにフォルダ一覧になってしまう）
document.getElementById('home').onclick=e=>{
  if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey) return;   // 別タブで開くときは邪魔しない
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

    # 年間ベストに選ばれた本。「ベスト」で絞り込んだとき、一覧と一緒にこの本の記事も出す
    best_ids = set()
    for b in books:
        if b["kind"] == "best":
            linked = linkify_best(b["body"], by_title, by_norm)
            best_ids |= set(re.findall(r'href="#([^"]+)"', linked))

    parts, cur_year, cur_month = [], None, None
    for b in books:
        y, m = b["date"][:4], b["date"][5:7]
        if y != cur_year:
            cur_year = y
            parts.append(f'<div class="year" id="y{y}">{y}</div>')
        if (y, m) != cur_month:
            cur_month = (y, m)
            parts.append(f'<div class="month" id="m{y}-{m}"><span>{y}年{int(m)}月</span></div>')

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
            body_html = '<span class="empty">記録なし</span>'

        parts.append(
            f'<article id="{b["id"]}" class="{b["kind"]}" data-rating="{b["rating"] or 0}"'
            + (' data-best="1"' if b["id"] in best_ids else "")
            + f'>'
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
    nbest = sum(1 for b in books if b["kind"] == "best" or b["id"] in best_ids)
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
<meta name="theme-color" content="#f5f4f1">
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
        '<circle cx="32" cy="32" r="32" fill="#111110"/>'
        '<text x="32" y="32" text-anchor="middle" dominant-baseline="central"'
        ' font-family="Hiragino Sans,Hiragino Kaku Gothic ProN,Noto Sans JP,sans-serif"'
        ' font-weight="400" font-size="34" fill="#f5f4f1">本</text></svg>\n', encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    size = (DOCS / "index.html").stat().st_size
    print(f"docs/index.html {size/1024/1024:.2f} MB / {len(books)}件 / 著者あり {withauthor}件")


if __name__ == "__main__":
    main()
