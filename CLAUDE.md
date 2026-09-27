# News Globe（ニュース地球儀）

3D の地球儀をクリックすると、その場所の概要・ニュース・天気・経済データを10言語で表示する Web アプリ。
GitHub Pages で `news-globe.html` をそのまま公開している（https://velqiron.github.io/news-globe/news-globe.html）。

## 運用方針
- **このリポジトリの `news-globe.html` が正本。** ローカルのファイルはアップロードしない。修正はすべてこのファイルに直接加える。
- 元のソースやビルド設定はリポジトリにない。修正は圧縮済みのコードを直接書き換える。
- 修正 → テスト → PR 作成 → **確認なしで `main` にマージしてよい**（オーナー了承済み）。
- ユーザーへの報告は日本語で行う。

## ファイル構成
- `news-globe.html`（約8.7MB・1ファイル完結）
  - `<script type="application/json" id="d-countries">` などに、国・州・海域・地名のデータとテクスチャを埋め込んでいる。
  - 本体のコードは最後の `<script>`（圧縮済み）。three.js 0.186.0 と d3-geo 3.1.1 を同梱。
  - 実行時に呼び出す外部サービス: Wikipedia / Wikidata / Open-Meteo / World Bank / USGS / GDELT / MyMemory / NASA GIBS。
- `LICENSE`: 独自ライセンス（All rights reserved）と、同梱ライブラリのライセンス表記。

## 編集時の注意
1. **CSP のハッシュ値を必ず更新する。** `<meta http-equiv="Content-Security-Policy">` の `script-src 'sha256-…'` は、本体スクリプトのハッシュ値と一致しないとアプリが動かない。
   ```python
   import re, hashlib, base64
   s = open('news-globe.html', encoding='utf-8').read()
   i = s.rfind('<script>') + 8; j = s.index('</script>', i)
   h = base64.b64encode(hashlib.sha256(s[i:j].encode()).digest()).decode()
   s = re.sub(r"script-src 'sha256-[^']+'", f"script-src 'sha256-{h}'", s, count=1)
   open('news-globe.html', 'w', encoding='utf-8').write(s)
   ```
2. **置換は一意に一致させる。** Python で `assert s.count(old) == 1` を確かめてから置き換える。
3. **新しい識別子は名前の衝突に注意する。** 圧縮後の短い名前（`yS` など）は既に使われていることが多い。`wnFetchRecent` のように長くて一意な名前にし、`(?<![\w$.])name(?![\w$])` で既存の定義がないか検索する。
4. **構文チェック**: `node -e "const s=require('fs').readFileSync('news-globe.html','utf8');const i=s.lastIndexOf('<script>')+8;new Function(s.slice(i,s.indexOf('</script>',i)))"`
5. UI の文字列は `"キー":"\uXXXX…"` 形式の辞書にある（例: `wn.title`、`tr.waiting`）。日本語は `\u` でエスケープされているので、検索するときもエスケープした形で探す。

## 動作確認
- クラウド環境からは外部の API に接続できないことが多い。Playwright（`/opt/pw-browsers/chromium`、`NODE_PATH=$(npm root -g)`）で `file://` として開き、`context.route()` で通信を模擬する。
- 起動: `chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] })`、`locale: 'ja-JP'`。
- 場所の選択: 検索欄に `55.75, 37.62` のような座標を入力して Enter。
- Chrome の内蔵翻訳は `addInitScript` で `self.Translator` を差し替えて模擬する。
- 修正前のファイルで症状を再現し、修正後に解消することを確かめてから反映する。

## 過去の修正
- #1: 内蔵翻訳（Translator API）が止まるとニュースが「翻訳待ち」のままになる → 準備完了の判定を厳密にし、待ち時間の上限と MyMemory への切り替えを追加。
- #2: 自転中は「今日の世界ニュース」の取得が始まらない（`requestIdleCallback` に上限がなかった） → 上限1秒を指定し、起動直後に取得を開始。取得は2日分だけにし、失敗時は再試行する。
- #4: 「国・経済」タブの経済指標が「接続できませんでした」になることがある（7指標を `;` でまとめた World Bank API のリクエストが、経路によってはブラウザからだけ 403 になる） → まとめ取りに失敗したら指標ごとに取得し直して結果を合わせる（`wbFetchEach`）。
