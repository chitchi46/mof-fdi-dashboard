# Country-Level Comparison Charts (Pie/Bar)

## Goal
- 各国（国・経済グループを含む）を横断して比較できる円グラフ・棒グラフのビューをダッシュボードに追加し、最新年の構成比やトップN比較、年切替などの操作に対応する。

## Scope
- 既存の地域辞書（`data/dictionaries/regions.yml`）を活用し、`segment_region` を国レベルまで正規化したうえで集計。
- サマリ生成（`summary.json`）を拡張し、国別の構成比・ランキング（トップN）のデータを提供。
- フロントエンドに新規ビュー：
  - 円グラフ（最新年の国別構成比）
  - 棒グラフ（国別トップN、年選択可能・並び替え options）
- 既存の地域分析計画（`.plans/region-analysis.md`）に依存。重複する「地域の抽出/正規化」自体は本タスクでは扱わない。

## Deliverables
- サマリ拡張：`summary.json` に `regions.composition`（既存）と並行して、国別 `countries.composition`、`countries.rankings` を追加。
- 集計ユーティリティ：`aggregate_by_country`（年・metric/side でのフィルタ対応、トップN抽出、シェア計算）。
- UI 追加：ビュー `country_pie`、`country_bar`（年セレクタ、トップNスライダ、ソート切替）。
- ドキュメント更新：`docs/USAGE.md` に新ビューの説明と操作手順。

## Work Breakdown
1. 要件定義・仕様
   - 円グラフ：最新年×国別の構成比。デフォルトは上位N＋その他集約（NはUIで可変）。
   - 棒グラフ：選択年×国別の値（降順）。ソート軸（値/国名）、表示数（N）をUIで切替。
   - フィルタ整合：`side`/`metric`/年範囲/地域選択と整合（国は地域配下の概念として扱う）。
2. データ層（集計）
   - 既存 `build_summary_multi_measure` を拡張または新関数を追加し、`segment_region` が国レベルの行を抽出→集計。
   - `latest_year` の決定ロジックを共通化（欠損時のフォールバック含む）。
3. API/サマリ形式
   - `summary.json` へ `countries` セクション（`available`, `composition`, `rankings`）を追加。後方互換維持。
4. UI 実装（非コーディング方針の骨子）
   - ビュータブへ「国別（円）」「国別（棒）」を追加。
   - 年セレクタ、Nスライダ、ソート切替、ツールチップ（国名＋値＋シェア）。
   - 色割当の安定化（国名ハッシュ等）。
5. ドキュメント
   - `docs/USAGE.md` に操作例（年変更、N変更、エクスポートとの連携）。
6. 検証
   - サンプルCSVで国別抽出が期待通りか手動QA（表示・エクスポート整合）。

## Dependencies
- `.plans/region-analysis.md`（地域/国辞書、抽出精度）。

## Risks & Mitigations
- 国・地域の重複/別名（例：UK/英国/イギリス）→ 辞書統合・別名吸収で対応。
- 小国多数で円グラフが煩雑 → 上位N＋その他集約、凡例スクロール。

## Acceptance Criteria
- 円/棒の両ビューで国別比較が可能（最新年構成比、任意年トップN）。
- フィルタ（side/metric/年範囲）を反映し、`/api/export` のCSVにも一致。
- 既存ビューへの影響なし（後方互換）。

