# 📰 慶應小論文 朝のニュース

毎朝 6:00（日本時間）に最新ニュースを集め、**慶應義塾大学の小論文（総合政策学部・併願対策）の素材になる記事を5本**選んで、
「論点（賛成・反対）」「使える概念」「設問」「構成メモ」をつけた Web ページを自動で作るアプリです。

## できること

- 🗞 NHK・Yahoo!ニュース・Google ニュースの RSS から記事を収集
- 🎯 12 の頻出テーマ（AI・少子高齢化・地方創生・環境・格差・多様性・国際関係 など）で採点し、テーマが偏らないように 5 本を選定
  - 事件・スポーツ・芸能は減点、同じニュースの重複や直近 7 日に出した記事は除外
- ✍️ 1 本を「今日のメイン設問」にして、構成メモと答案メモ欄（ブラウザに自動保存・字数カウント付き）を表示
- 🔥 「読んだ」チェックで連続日数を記録
- 📚 過去の日付のページをアーカイブで振り返り
- 🤖 `ANTHROPIC_API_KEY` を設定すると、Claude が記事ごとに要約・論点・設問・構成メモを書き下ろします
  （未設定なら、テーマごとのテンプレート解説で動きます）

## セットアップ（最初の 1 回だけ）

1. このブランチを `main` にマージする（定期実行はデフォルトブランチでのみ動きます）
2. **Settings → Pages** で「Deploy from a branch」→ ブランチ `main`、フォルダ `/docs` を選んで保存
   - 非公開リポジトリで Pages を使うには GitHub の有料プランが必要です。無料なら公開リポジトリにしてください
3. （推奨）**Settings → Secrets and variables → Actions** に `ANTHROPIC_API_KEY` を登録
4. （任意）スマホに通知したい場合は Discord の Webhook URL を `DISCORD_WEBHOOK_URL` として登録
5. **Actions → 朝の小論文ニュース → Run workflow** で一度手動実行して、
   `https://<ユーザー名>.github.io/<リポジトリ名>/` が表示されることを確認

以降は毎朝自動で更新されます。スマホのホーム画面にページを追加しておくと便利です。

## ローカルで動かす

```bash
pip install -r requirements.txt
python -m ronbun_news --out docs                                  # ネットから取得して生成
python -m ronbun_news --out /tmp/site --feed-file tests/sample_feed.xml   # サンプルで試す
python -m unittest discover -s tests -t .                          # テスト
```

## カスタマイズ

- テーマ・キーワード・論点・設問：`ronbun_news/themes.py`
- ニュースの配信元：`ronbun_news/feeds.py`
- Claude への指示（解説の方針）：`ronbun_news/enrich.py` の `SYSTEM_PROMPT`
- 配信時刻：`.github/workflows/daily-news.yml` の `cron`（UTC 表記。`0 21 * * *` = 6:00 JST）
