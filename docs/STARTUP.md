# 起動方法（WSL/Ubuntu 専用・PowerShell 非対応）

このプロジェクトは Linux 環境（WSL/Ubuntu）での実行を前提としています。PowerShell は使用しません。以下は bash 上での手順です。

## 0. 事前準備
- Ubuntu のターミナル（bash）を開く
- リポジトリへ移動
```
cd /home/uka_agai/mof_investviz
```

## 1. 仮想環境と依存関係のセットアップ
```
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## 2. 起動方法A（アップロード型ダッシュボード）
ローカルの CSV をブラウザからアップロードして解析・可視化します。
```
python3 scripts/serve_upload_dashboard.py --host 0.0.0.0 --port 8000
```
アクセス: http://localhost:8000/

## 3. 起動方法B（サンプルデータでビルドして表示）
サンプルの `data/` を正規化して build に出力し、その結果を表示します。
```
python3 scripts/run_pipeline.py --input data --build-dir build
python3 scripts/serve_dashboard.py --build-dir build --host 0.0.0.0 --port 8000
```
アクセス: http://localhost:8000/

## 4. トラブルシュート
- 仮想環境未有効: `source .venv/bin/activate`
- ポート競合: `--port 8001` 等に変更
- localhost で開けない: `hostname -I` で WSL の IP を確認し `http://<IP>:8000` でアクセス
- 依存が足りない/インストール失敗: `pip install -r requirements.txt` を再実行

## 5. 補足
- 対応シェルは bash のみです。PowerShell は使用しません。
- 追加の外部サービスや DB は不要（標準ライブラリ + pandas などの依存のみ）。

