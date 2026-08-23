# 読書記録 by どぅ

2008年から読んだ本の記録（1,482冊）を、1枚のHTMLとして持っておくためのもの。
元はFC2ブログ「読書記録 by どぅ」で、そちらは畳んだ。

人に読ませるためのサイトではないので、検索エンジンには載せない（`noindex`）。

## 中身

```
data/books.json     原本。ここが正
data/cache/         openBD と 国立国会図書館サーチ から取ってきた控え
scripts/add.py      本を1冊足す
scripts/enrich.py   著者・出版社・出版年が空いている記事だけ埋める
scripts/build.py    books.json -> docs/index.html
docs/index.html     公開されるもの（自動生成）
```

## 本を1冊足す

本文は標準入力から渡す。

```bash
python3 scripts/add.py "父の生きる" 5 <<'BODY'
P121.父の本質は、私を可愛がってくれて、自分よりも大切に思ってくれて、
私が頼りにもしてきたおとうさんだ。
BODY
```

そのあと、著者を引いてHTMLを作り直して、pushする。

```bash
python3 scripts/enrich.py && python3 scripts/build.py
```

pushすると GitHub Actions が `docs/` を GitHub Pages に出す。
Actionsは `build.py` を走らせるだけで、外部には問い合わせない。

日付を変えたいときは `--date 2026-08-20`、ISBNが分かっていれば `--isbn` を付ける。

## 書誌の出どころ

1,482冊すべてに著者・出版社・出版年が入っている。

- [openBD](https://openbd.jp/) … ISBNで引く
- [国立国会図書館サーチ](https://ndlsearch.ndl.go.jp/) … ISBNまたは書名で引く（OpenSearch と SRU）
- 元記事の本文・タイトルの表記
- 版元・書店の書誌（自動で当たらなかった46件を1件ずつ確かめた）

NDLのタイトル検索は、その本を論じた雑誌記事や書評まで返してくる。
図書のレコードに限ったうえで、書名が実際に噛み合うものだけを採っている
（`scripts/enrich.py` の `title_ok`）。副題の有無は吸収し、短い書名がたまたま
長い書名に含まれているだけの一致（「シフト」と「…にシフト」）は落とす。

`enrich.py` は3つとも埋まっている記事には触らない。足した1冊だけを引きに行く。

## 元データについて

FC2からのMT形式の書き出し `data/dokushop.txt` と、それを変換する `parse.py`、
自動で引けなかったぶんの書誌 `manual.json` は、役目を終えたので消した。
必要になったらgitの履歴から戻せる。

```bash
git show 11ea7cf:data/dokushop.txt > dokushop.txt
```

変換のときに分かったことを残しておく。

- 星評価はMT形式の `PRIMARY CATEGORY` に入っていた（★5=615 / ★4=708 / ★3=119 / ★2=6）
- `ベスト` の14件は本の記事ではなく年間まとめ。本文中の書名は該当記事へのリンクに張り替えてある
- 2009年の記事は元データに1件もない
- 1件だけ日付が `12/14/1901` になっていたので、前後の記事から `2022-12-31` に直した
- 画像は全部落とした（参照先がFC2上にあり、読書記録以外をやっていた頃の名残のため）
- 44件は元から本文が空（Amazonリンク1行だけの記事）
- Amazonのアフィリエイトリンクは全部捨てたが、URLの中のISBNだけは回収した
