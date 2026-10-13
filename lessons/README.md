# lessons/ — 教訓帳の受信箱と保管庫

自己改善ループ（`.claude/rules/self-improvement.md`）の作業場所。sns リポと同じ構成。

| 場所 | 中身 |
|---|---|
| `.claude/rules/lessons.md` | 教訓帳の本体（全スレッドが起動時に読む） |
| `inbox/` | 各スレッドが締めに書く振り返り（1スレッド1ファイル・形は `inbox/_TEMPLATE.md`） |
| `archive/<YYYY-MM>/` | 教訓帳に反映済みの振り返り |
| `tools/lessons.py` | 教訓帳の点検・受信箱の集計・回数の反映（sns と同じスクリプト） |
| `stats.csv` | 週ごとの集計（訂正・手戻り・CI失敗の件数）。効き目の計測に使う |

```
python lessons/tools/lessons.py check     # 教訓帳の書式・ID重複・上限を点検
python lessons/tools/lessons.py inbox     # 受信箱の教訓と ✔/✖ 評価を一覧
python lessons/tools/lessons.py tally     # 受信箱の ✔/✖ を教訓帳の回数に足す（--apply で書き込み）
python lessons/tools/lessons.py archive   # 反映済みの受信箱を archive/ へ移し、stats.csv に1行足す（--apply で実行）
python lessons/tools/lessons.py skills    # 繰り返した手順を数え、3回以上をスキル化候補に出す
```

週1整理は sns の定時実行がまとめて行う（受信箱が空の週はこのリポは開かない）。
