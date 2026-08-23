# 読書記録 by どぅ

FC2ブログ「読書記録 by どぅ」（2008–2026 / 1,495件）を、1枚のHTMLとして保管し直したもの。

FC2を畳んでも記録が残るようにするのが目的で、人に読ませるためのサイトではない。
検索エンジンには載せない（`noindex` と `robots.txt`）。

## 中身

```
data/dokushop.txt      FC2のMT形式エクスポート（元データ・原本のまま）
data/books.json        機械可読にしたもの。ここが正
data/cache/            外部から取ってきた書誌データの控え
scripts/parse.py       dokushop.txt -> books.json
scripts/enrich.py      著者・出版社・出版年を補完
scripts/build.py       books.json -> docs/index.html
docs/                  公開されるファイル（GitHub Actionsが自動で作る）
```

## 使い方

```bash
python3 scripts/parse.py            # 元データを読み直す
python3 scripts/enrich.py           # 書誌を補完（外部に問い合わせる）
python3 scripts/enrich.py --offline # 控えにあるぶんだけ反映（CIはこちら）
python3 scripts/build.py            # HTMLを書き出す
```

`main` にpushすると GitHub Actions が `--offline` でビルドして Pages に出す。
外部への問い合わせは手元で済ませ、結果を `data/cache/` にコミットしてあるので、
pushのたびに openBD や国立国会図書館サーチを叩くことはない。

## 元データについて

- 記事の区切りは `--------`、フィールドの区切りは `-----`（Movable Type形式）
- 星評価は `PRIMARY CATEGORY` に入っている（★5=614 / ★4=708 / ★3=119 / ★2=6 / 未分類=34）
- `ベスト` の14件は本の記事ではなく年間まとめ。本文中の書名は該当記事へのリンクに張り替えてある
- 2009年の記事は元データに1件もない
- 1件だけ日付が `12/14/1901` になっていたので、前後の記事から `2022-12-31` に直した
- 画像は全部落とした（参照先がFC2上にあり、読書記録以外をやっていた頃の名残のため）
- 44件は元から本文が空（Amazonリンク1行だけの記事）

## 著者・出版社の出どころ

Amazonのアフィリエイトリンクは全部捨てたが、URLの中のISBNだけは回収した。
`amzn.asia` / `amzn.to` の短縮URLは1回だけ展開してISBNを取り、結果を `data/cache/` に保存してある。
書誌そのものは Amazon からは取らず、以下から引いている。

- 元記事の本文・タイトル（`著者：`、`〜(著)`、`書名（著者）出版社` の表記）
- [openBD](https://openbd.jp/)
- [国立国会図書館サーチ](https://ndlsearch.ndl.go.jp/)
