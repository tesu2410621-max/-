# 📰 慶應入試新聞

毎朝 6:00（日本時間）に最新ニュースを集め、**約10分で読める新聞形式の紙面**を Web ページと **A5 の PDF**（iPad などで手書きする用）で発行するアプリです。

| 面 | 内容 |
|---|---|
| ✍️ 小論文面 ×2 | 文学部・法学部・環境情報学部・総合政策学部を2日で一巡。何が起きたか／背景／論点（賛成・反対）／学部とのつながり／キーワード／1分思考問題／解答例。解答例の下の余白は手書き欄 |
| 🇬🇧 英語長文面 ×2 | 経済学部・商学部向け。慶應英語で出る考え方／単語／語形変化（名詞化）／例文 |
| 🏛 世界史の窓 | 今日のテーマに関わる世界史（経済史・社会史中心） |

`ANTHROPIC_API_KEY` を登録すると、Claude が記事ごとに **Web検索で事実関係を取材** してから紙面を書きます（取材メモにない数字・固有名詞は書かない）。
未登録の場合は、見出し・論点・キーワード・設問だけの簡易版になります。

## 📅 出題時期を踏まえた切り替え

入試問題は本番の数か月前に作られるため、出題に反映されうるニュースはおおむね **11 月末まで** と考えます。

| 時期 | モード | 内容 |
|---|---|---|
| 4〜9 月 | 🟢 出題圏内 | 最新ニュースから選定 |
| 10〜11 月 | ⏳ ラストスパート | 最新ニュース＋締め切りまでの残り日数を表示 |
| 12〜3 月 | 🧊 復習モード | 直前のニュースは追わず、出題圏内（前年 12 月〜11 月）に集めた記事を学部ごとに復習。30 日以内に出した記事は繰り返さない |

復習用のストックが足りない学部だけ最新ニュースで補い、「⚪ 出題圏外：テーマ理解用」と表示します。
英語長文も数年前までに出版された本や記事から採られることが多いため、個々のニュースより「背景にあるテーマ」を押さえるのが目的です。

## しくみ

- 🗞 NHK・Yahoo!ニュース・Google ニュース（日本語）、BBC・NPR・The Conversation・Guardian・Google News（英語）の RSS から記事を収集
- 🎯 14 の頻出テーマ（文化・言語、法と民主主義、AI、科学技術、少子高齢化、環境、格差 など）で採点し、その日の2学部に 1 本ずつ選定
  - 事件・スポーツ・芸能は減点、同じニュースの重複や直近 7 日に出した記事は除外
- 📄 Playwright（Chromium）で紙面を A5 の PDF にし、`docs/pdf/` に保存
- 📚 過去の日付のページをアーカイブで振り返り
- 🤖 Claude（取材：Web検索・Web取得 → 執筆：構造化出力）で紙面を作成

## セットアップ（最初の 1 回だけ）

1. このブランチを `main` にマージする（定期実行はデフォルトブランチでのみ動きます）
2. **Settings → Pages** で「Deploy from a branch」→ ブランチ `main`、フォルダ `/docs` を選んで保存
   - 非公開リポジトリで Pages を使うには GitHub の有料プランが必要です。無料なら公開リポジトリにしてください
3. （推奨）**Settings → Secrets and variables → Actions** に `ANTHROPIC_API_KEY` を登録
4. （任意）スマホに通知したい場合は Discord の Webhook URL を `DISCORD_WEBHOOK_URL` として登録
5. **Actions → 慶應入試新聞 → Run workflow** で一度手動実行して、
   `https://<ユーザー名>.github.io/<リポジトリ名>/` が表示されることを確認

以降は毎朝自動で更新されます。スマホのホーム画面にページを追加しておくと便利です。

## ローカルで動かす

```bash
pip install -r requirements.txt
python -m ronbun_news --out docs                                  # ネットから取得して生成
python -m ronbun_news --out /tmp/site --feed-file tests/sample_feed.xml \
  --english-feed-file tests/sample_feed_en.xml                     # サンプルで試す
python -m ronbun_news.pdf --out docs                              # A5 PDF を作る（要 playwright）
python -m unittest discover -s tests -t .                          # テスト
```

## カスタマイズ

- テーマ・学部の傾向・英語の分野と語彙：`ronbun_news/themes.py`
- 出題圏の締め切り（11 月末）：`ronbun_news/exam.py`
- ニュースの配信元：`ronbun_news/feeds.py`
- Claude への指示（取材・紙面の方針と字数）：`ronbun_news/enrich.py` の `RESEARCH_SYSTEM` / `WRITER_SYSTEM`
- 紙面のデザイン・A5印刷のレイアウト：`ronbun_news/render.py`
- 配信時刻：`.github/workflows/daily-news.yml` の `cron`（UTC 表記。`0 21 * * *` = 6:00 JST）
