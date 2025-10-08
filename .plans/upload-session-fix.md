# Upload Session & Export Consistency Fix

## Issue
- 新しくCSVをアップロードできるが、実際の分析/エクスポートが特定の（既定の）ファイルに固定されるケースがある。
- 想定原因（現状の挙動）
  - 画面表示は直近アップロードの`summary`を使うが、`/api/export` は `build/normalized.csv` 等の固定パスを参照しているため、別データをエクスポートしてしまう。
  - セッションID（`/uploads/<sid>/...`）がエクスポート要求に伝搬していない。

## Goal
- アップロードごとにセッションIDを払い出し、可視化・エクスポート・ダウンロードで同一セッションのデータを一貫して使用する。
- 連続アップロード時も、その都度のセッション単位で正しく分析・可視化・エクスポートできる。

## Scope
- API: `/api/export` をセッション対応に変更（例: `/api/export/<sid>` または クエリ `?sid=...`）。
- UI: `uploadAndAnalyze()` で受け取る `sid` を保持し、エクスポート時URLへ付与。
- サーバ: エクスポート時に `uploads/<sid>/normalized.csv` を参照するよう修正。
- 互換: 既存の`build/summary.json`がある場合でも、新規アップロードの導線を常時表示（導線は `.plans/upload-flow-fix.md` 参照）。

## Deliverables
- セッション対応した `/api/export`（サーバ側）
- セッションIDをUI状態に保持し、`CSVエクスポート`・リンク群の更新に反映
- ドキュメント更新（連続アップロードの想定フローを明記）

## Acceptance Criteria
- 任意のCSVをアップロード→表示→エクスポートで、同一データに基づく一致した結果が得られる。
- 連続アップロードでも、直近のセッションIDが常に利用され、他のデータが混入しない。

