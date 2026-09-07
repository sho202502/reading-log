# このリポジトリでの進め方

本を足したり直したりしたら、`main` まで押しきる。作業ブランチに置いて
確認を待たない。

```bash
python3 scripts/add.py "書名" 4 <<'BODY'
P26.本文
BODY
python3 scripts/enrich.py && python3 scripts/build.py
git add -A && git commit && git push -u origin main
```

GitHub Pages を作り直すのは `.github/workflows/build.yml` で、
`main` への push でしか動かない。ほかのブランチに押しても
サイトは前のままになる。

`data/books.json` が原本。`docs/index.html` は `build.py` の出力なので、
直に触らず作り直す。

星の数だけは決められないので、指定が無ければ聞く。

openBD と 国立国会図書館サーチ に出られない環境のことがある
（`CONNECT tunnel failed, 403`）。そのときは版元の書誌から手で入れて、
`source` を `手当て` にする。空振りが `data/cache/` に「結果なし」として
残ると次から引きに行かなくなるので、キャッシュへの書き込みは戻す。
