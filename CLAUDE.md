# News Globe（ニュース地球儀）

3D の地球儀をクリックすると、その場所の概要・ニュース・天気・経済データを12言語で表示する Web アプリ。
GitHub Pages で `news-globe.html` をそのまま公開している（https://velqiron.github.io/news-globe/news-globe.html）。

## 運用方針
- **このリポジトリの `news-globe.html` が正本。** ローカルのファイルはアップロードしない。修正はすべてこのファイルに直接加える。
- 元のソースやビルド設定はリポジトリにない。修正は圧縮済みのコードを直接書き換える。
- 修正 → テスト → PR 作成 → **確認なしで `main` にマージしてよい**（オーナー了承済み）。
- **API キーを公開ページに載せない**（オーナー方針）。キーが必要なサービス（Google Cloud Translation、DeepL など）は使わない。使う場合は中継サーバーを別に用意する。
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

## 主要メディア・現地メディア（ニュースタブの「世界の報道」）
- `ngMajorByCC`（`async function ba` の直前）が主要メディアの一覧。キーは媒体の本拠地の国コード（ISO 3166-1 alpha-2）、値は空白区切りのドメイン。選定基準は「国際通信社・公共放送・主要な全国紙」。追加・削除はここを編集する（サブドメインは親ドメインで一致する。例: `asia.nikkei.com` → `nikkei.com`）。
- 「主要メディア」の記事を一覧の上に並べる。「現地メディア」は GDELT の `sourcecountry` か国別ドメイン（ccTLD）が選んだ国と一致する記事に付ける（`ngIsLocal`、国名の表記ゆれは `ngAlias`）。現地メディアは印を付けるだけで、並び順は変えない。
- 主要メディアが3件未満のときだけ、`domain:` で主要メディアに絞った GDELT 検索を1回追加する（`ngMore`）。対象は BBC・Reuters・AP と、その国の媒体（なければ DW・France 24・NHK・ABC）の計8件まで。GDELT は IP ごとに「5秒に1回」の制限があり、アプリ側で6秒間隔にしている（`Kp`）。
- 表示の文言は各言語の辞書の `src.major` / `src.local` / `src.legend` / `src.searching`。
- GDELT の利用条件として、出典表記と https://www.gdeltproject.org/ へのリンクが必要（一覧の注記と「データと出典」に設置済み）。

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
- #5: GDELT の「世界の報道」に「主要メディア」「現地メディア」の印を付け、主要メディアを上に表示。主要メディアが少ないときは主要メディアに絞った検索を追加。gdeltproject.org へのリンクを追加。
- #6: 内蔵翻訳が止まらずに遅い（1件10秒など）と、上限の15秒に届かず「翻訳待ち」が長く続く → 1件ごとの上限を、言語ごとの最初の1件は12秒、以降は6秒に短縮（`_tx`、`txWarm`）。
- #7: 同じ場所をもう一度表示すると、ニュースが英語のまま「翻訳待ち」になる（`translateMany` がキャッシュ済みの訳を `onItem` で知らせずに返していた） → キャッシュ済み・翻訳不要の項目も `onItem` で知らせる。
- #8: 「みんなの投稿を見る」を X と Bluesky の2つのボタンに分けた（`see-row`）。X は `#ニュース地球儀 OR #NewsGlobe` で検索。Bluesky は検索の OR 対応が確認できないため、表示中の言語のハッシュタグ（投稿文と同じ `yS`）で検索する。
- #9: ニュースタブ上部の翻訳状態の欄を削除。正常時（`describe()` の tone が ok で操作なし）は何も出さず、再試行・有効化などの操作が必要なときだけ、タブ列の右端（`.tr-mini`）に点とボタンを小さく出す。詳しい文面はマウスを乗せたときの表示（title）。
- #10: 訳文をブラウザに保存して再利用（`trCacheLoad` / `trCacheSave`、localStorage の `newsglobe:tr-cache`）。キーは「表示言語・元の言語・原文」。14日で期限切れ、最新2,000件まで、容量不足なら件数を半分ずつ減らして保存。MyMemory で訳した文は、内蔵翻訳が使えるときは訳し直す。MyMemory の枠を使い切った／残り1,500文字未満でメール未設定のときは、タブ列の右端に「メールで上限を増やす」を出し、設定画面のメール欄を開く（`trEmailCta`）。メール設定時に使い切りの状態を解除。
- #11: 表示言語を自分で選んだとき、または表示言語がブラウザの第一言語と同じときは、`<html translate="no">` にしてブラウザ（Chrome）の自動ページ翻訳を止める（`kd()`）。日本語の人が English を選ぶと Chrome が英語 UI を日本語に機械翻訳し、表示が混在していたため。タイ語・ベトナム語など未対応言語の人（英語表示に自動フォールバック）は翻訳を許可したままにし、Chrome の翻訳で読めるようにしている。
- #12: 表示言語にタイ語（th）とベトナム語（vi）を追加（辞書 `ngDictTh` / `ngDictVi`、言語一覧 `kc`、`Ha`、地域設定 `pg`（タイ語は西暦表示の `th-TH-u-ca-gregory`）、Google ニュース `wm`、集落判定 `Qb`、CSP に th/vi.wikipedia.org）。ベトナム語の都市・州県・海域名は Natural Earth の NAME_VI を `d-names` に追加（既存の中国語名と照合して対応づけを検証）。Natural Earth にタイ語名はないため、タイ語では都市・州県・海域名は英語、国名はブラウザの Intl.DisplayNames でタイ語。タブ名が折り返さないよう `.tab` に `white-space:nowrap`。
- #13: 「翻訳エンジンを確認中…」から戻らない（内蔵翻訳の `Translator.create()` が DOMException を投げると、その数値の `code`（例: NotSupportedError=9）が状態として保存され、`describe()` のどの分岐にも当たらなかった。訳文がすべて保存済みだと切り替え処理も走らず固定される） → 状態には文字列の code だけを使い、DOMException は name で分類（NotSupportedError → unavailable）。未知の状態は自動モードでは MyMemory 扱いにして「確認中」に落ちないようにした。
- #14（総点検）: 12言語×（通常／外部サービス全停止／スマホ幅）の自動点検で見つかった不具合を修正。(1) スマホ幅で設定画面の「翻訳エンジン」選択欄が長い選択肢のせいで右端からはみ出す → `.field` を `minmax(0,1fr)` にし選択欄の幅を制限。(2) 内蔵翻訳が特定の文だけエラーを返すと、その文が原文のまま → 自動モードではその文だけ MyMemory で訳す（時間切れの場合は従来どおり以降すべて MyMemory）。(3) 検索がアクセント記号を区別し「Sao Paulo」で「São Paulo」が見つからない → `norm` でアクセント記号（U+0300–036F）と đ を無視。(4) 地名データ（d-places の州・省名の欄）に Natural Earth 由来の文字化け 38 件（例「Ðà N?ng」）→ 正しい名前に修正。(5) 「最近見た場所」が見たときの言語の名前のまま残り、言語を切り替えると混在する → 保存時に言語（`lg`）と種類（`k`: 国／地域／海域）を記録し、別言語の項目は座標から今の言語の名前を出し直す（`ngRecentName`）。座標が同じ項目は重複させない。
- #15: 地球儀上の地名ラベル（都市・国・海域）をクリックすると、その場所を選ぶのに加えて、ラベルの位置に追従するカード（`.xcard`、`wnLabelCard` / `wnLabelCardClose`）を表示。X（最新 `f=live`／話題）と Bluesky でその地名を検索するボタンと、コメント欄から X / Bluesky に投稿するボタン（web intent、文面は「コメント + #地名 + `yS`」と場所の URL）を置く。X・Bluesky とも API キーなしでは投稿の取得・埋め込みができない（X の検索埋め込みは提供終了、CSP も `frame-src 'none'`）ため、表示・投稿は新しいタブで行う。ラベルは `pointer-events:none` のままにし、クリック判定は地球儀側（`wnLabelAt`、ドラッグでは反応しない）で行う。ホバー時は下線とポインタ（`wnHoverLabel`）。文言は辞書の `xl.*`。
- #16: PC で地名ラベルをクリックしてもカードが出ない（場所の選択も起きない）ことがある → クリック判定（`pointerup`）の「押してから離すまで600ms未満」が、少しゆっくり押したときや描画が重いとき（イベント処理が遅れて計測が伸びる）に外れていた。上限を1500msに緩め、押した時点のラベルも当たりとする（`t.L`）。マウスの当たり判定の余白を3→5px に。
- #17: ニュース層のピン（「イスラエル 2」のような件数付きの国名ボタン、`.pin`）をクリックしても X / Bluesky のカードが出なかった（#15 は地名ラベルだけが対象） → `De.on("pin")` で `Tm(s)` の後に `wnLabelCard` を呼ぶ（名前はピンの表示名と同じく末尾の括弧書きを除く）。
- 総点検の道具: 作業用の Playwright スクリプト（全 API を模擬し、各タブ・設定・データと出典を開いて、画面上の未翻訳キー・undefined/NaN・未置換の {name}・右端のはみ出し・スクリプトエラーを検出する）。リポジトリには含めていない。
