from __future__ import annotations

import os
import re
import unicodedata
import yaml
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .io import read_csv_matrix


# Schema columns (normalized tidy format)
SCHEMA_HEADERS = [
    "year",
    "fiscal_year",
    "year_jp",
    "side",
    "metric",
    "measure",
    "segment_region",
    "segment_industry",
    "segment_other",
    "value_100m_yen",
    "qa_flag",
    "flag_outlier",
    "flag_break",
]


# -------------------- Basic parsing helpers --------------------

_NAN_TOKENS = {"", "--", "-", "...", "n.a.", "na", "n/a", "*"}


def _clean_numeric_token(v: object) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return float(v)
        except Exception:
            return None
    s = str(v)
    s = s.strip()
    if s.lower() in _NAN_TOKENS:
        return None
    # Parentheses-negative: (123)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    # Normalize full-width forms; remove thousand separators and spaces
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(",", "").replace(" ", "")
    if s in {"", "-", "."}:
        return None
    try:
        val = float(s)
        return -val if neg else val
    except Exception:
        return None


def to_float(v: object) -> Optional[float]:
    return _clean_numeric_token(v)


YEAR_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"^year$", r"fiscal_?year", r"年度", r"西暦", r"^cy$", r"年(度)?$",
    ]
]


def identify_year_column(rows: Sequence[Dict[str, str]], headers: Sequence[str]) -> Optional[str]:
    # Prefer headers matching patterns
    for h in headers:
        if h is None:
            continue
        name = str(h)
        if any(p.search(name) for p in YEAR_PATTERNS):
            return h
    # Fallback: a column with 4-digit integers predominantly between 1900-2100
    sample = rows[: min(100, len(rows))]
    candidates: List[Tuple[str, float]] = []
    for h in headers:
        if h is None:
            continue
        vals = []
        for r in sample:
            v = r.get(h)
            try:
                iv = int(str(v).strip())
            except Exception:
                continue
            vals.append(iv)
        if not vals:
            continue
        in_range = [1900 <= v <= 2100 for v in vals]
        score = sum(in_range) / len(vals)
        if score >= 0.7:
            candidates.append((h, score))
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    return None


def identify_numeric_columns(rows: Sequence[Dict[str, str]], headers: Sequence[str]) -> List[str]:
    numeric_cols: List[str] = []
    sample = rows[: min(100, len(rows))]
    for h in headers:
        if h is None:
            continue
        vals = [to_float(r.get(h)) for r in sample]
        count_num = sum(1 for x in vals if isinstance(x, float))
        count_nonempty = sum(1 for x in (r.get(h) for r in sample) if str(x).strip() != "")
        if count_nonempty > 0 and count_num / count_nonempty >= 0.5:
            numeric_cols.append(h)
    return numeric_cols


# -------------------- Year headers (wide years) --------------------

_YEAR4 = re.compile(r"^(19\d{2}|20\d{2}|21\d{2})$")
_YEAR4_JP = re.compile(r"^(19\d{2}|20\d{2}|21\d{2})年$")


def parse_year_from_header(name: str) -> Optional[int]:
    s = str(name).strip()
    m = _YEAR4.match(s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    m = _YEAR4_JP.match(s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


# -------------------- Region dictionary and extraction --------------------

_REGION_DICT_CACHE: Optional[List[Dict[str, object]]] = None


def load_region_dictionary() -> List[Dict[str, object]]:
    """地域辞書を読み込む（キャッシュ付き）"""
    global _REGION_DICT_CACHE
    if _REGION_DICT_CACHE is not None:
        return _REGION_DICT_CACHE
    
    # プロジェクトルートからの相対パス
    dict_path = Path(__file__).parent.parent.parent / "data" / "dictionaries" / "regions.yml"
    
    if not dict_path.exists():
        # 辞書が見つからない場合は空リストを返す
        _REGION_DICT_CACHE = []
        return _REGION_DICT_CACHE
    
    with open(dict_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    _REGION_DICT_CACHE = data.get("regions", [])
    return _REGION_DICT_CACHE


def extract_region_from_text(text: str) -> Optional[str]:
    """テキストから地域名を抽出し、正規化された地域名を返す
    
    Args:
        text: 検索対象のテキスト
    
    Returns:
        正規化された地域名（日本語）、見つからない場合はNone
    """
    if not text:
        return None
    
    regions = load_region_dictionary()
    text_lower = text.lower().strip()
    text_normalized = text.strip()
    
    # スコアリングシステム：より具体的な地域（国レベル）を優先
    matches = []
    
    for region in regions:
        canonical = region.get("canonical", "")
        canonical_en = region.get("canonical_en", "")
        aliases_ja = region.get("aliases_ja", [])
        aliases_en = region.get("aliases_en", [])
        level = region.get("level", "region")
        
        # レベルによる優先度（国 > グループ > 地域）
        priority = {"country": 3, "group": 2, "region": 1, "total": 0}.get(level, 0)
        
        # 日本語エイリアスのマッチング
        for alias in aliases_ja:
            if alias in text_normalized:
                match_len = len(alias)
                matches.append((canonical, priority, match_len))
                break
        
        # 英語エイリアスのマッチング（大文字小文字を区別しない）
        for alias in aliases_en:
            if alias.lower() in text_lower:
                match_len = len(alias)
                matches.append((canonical, priority, match_len))
                break
    
    if not matches:
        return None
    
    # 優先度が高く、マッチ長が長いものを選択
    matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return matches[0][0]


def extract_region_from_header(header: str) -> Optional[str]:
    """ヘッダー文字列から地域を抽出
    
    Args:
        header: ヘッダー文字列（" / "で区切られた多層ヘッダーの可能性あり）
    
    Returns:
        正規化された地域名、見つからない場合はNone
    """
    if not header:
        return None
    
    # " / "で分割されている場合、各部分を検査
    parts = header.split(" / ")
    for part in parts:
        region = extract_region_from_text(part)
        if region:
            return region
    
    # 全体でも試行
    return extract_region_from_text(header)


def get_region_level(region_name: str) -> Optional[str]:
    """地域名から level を取得
    
    Args:
        region_name: 正規化された地域名（日本語）
    
    Returns:
        level（'country', 'region', 'group', 'total'）、見つからない場合はNone
    """
    if not region_name:
        return None
    
    regions = load_region_dictionary()
    for region in regions:
        canonical = region.get("canonical", "")
        if canonical == region_name:
            return region.get("level")
    
    return None


# -------------------- Unit / side / metric detection --------------------

UNIT_SCALES = [
    (re.compile(r"兆円|trillion\s*y(en)?", re.I), 10000.0),
    (re.compile(r"億円|100\s*million\s*y(en)?", re.I), 1.0),
    (re.compile(r"十億円|billion\s*y(en)?", re.I), 10.0),
    (re.compile(r"百万円|million\s*y(en)?", re.I), 0.01),
    (re.compile(r"千万円", re.I), 0.1),
    (re.compile(r"万円|ten\s*thousand\s*y(en)?", re.I), 0.0001),
]


def detect_unit_scale(texts: Sequence[str]) -> Tuple[str, float]:
    joined = " / ".join([t for t in texts if t])
    for pat, scale in UNIT_SCALES:
        if pat.search(joined):
            return pat.pattern, scale
    return "", 1.0


def detect_side(texts: Sequence[str]) -> str:
    joined = " ".join([t.lower() for t in texts if t])
    if any(k in joined for k in ["対外", "outward", "assets"]):
        return "assets"
    if any(k in joined for k in ["対内", "inward", "liabilities"]):
        return "liabilities"
    return "unknown"


def detect_metric(texts: Sequence[str]) -> str:
    joined = " ".join([t.lower() for t in texts if t])
    if any(k in joined for k in ["再投資", "reinvested"]):
        return "reinvested"
    if any(k in joined for k in ["ネット", "純", "net "]):
        return "net"
    if any(k in joined for k in ["フロー", "flow"]):
        return "flow"
    return "unknown"


# -------------------- Multi-row header handling --------------------

def is_numeric_token(s: str) -> bool:
    return to_float(s) is not None


def is_annotation_row(row: Sequence[str]) -> bool:
    """注釈・脚注行かどうかを判定"""
    if not row:
        return False
    first_col = str(row[0]).strip()
    # 注釈マーカー
    annotation_markers = ["（備考）", "(NOTE)", "注:", "Note:", "注釈", "※"]
    if any(marker in first_col for marker in annotation_markers):
        return True
    # 数字や記号で始まる説明文（①、②、(1)、など）
    if first_col and (first_col[0] in "①②③④⑤⑥⑦⑧⑨⑩" or 
                      (len(first_col) > 1 and first_col[0] in "123456789" and first_col[1] in ".)、")):
        return True
    return False


def is_title_row(row: Sequence[str]) -> bool:
    """タイトル行かどうかを判定（データヘッダーではない）"""
    if not row:
        return False
    first_col = str(row[0]).strip()
    non_empty = [c for c in row if str(c).strip()]
    
    # ほとんどの列が空でない場合はタイトルではない
    if len(non_empty) > len(row) * 0.3:
        return False
    
    # タイトルっぽいキーワード
    title_keywords = ["Balance of Payments", "統計", "Statistics", 
                     "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ",
                     "（単位", "(単位", "Unit:", "(100 million"]
    return any(keyword in first_col for keyword in title_keywords)


def detect_header_rows(matrix: Sequence[Sequence[str]], max_check: int = 40) -> int:
    """改善版: 注釈やタイトルを除外し、実際のデータヘッダーを検出"""
    if not matrix or len(matrix) < 2:
        return 1
    
    # ステップ1: タイトル・注釈行を全てスキップ
    skip_until = 0
    for i in range(min(max_check, len(matrix))):
        row = matrix[i]
        if is_annotation_row(row) or is_title_row(row):
            skip_until = i + 1
    
    # ステップ2: スキップ後の最初の連続空行グループを探す
    in_empty_group = False
    empty_group_start = skip_until
    header_start = skip_until
    
    for i in range(skip_until, min(skip_until + 20, len(matrix))):
        row = matrix[i]
        is_empty = not any(str(c).strip() for c in row)
        
        if is_empty:
            if not in_empty_group:
                empty_group_start = i
                in_empty_group = True
        else:
            if in_empty_group:
                # 空行グループが終わった - この行からヘッダー開始
                header_start = i
                break
            in_empty_group = False
    
    # ステップ3: データ開始行を探す（年の表記がある行）
    data_start = header_start + 1
    for i in range(header_start, min(header_start + 15, len(matrix))):
        row = matrix[i]
        if len(row) > 0:
            first_col = str(row[0]).strip()
        else:
            first_col = ""
        
        # 空行はスキップ
        if not any(str(c).strip() for c in row):
            continue
        
        # 年表記を含む行はデータ開始（ただし、（暦年）などのラベル行は除外）
        year_markers = ["C.Y.", "F.Y.", "平成", "令和", "昭和"]
        # 年だけのラベル行を除外
        exclude_markers = ["（暦年）", "(Annual", "(Monthly", "(Quarterly"]
        
        has_year_marker = any(marker in first_col for marker in year_markers)
        is_label_only = any(marker in first_col for marker in exclude_markers) or first_col in ["（暦年）", "(Annual figures)", "(Monthly figures)"]
        
        if has_year_marker and not is_label_only:
            data_start = i
            break
        
        # または、最初の列が年で2列目以降に数値が多い行
        if len(row) > 4:
            non_empty = [c for c in row[1:] if str(c).strip()]  # 最初の列を除く
            if len(non_empty) > len(row) * 0.2:
                numeric_count = sum(1 for c in non_empty if is_numeric_token(str(c)))
                numeric_ratio = numeric_count / len(non_empty) if non_empty else 0
                
                # 50%以上が数値ならデータ行
                if numeric_ratio >= 0.5:
                    data_start = i
                    break
    
    # ステップ4: ヘッダー開始からデータ開始の直前まで
    header_rows = data_start - header_start
    if header_rows < 1:
        header_rows = 1
    
    # ヘッダーは最大10行まで
    return min(header_start + header_rows, header_start + 10)


def build_headers(matrix: Sequence[Sequence[str]], header_rows: int) -> List[str]:
    cols = max((len(r) for r in matrix[:header_rows]), default=0)
    tokens: List[List[str]] = [[] for _ in range(cols)]
    carry: List[str] = [""] * cols
    for r in range(header_rows):
        row = list(matrix[r]) + [""] * (cols - len(matrix[r]))
        for c in range(cols):
            val = row[c].strip()
            if val:
                carry[c] = val
            tokens[c].append(carry[c])
    headers = [" / ".join([t for t in toks if t]).strip() or f"col_{i}" for i, toks in enumerate(tokens)]
    return headers


def matrix_to_dict_rows(matrix: Sequence[Sequence[str]], headers: Sequence[str], start_row: int) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    cols = len(headers)
    for r in range(start_row, len(matrix)):
        row = list(matrix[r]) + [""] * (cols - len(matrix[r]))
        rows.append({headers[c]: row[c] for c in range(cols)})
    return rows


# -------------------- Normalization --------------------

def normalize_rows(
    rows: Sequence[Dict[str, str]],
    headers: Sequence[str],
    *,
    side: str = "unknown",
    metric: str = "unknown",
    scale_factor: float = 1.0,
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    numeric_cols = identify_numeric_columns(rows, headers)
    year_col = identify_year_column(rows, headers)

    norm: List[Dict[str, object]] = []

    if year_col:
        # Typical case: each row has a year column; numeric columns are measures
        for r in rows:
            year_val = None
            try:
                year_val = int(str(r.get(year_col, "").strip()) or 0) or None
            except Exception:
                year_val = None
            for col in numeric_cols:
                v = to_float(r.get(col))
                if v is None:
                    continue
                # ヘッダーから地域を抽出
                region = extract_region_from_header(col)
                norm.append({
                    "year": year_val,
                    "fiscal_year": None,
                    "year_jp": None,
                    "side": side,
                    "metric": metric,
                    "measure": col,
                    "segment_region": region,
                    "segment_industry": None,
                    "segment_other": None,
                    "value_100m_yen": v * float(scale_factor),
                    "qa_flag": None,
                    "flag_outlier": None,
                    "flag_break": None,
                })
    else:
        # Fallback: wide layout where headers are years
        year_headers: List[Tuple[str, int]] = []
        for h in headers:
            y = parse_year_from_header(str(h))
            if y:
                year_headers.append((h, y))
        if year_headers:
            # pick identifier columns (non-year, mostly non-numeric)
            id_candidates: List[str] = []
            sample = rows[: min(50, len(rows))]
            for h in headers:
                if any(h == yh for yh, _ in year_headers):
                    continue
                vals = [str(r.get(h, "")).strip() for r in sample]
                nonempty = [v for v in vals if v != ""]
                if not nonempty:
                    continue
                num_ratio = sum(1 for v in nonempty if to_float(v) is not None) / len(nonempty)
                if num_ratio < 0.5:
                    id_candidates.append(h)
            id_candidates = id_candidates[:3]  # keep it compact

            for idx, r in enumerate(rows):
                label_parts = [str(r.get(h, "")).strip() for h in id_candidates if str(r.get(h, "")).strip()]
                measure_label = " / ".join(label_parts) if label_parts else f"row_{idx}"
                # ラベルから地域を抽出
                region = extract_region_from_text(measure_label)
                for h, y in year_headers:
                    v = to_float(r.get(h))
                    if v is None:
                        continue
                    norm.append({
                        "year": y,
                        "fiscal_year": None,
                        "year_jp": None,
                        "side": side,
                        "metric": metric,
                        "measure": measure_label,
                        "segment_region": region,
                        "segment_industry": None,
                        "segment_other": None,
                        "value_100m_yen": v * float(scale_factor),
                        "qa_flag": None,
                        "flag_outlier": None,
                        "flag_break": None,
                    })

    stats = {
        "rows_in": len(rows),
        "rows_out": len(norm),
        "numeric_columns": numeric_cols,
        "year_column": year_col,
        "scale_factor": scale_factor,
    }
    return norm, stats


def add_outlier_flags(norm_rows: List[Dict[str, object]]) -> None:
    by_measure: Dict[str, List[Tuple[Optional[int], float, int]]] = defaultdict(list)
    for i, r in enumerate(norm_rows):
        m = str(r.get("measure"))
        y = r.get("year")
        v = r.get("value_100m_yen")
        if isinstance(v, (int, float)):
            by_measure[m].append((y, float(v), i))
    def median(x: List[float]) -> float:
        s = sorted(x)
        n = len(s)
        return 0.5 * (s[n//2] + s[(n-1)//2])
    for m, items in by_measure.items():
        vals = [v for (_, v, _) in items]
        if len(vals) < 8:
            continue
        med = median(vals)
        abs_dev = [abs(v - med) for v in vals]
        mad = median(abs_dev) or 1e-9
        for (y, v, idx) in items:
            rzs = 0.6745 * (v - med) / mad
            if abs(rzs) >= 3.5:
                norm_rows[idx]["flag_outlier"] = True
                prev = norm_rows[idx].get("qa_flag") or ""
                norm_rows[idx]["qa_flag"] = (prev + ";" if prev else "") + "outlier"


def build_summary_multi_measure(norm_rows: List[Dict[str, object]], top_n: int = 5) -> Dict[str, object]:
    agg: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    years_set: set[str] = set()
    regions_set: set[str] = set()
    countries_set: set[str] = set()
    
    # 地域別・年別の集計
    region_agg: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    # 国別・年別の集計（level=='country'のみ）
    country_agg: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    
    for r in norm_rows:
        m = str(r.get("measure"))
        y = r.get("year")
        yk = str(y) if y is not None else ""
        v = float(r.get("value_100m_yen") or 0.0)
        region = r.get("segment_region")
        
        agg[m][yk] += v
        if yk:
            years_set.add(yk)
        
        # 地域別集計
        if region:
            regions_set.add(region)
            region_agg[region][yk] += v
            
            # 国レベルのみを分離して集計
            level = get_region_level(region)
            if level == "country":
                countries_set.add(region)
                country_agg[region][yk] += v
    
    years = sorted(years_set)
    totals = [(m, sum(d.values())) for m, d in agg.items()]
    totals.sort(key=lambda x: x[1], reverse=True)
    measures = [m for m, _ in totals[:top_n]]
    series = []
    for m in measures:
        d = agg[m]
        series.append({"label": m, "x": years, "y": [d.get(y, 0.0) for y in years]})
    latest = years[-1] if years else ""
    comp_labels = measures
    comp_values = [agg[m].get(latest, 0.0) for m in measures]
    comp_sum = sum(comp_values) or 1.0
    comp_share = [v/comp_sum for v in comp_values]
    
    # 地域別サマリの構築（全地域・グループ・国を含む）
    regions_list = sorted(regions_set)
    region_series = []
    for region in regions_list:
        d = region_agg[region]
        region_series.append({
            "label": region,
            "x": years,
            "y": [d.get(y, 0.0) for y in years]
        })
    
    # 地域別構成比（最新年）
    region_comp_values = [region_agg[r].get(latest, 0.0) for r in regions_list]
    region_comp_sum = sum(region_comp_values) or 1.0
    region_comp_share = [v/region_comp_sum for v in region_comp_values]
    
    # 国別サマリの構築（level=='country'のみ）
    countries_list = sorted(countries_set)
    country_series = []
    for country in countries_list:
        d = country_agg[country]
        country_series.append({
            "label": country,
            "x": years,
            "y": [d.get(y, 0.0) for y in years]
        })
    
    # 国別ランキング（最新年・降順）
    country_rankings = []
    for country in countries_list:
        val = country_agg[country].get(latest, 0.0)
        if val > 0:
            country_rankings.append({"country": country, "value": val})
    country_rankings.sort(key=lambda x: x["value"], reverse=True)
    
    # 国別構成比（最新年）
    country_comp_values = [country_agg[c].get(latest, 0.0) for c in countries_list]
    country_comp_sum = sum(country_comp_values) or 1.0
    country_comp_share = [v/country_comp_sum for v in country_comp_values]
    
    result = {
        "title": "MVP Summary",
        "years": years,
        "series": series,
        "views": ["timeseries", "yoy_diff", "composition"],
        "composition": {"year": latest, "labels": comp_labels, "share": comp_share},
    }
    
    # 地域データがある場合のみ追加（全地域・グループ・国を含む）
    if regions_list:
        result["regions"] = {
            "available": regions_list,
            "series": region_series,
            "composition": {
                "year": latest,
                "labels": regions_list,
                "values": region_comp_values,
                "share": region_comp_share
            }
        }
    
    # 国別データがある場合のみ追加（level=='country'のみ）
    if countries_list:
        result["countries"] = {
            "available": countries_list,
            "series": country_series,
            "rankings": country_rankings,
            "composition": {
                "year": latest,
                "labels": countries_list,
                "values": country_comp_values,
                "share": country_comp_share
            }
        }
    
    return result


@dataclass
class NormalizeResult:
    rows: List[Dict[str, object]]
    headers: List[str]
    stats: Dict[str, object]
    meta: Dict[str, object]


def normalize_file(path: str) -> NormalizeResult:
    matrix, meta = read_csv_matrix(path)
    hrows = detect_header_rows(matrix)
    headers = build_headers(matrix, hrows)
    texts = headers + [os.path.basename(path)]
    unit_pat, scale = detect_unit_scale(texts)
    side = detect_side(texts)
    metric = detect_metric(texts)
    rows_raw = matrix_to_dict_rows(matrix, headers, start_row=hrows)
    norm_rows, stats = normalize_rows(rows_raw, headers, side=side, metric=metric, scale_factor=scale)
    add_outlier_flags(norm_rows)
    meta.update({
        "header_rows": hrows,
        "unit_detected": unit_pat,
        "scale_factor": scale,
        "side": side,
        "metric": metric,
    })
    return NormalizeResult(rows=norm_rows, headers=list(headers), stats=stats, meta=meta)
