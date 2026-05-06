import os
import random
import re
import time

import akshare as ak
import akshare.stock_feature.stock_hist_em as ak_stock_hist_em
import akshare.utils.func as ak_func
import pandas as pd


def _patch_akshare_eastmoney_clist_host() -> None:
    """
    Some networks get RST/RemoteDisconnected from numbered push2 nodes
    (e.g. 82.push2.eastmoney.com). push2delay serves the same clist API.

    stock_hist_em binds fetch_paginated_data at import time, so patch both
    akshare.utils.func and that module's global after akshare is loaded.
    """
    override = os.environ.get(
        "AKSHARE_EM_CLIST_HOST", "push2delay.eastmoney.com"
    ).strip()
    if not override or override.lower() in ("0", "false", "no"):
        return

    repl = f"https://{override}/api/qt/clist/get"
    # e.g. https://82.push2.eastmoney.com/... or https://7.push2.eastmoney.com/...
    # not push2delay / push2his
    pat = re.compile(
        r"https://(?:\d+\.)?push2\.eastmoney\.com/api/qt/clist/get\Z"
    )

    orig = ak_func.fetch_paginated_data

    def fetch_paginated_data(url: str, base_params, timeout: int = 15):
        if pat.match(url):
            url = repl
        return orig(url, base_params, timeout)

    ak_func.fetch_paginated_data = fetch_paginated_data  # type: ignore[method-assign]
    ak_stock_hist_em.fetch_paginated_data = fetch_paginated_data  # type: ignore[method-assign]


_patch_akshare_eastmoney_clist_host()


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def fetch_with_retry(
    fetch_fn,
    source_name: str,
    retries: int = 3,
    base_sleep: float = 2,
    max_sleep: float = 20,
    jitter_ratio: float = 0.25,
) -> pd.DataFrame:
    last_error = None
    for i in range(retries):
        try:
            return fetch_fn()
        except Exception as e:
            last_error = e
            print(f"[{source_name}] 第 {i + 1}/{retries} 次失败: {type(e).__name__}: {e}")
            if i < retries - 1:
                backoff = min(max_sleep, base_sleep * (2**i))
                jitter = random.uniform(0, backoff * jitter_ratio)
                wait_s = backoff + jitter
                print(f"[{source_name}] {wait_s:.1f} 秒后重试...")
                time.sleep(wait_s)
    raise last_error


def fetch_spot_data() -> tuple[pd.DataFrame, str]:
    try:
        df = fetch_with_retry(ak.stock_zh_a_spot_em, "全市场EM", retries=3, base_sleep=2)
        return df, "stock_zh_a_spot_em"
    except Exception as e:
        print(f"[全市场EM] 连续失败，尝试分市场接口兜底。原因: {type(e).__name__}: {e}")

    parts = []
    sources = [
        ("沪市EM", ak.stock_sh_a_spot_em),
        ("深市EM", ak.stock_sz_a_spot_em),
        ("北交所EM", ak.stock_bj_a_spot_em),
    ]
    for source_name, fn in sources:
        try:
            part = fetch_with_retry(fn, source_name, retries=2, base_sleep=2)
            parts.append(part)
            print(f"[{source_name}] 成功，记录数: {len(part)}")
        except Exception as e:
            print(f"[{source_name}] 失败，跳过。原因: {type(e).__name__}: {e}")

    if not parts:
        raise RuntimeError(
            "东财行情接口当前不可用，无法获取 PE/总市值。\n"
            "建议：\n"
            "1) 稍后重试；\n"
            "2) 切换网络（如关闭代理/VPN后重试）；\n"
            "3) 升级 AkShare: pip install -U akshare。"
        )

    merged = pd.concat(parts, ignore_index=True)
    code_col = pick_col(merged, ["代码", "股票代码"])
    if code_col:
        merged = merged.drop_duplicates(subset=[code_col])
    return merged, "stock_sh/sz/bj_a_spot_em"


def main() -> None:
    # 1) A股实时行情（用于 PE 和总市值）
    spot_df, spot_source = fetch_spot_data()
    print(f"\n使用行情来源: {spot_source}")
    print("=== spot_df.head() ===")
    print(spot_df.head())
    print("\n=== spot_df.shape ===")
    print(spot_df.shape)
    print("\n=== spot_df.columns ===")
    print(spot_df.columns.tolist())

    code_col = pick_col(spot_df, ["代码", "股票代码"])
    name_col = pick_col(spot_df, ["名称", "股票名称"])
    pe_col = pick_col(spot_df, ["市盈率-动态", "市盈率", "PE", "pe_ttm"])
    mv_col = pick_col(spot_df, ["总市值", "市值", "market_cap"])

    if not all([code_col, name_col, pe_col, mv_col]):
        raise ValueError(f"实时行情缺少关键字段，请检查：{spot_df.columns.tolist()}")

    spot_use = spot_df[[code_col, name_col, pe_col, mv_col]].copy()
    spot_use.columns = ["代码", "名称", "PE", "总市值"]

    # 2) 财报指标（用于 ROE）
    # 如需要可改为其他报告期：20250930 / 20250630
    fin_df = fetch_with_retry(
        lambda: ak.stock_yjbb_em(date="20251231"),
        "业绩报表EM",
        retries=3,
        base_sleep=3,
    )
    print("\n=== fin_df.head() ===")
    print(fin_df.head())
    print("\n=== fin_df.shape ===")
    print(fin_df.shape)
    print("\n=== fin_df.columns ===")
    print(fin_df.columns.tolist())

    fin_code_col = pick_col(fin_df, ["股票代码", "代码"])
    roe_col = pick_col(fin_df, ["净资产收益率", "加权净资产收益率", "ROE", "净资产收益率(%)"])

    if not all([fin_code_col, roe_col]):
        raise ValueError(f"财报数据缺少关键字段，请检查：{fin_df.columns.tolist()}")

    fin_use = fin_df[[fin_code_col, roe_col]].copy()
    fin_use.columns = ["代码", "ROE"]

    # 3) 合并并筛选
    df = pd.merge(spot_use, fin_use, on="代码", how="inner")

    for col in ["PE", "ROE", "总市值"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["PE", "ROE", "总市值"])

    filtered = df[(df["PE"] < 20) & (df["ROE"] > 15) & (df["总市值"] > 1e10)]

    result = filtered.sort_values("总市值", ascending=False).head(20).copy()
    result["PE"] = result["PE"].round(2)
    result["ROE"] = result["ROE"].round(2)
    result["总市值(亿元)"] = (result["总市值"] / 1e8).round(2)
    result = result[["代码", "名称", "PE", "ROE", "总市值(亿元)"]]

    print("\n=== 筛选结果（前20）===")
    if result.empty:
        print("未筛选到满足条件的股票，请检查数据源或放宽条件。")
    else:
        print(result.to_string(index=False))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n脚本执行失败：", f"{type(e).__name__}: {e}")
        print("请稍后重试，或切换网络后再运行。")
