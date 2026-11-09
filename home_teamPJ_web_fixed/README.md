# Home Team PJ - Web統合版（修正版）

予定・実績管理、週間レビュー、本人操作による位置情報記録を統合したFlaskアプリです。PC・スマートフォンのブラウザから利用できます。

## 主な機能

- ユーザー登録・ログイン（パスワードハッシュ化）
- 予定登録（1回のみ／毎週）と削除
- 実績登録・削除（ISO 8601形式の日時をPython側で生成）
- 週間集計、活動別・曜日別グラフ、ユーザー間ランキング、前週比較
- OpenAI APIキーを設定した場合の週間AI振り返り。未設定時は通常の集計コメントを表示
- ブラウザGeolocation APIによる位置記録（明示的な開始／停止、アカウント単位の閲覧制限）
- レスポンシブ画面

## Windowsでの起動方法

1. ZIPを解凍し、`app.py` と `requirements.txt` が同じフォルダにあることを確認します。
2. コマンドプロンプトを開き、そのフォルダへ移動します。例：

```cmd
cd /d "%USERPROFILE%\Downloads\home_teamPJ_web\home_teamPJ_web"
```

3. 仮想環境を作成・有効化します（すでに `.venv` がある場合は有効化だけで構いません）。

```cmd
py -m venv .venv
.venv\Scripts\activate
```

4. 必要ライブラリをインストールします。

```cmd
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

5. アプリを起動します。

```cmd
python -m flask --app app run --debug
```

6. ブラウザで http://127.0.0.1:5000 を開きます。

停止するときは、コマンドプロンプトで `Ctrl + C` を押します。

## 週間レビューの動作確認テスト

必要ライブラリをインストールした状態で、プロジェクトフォルダから実行します。

```cmd
python -m unittest discover -s tests -v
```

テストは `smoke_test.db` というテスト専用SQLiteデータベースを使用します。通常の `home_team_pj.db` とは別です。

## データベースと既存データ

ローカル起動時はSQLiteを使用します。Flask-SQLAlchemyのSQLiteファイルは通常 `instance` フォルダ内に作成されます。修正版へ置き換える際は、既存の `instance` フォルダを削除しないでください。念のため、置き換え前にフォルダごとバックアップしてください。

複数のPC・スマートフォンで同じデータを使うには、インターネット上にWebアプリを公開し、PostgreSQL等の共有データベースを設定する必要があります。ローカルの `127.0.0.1` は、そのPC内からしかアクセスできません。

## 環境変数

`.env.example` を `.env` にコピーして使用できます。

- `SECRET_KEY`: セッション署名用のランダムな秘密鍵。本番では必ず変更
- `DATABASE_URL`: PostgreSQLを使う場合の接続URL。未設定ならSQLite
- `OPENAI_API_KEY`: AI振り返りを利用する場合のみ設定
- `OPENAI_MODEL`: AIモデルを変更する場合に設定（既定値 `gpt-4.1-mini`）
- `COOKIE_SECURE`: HTTPS本番環境では `true`

`.env` とAPIキーはGitHubなどへ公開しないでください。

## 位置情報について

- ブラウザの位置情報許可が必要です。
- 本番環境ではHTTPSが必要です（localhostは開発用の例外）。
- 位置情報ページで本人が開始ボタンを押した場合だけ取得します。停止ボタンで終了できます。
- ブラウザやOSの省電力設定により、バックグラウンド取得が止まる場合があります。
- 位置情報は個人情報です。保存・共有の範囲に注意してください。

## 公開運用について

Render等のホスティングサービスとPostgreSQLを利用できます。本番では開発サーバーではなくGunicorn等を使用し、HTTPS、強固な `SECRET_KEY`、データベースのバックアップ、利用者へのプライバシー説明を設定してください。

## 実装上の範囲

元のTkinter/PySide6版をWeb向けに再実装した統合版です。元のデスクトップ画面をそのまま移植したものではありません。予定編集、元UIの細かな入力項目、住所の逆ジオコーディング、バックグラウンドでの常時位置追跡などは未実装です。
