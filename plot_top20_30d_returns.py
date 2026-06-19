"""
近 30 个交易日涨跌幅与走势对比（与 screen_a_share 筛选结果一致的前 20 只，PE>0 版本）。
运行前会应用与 screen_a_share 相同的东财 clist host 补丁。
"""

from __future__ import annotations

import importlib.util
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import akshare as ak
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# 应用 screen_a_share 中的 push2delay 补丁
_root = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("screen_a_share", _root / "screen_a_share.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

# 与 screen_a_share 筛选结果一致的前 20 只：代码、名称
TOP20: list[tuple[str, str]] = [
    ("600519", "贵州茅台"),
    ("600938", "中国海油"),
    ("601628", "中国人寿"),
    ("601899", "紫金矿业"),
    ("000333", "美的集团"),
    ("603993", "洛阳钼业"),
    ("603259", "药明康德"),
    ("601319", "中国人保"),
    ("601601", "中国太保"),
    ("301308", "江波龙"),
    ("601225", "陕西煤业"),
    ("002379", "宏桥控股"),
    ("000651", "格力电器"),
    ("002714", "牧原股份"),
    ("603288", "海天味业"),
    ("600690", "海尔智家"),
    ("688525", "佰维存储"),
    ("601336", "新华保险"),
    ("300760", "迈瑞医疗"),
    ("001309", "德明利"),
]

TRADING_DAYS = 30
# 约 4 个月自然日，覆盖 30 个交易日
LOOKBACK_DAYS = 130


def _ymd_dashed(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def _hist_date_range() -> tuple[str, str]:
    end = datetime.now().date()
    start = end - timedelta(days=LOOKBACK_DAYS)
    return _ymd_dashed(start), _ymd_dashed(end)


def _to_tx_symbol(code: str) -> str:
    """沪深 A 股 -> 腾讯行情代码 sh600519 / sz000001。"""
    if code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"


def _fetch_hist_tx(code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """腾讯日 K（前复权），避免东财 push2his 断连。"""
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=_to_tx_symbol(code),
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
    except Exception:
        return None
    if df is None or df.empty or "close" not in df.columns:
        return None
    out = df[["date", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["close"]).sort_values("date")
    if len(out) < TRADING_DAYS:
        return None
    return out.tail(TRADING_DAYS).reset_index(drop=True)


def _fetch_hist_em_with_retry(
    code: str, start_ymd: str, end_ymd: str, retries: int = 3
) -> pd.DataFrame | None:
    """东财日 K 兜底（带重试）。"""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_ymd,
                end_date=end_ymd,
                adjust="qfq",
            )
        except Exception as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))
            continue
        if df is None or df.empty:
            continue
        for dcol, ccol in (("日期", "收盘"), ("date", "close")):
            if dcol in df.columns and ccol in df.columns:
                out = df[[dcol, ccol]].copy()
                out.columns = ["date", "close"]
                out["date"] = pd.to_datetime(out["date"])
                out["close"] = pd.to_numeric(out["close"], errors="coerce")
                out = out.dropna(subset=["close"]).sort_values("date")
                if len(out) >= TRADING_DAYS:
                    return out.tail(TRADING_DAYS).reset_index(drop=True)
                break
    if last_err is not None:
        print(f"  [东财兜底失败] {code}: {type(last_err).__name__}: {last_err}")
    return None


def fetch_last_window(code: str, start_dashed: str, end_dashed: str) -> pd.DataFrame | None:
    w = _fetch_hist_tx(code, start_dashed, end_dashed)
    if w is not None:
        return w
    start_ymd = start_dashed.replace("-", "")
    end_ymd = end_dashed.replace("-", "")
    return _fetch_hist_em_with_retry(code, start_ymd, end_ymd)


def main() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    start_date, end_date = _hist_date_range()
    print(f"行情区间: {start_date} ~ {end_date}（用于截取最近 {TRADING_DAYS} 个交易日）")

    rows: list[dict] = []
    series_list: list[tuple[str, pd.DataFrame]] = []

    for code, name in TOP20:
        w = fetch_last_window(code, start_date, end_date)
        time.sleep(0.25)
        if w is None or w.empty:
            print(f"[跳过] {code} {name}: 无足够行情")
            continue
        first = float(w["close"].iloc[0])
        last = float(w["close"].iloc[-1])
        if first == 0:
            continue
        pct = (last / first - 1.0) * 100.0
        rows.append(
            {
                "代码": code,
                "名称": name,
                "近30交易日涨跌幅(%)": round(pct, 2),
                "窗口首日收盘": round(first, 4),
                "窗口末日收盘": round(last, 4),
            }
        )
        norm = w.copy()
        norm["norm"] = norm["close"] / first * 100.0
        series_list.append((f"{code} {name}", norm))

    stats = pd.DataFrame(rows)
    if stats.empty:
        print("没有可用数据，退出。")
        sys.exit(1)

    print("\n=== 近 30 个交易日涨跌幅（前复权收盘，窗口为最近 30 根日线）===\n")
    print(stats.to_string(index=False))
    print("\n（行情优先：腾讯前复权日线 stock_zh_a_hist_tx；失败时兜底东财 stock_zh_a_hist）")

    fig, (ax0, ax1) = plt.subplots(
        2,
        1,
        figsize=(14, 11),
        gridspec_kw={"height_ratios": [2.2, 1.0]},
    )
    colors = plt.cm.tab20.colors

    for i, (label, norm) in enumerate(series_list):
        ax0.plot(
            norm["date"],
            norm["norm"],
            label=label,
            linewidth=1.2,
            color=colors[i % len(colors)],
            alpha=0.9,
        )

    ax0.axhline(100.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax0.set_title("前 20 筛选股：近 30 个交易日走势对比（首日收盘=100）")
    ax0.set_ylabel("相对指数（首日=100）")
    ax0.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax0.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax0.grid(True, alpha=0.3)
    ax0.set_xlabel("日期")
    ax0.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8, ncol=1)

    bar = stats.sort_values("近30交易日涨跌幅(%)", ascending=True)
    y_pos = range(len(bar))
    bar_colors = ["#c44e52" if v < 0 else "#4c72b0" for v in bar["近30交易日涨跌幅(%)"]]
    ax1.barh(y_pos, bar["近30交易日涨跌幅(%)"], color=bar_colors, height=0.65, alpha=0.85)
    ax1.set_yticks(list(y_pos))
    ax1.set_yticklabels([f"{r['代码']} {r['名称']}" for _, r in bar.iterrows()])
    ax1.axvline(0.0, color="gray", linewidth=0.8)
    ax1.set_xlabel("近 30 个交易日涨跌幅 (%)")
    ax1.set_title("涨跌幅排名（同窗口）")
    ax1.grid(True, axis="x", alpha=0.3)

    fig.autofmt_xdate()
    out_png = _root / "top20_30d_comparison.png"
    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n图表已保存: {out_png}")


if __name__ == "__main__":
    main()
