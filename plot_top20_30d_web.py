"""
近 30 个交易日涨跌幅 — 交互式网页报告（ECharts）。
复用 plot_top20_30d_returns 的行情拉取逻辑。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

_root = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "plot_top20_30d_returns", _root / "plot_top20_30d_returns.py"
)
_plot_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_plot_mod)

TOP20 = _plot_mod.TOP20
TRADING_DAYS = _plot_mod.TRADING_DAYS
fetch_last_window = _plot_mod.fetch_last_window
_hist_date_range = _plot_mod._hist_date_range


def collect_data() -> tuple[pd.DataFrame, list[dict], str, str]:
    start_date, end_date = _hist_date_range()
    rows: list[dict] = []
    series_list: list[dict] = []

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
        label = f"{code} {name}"
        rows.append(
            {
                "代码": code,
                "名称": name,
                "近30交易日涨跌幅(%)": round(pct, 2),
                "窗口首日收盘": round(first, 4),
                "窗口末日收盘": round(last, 4),
            }
        )
        dates = [d.strftime("%Y-%m-%d") for d in w["date"]]
        norm = (w["close"] / first * 100.0).round(2).tolist()
        series_list.append({"name": label, "dates": dates, "values": norm})

    stats = pd.DataFrame(rows)
    if stats.empty:
        raise RuntimeError("没有可用行情数据")
    return stats, series_list, start_date, end_date


def render_html(
    stats: pd.DataFrame,
    series_list: list[dict],
    start_date: str,
    end_date: str,
    out_path: Path,
) -> None:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    bar_sorted = stats.sort_values("近30交易日涨跌幅(%)", ascending=True)
    table_rows = stats.sort_values("近30交易日涨跌幅(%)", ascending=False).to_dict(
        orient="records"
    )

    payload = {
        "meta": {
            "generated_at": generated_at,
            "start_date": start_date,
            "end_date": end_date,
            "trading_days": TRADING_DAYS,
            "count": len(stats),
        },
        "series": series_list,
        "bar": {
            "labels": [
                f"{r['代码']} {r['名称']}" for _, r in bar_sorted.iterrows()
            ],
            "values": bar_sorted["近30交易日涨跌幅(%)"].tolist(),
        },
        "table": table_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>筛选股近30日走势对比</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --border: #2d3a4f;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --up: #3b82f6;
      --down: #ef4444;
      --accent: #22d3ee;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }}
    .wrap {{ max-width: 1280px; margin: 0 auto; }}
    header {{
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }}
    h1 {{ font-size: 1.6rem; font-weight: 600; margin-bottom: 8px; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; }}
    .meta span {{ margin-right: 16px; }}
    .grid {{
      display: grid;
      gap: 20px;
      margin-bottom: 20px;
    }}
    @media (min-width: 960px) {{
      .grid-2 {{ grid-template-columns: 1fr 1fr; }}
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 16px 8px;
    }}
    .card h2 {{
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 8px;
      color: var(--accent);
    }}
    .chart {{ width: 100%; height: 420px; }}
    .chart-bar {{ height: 520px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    th, td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      color: var(--muted);
      font-weight: 500;
      cursor: pointer;
      user-select: none;
    }}
    th:hover {{ color: var(--accent); }}
    tr:hover td {{ background: rgba(34, 211, 238, 0.06); }}
    .up {{ color: var(--up); }}
    .down {{ color: var(--down); }}
    .pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.8rem;
      background: rgba(34, 211, 238, 0.12);
      color: var(--accent);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>价值筛选 Top20 · 近 30 交易日走势对比</h1>
      <div class="meta">
        <span>生成时间：{generated_at}</span>
        <span>行情窗口：最近 {TRADING_DAYS} 根日线（前复权）</span>
        <span>拉取区间：{start_date} ~ {end_date}</span>
        <span class="pill">{len(stats)} 只</span>
      </div>
    </header>

    <div class="card" style="margin-bottom:20px">
      <h2>走势对比（首日收盘 = 100，可缩放 / 点击图例隐藏曲线）</h2>
      <div id="lineChart" class="chart"></div>
    </div>

    <div class="grid grid-2">
      <div class="card">
        <h2>涨跌幅排名</h2>
        <div id="barChart" class="chart chart-bar"></div>
      </div>
      <div class="card">
        <h2>数据明细（点击表头排序）</h2>
        <div style="overflow-x:auto; max-height:520px; overflow-y:auto">
          <table id="dataTable">
            <thead>
              <tr>
                <th data-key="代码">代码</th>
                <th data-key="名称">名称</th>
                <th data-key="近30交易日涨跌幅(%)">涨跌幅(%)</th>
                <th data-key="窗口首日收盘">首日收盘</th>
                <th data-key="窗口末日收盘">末日收盘</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <script>
    const DATA = {data_json};

    function pctClass(v) {{
      return v >= 0 ? "up" : "down";
    }}

    function fmtPct(v) {{
      const sign = v > 0 ? "+" : "";
      return sign + v.toFixed(2) + "%";
    }}

    // --- 表格 ---
    const tbody = document.querySelector("#dataTable tbody");
    let sortKey = "近30交易日涨跌幅(%)";
    let sortAsc = false;

    function renderTable() {{
      const rows = [...DATA.table].sort((a, b) => {{
        const va = a[sortKey], vb = b[sortKey];
        if (typeof va === "number" && typeof vb === "number") {{
          return sortAsc ? va - vb : vb - va;
        }}
        return sortAsc
          ? String(va).localeCompare(String(vb), "zh-CN")
          : String(vb).localeCompare(String(va), "zh-CN");
      }});
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td>${{r["代码"]}}</td>
          <td>${{r["名称"]}}</td>
          <td class="${{pctClass(r["近30交易日涨跌幅(%)"])}}">${{fmtPct(r["近30交易日涨跌幅(%)"])}}</td>
          <td>${{r["窗口首日收盘"]}}</td>
          <td>${{r["窗口末日收盘"]}}</td>
        </tr>`).join("");
    }}

    document.querySelectorAll("#dataTable th").forEach(th => {{
      th.addEventListener("click", () => {{
        const key = th.dataset.key;
        if (sortKey === key) sortAsc = !sortAsc;
        else {{ sortKey = key; sortAsc = key === "名称" || key === "代码"; }}
        renderTable();
      }});
    }});
    renderTable();

    // --- 折线图 ---
    const lineChart = echarts.init(document.getElementById("lineChart"));
    const allDates = DATA.series[0]?.dates || [];
    let lastMouse = {{ x: 0, y: 0 }};

    lineChart.getZr().on("mousemove", ev => {{
      lastMouse = {{ x: ev.offsetX, y: ev.offsetY }};
    }});

    function nearestParam(params) {{
      if (!params || !params.length) return null;
      let best = params[0], minDist = Infinity;
      params.forEach(p => {{
        const val = Array.isArray(p.value) ? p.value[1] : p.value;
        if (val == null || Number.isNaN(val)) return;
        const pt = lineChart.convertToPixel(
          {{ seriesIndex: p.seriesIndex }},
          [p.dataIndex, val]
        );
        if (!pt) return;
        const d = Math.hypot(pt[0] - lastMouse.x, pt[1] - lastMouse.y);
        if (d < minDist) {{ minDist = d; best = p; }}
      }});
      return best;
    }}

    lineChart.setOption({{
      backgroundColor: "transparent",
      tooltip: {{
        trigger: "axis",
        axisPointer: {{ type: "line", lineStyle: {{ color: "#64748b", type: "dashed" }} }},
        backgroundColor: "rgba(26,35,50,0.95)",
        borderColor: "#2d3a4f",
        textStyle: {{ color: "#e7ecf3" }},
        formatter: params => {{
          const p = nearestParam(params);
          if (!p) return "";
          const val = Array.isArray(p.value) ? p.value[1] : p.value;
          const date = p.axisValue || allDates[p.dataIndex] || "";
          return p.seriesName
            + (date ? "<br/>" + date : "")
            + "<br/>相对指数: " + Number(val).toFixed(2);
        }},
      }},
      legend: {{
        type: "scroll",
        bottom: 0,
        textStyle: {{ color: "#8b9cb3", fontSize: 11 }},
        pageTextStyle: {{ color: "#8b9cb3" }},
      }},
      grid: {{ left: 48, right: 24, top: 24, bottom: 72 }},
      xAxis: {{
        type: "category",
        data: allDates,
        axisLabel: {{ color: "#8b9cb3", formatter: v => v.slice(5) }},
        axisLine: {{ lineStyle: {{ color: "#2d3a4f" }} }},
      }},
      yAxis: {{
        type: "value",
        name: "相对指数",
        min: "dataMin",
        axisLabel: {{ color: "#8b9cb3" }},
        splitLine: {{ lineStyle: {{ color: "#2d3a4f", type: "dashed" }} }},
      }},
      dataZoom: [
        {{ type: "inside", start: 0, end: 100 }},
        {{ type: "slider", height: 18, bottom: 40, borderColor: "#2d3a4f" }},
      ],
      series: DATA.series.map((s, i) => ({{
        name: s.name,
        type: "line",
        smooth: true,
        triggerLineEvent: true,
        symbol: "circle",
        symbolSize: 6,
        showSymbol: false,
        lineStyle: {{ width: 1.5 }},
        emphasis: {{
          focus: "series",
          lineStyle: {{ width: 2.5 }},
        }},
        data: s.values,
        markLine: i === 0 ? {{
          silent: true,
          symbol: "none",
          lineStyle: {{ color: "#64748b", type: "dashed" }},
          data: [{{ yAxis: 100 }}],
        }} : undefined,
      }})),
    }});

    // --- 条形图 ---
    const barChart = echarts.init(document.getElementById("barChart"));
    barChart.setOption({{
      backgroundColor: "transparent",
      tooltip: {{
        trigger: "axis",
        axisPointer: {{ type: "shadow" }},
        formatter: params => {{
          const p = params[0];
          return p.name + "<br/>涨跌幅: " + fmtPct(p.value);
        }},
      }},
      grid: {{ left: 100, right: 24, top: 16, bottom: 24 }},
      xAxis: {{
        type: "value",
        name: "%",
        axisLabel: {{ color: "#8b9cb3" }},
        splitLine: {{ lineStyle: {{ color: "#2d3a4f", type: "dashed" }} }},
      }},
      yAxis: {{
        type: "category",
        data: DATA.bar.labels,
        axisLabel: {{ color: "#8b9cb3", fontSize: 11 }},
        axisLine: {{ lineStyle: {{ color: "#2d3a4f" }} }},
      }},
      series: [{{
        type: "bar",
        data: DATA.bar.values.map(v => ({{
          value: v,
          itemStyle: {{ color: v >= 0 ? "#3b82f6" : "#ef4444" }},
        }})),
        label: {{
          show: true,
          position: "right",
          formatter: p => fmtPct(p.value),
          color: "#8b9cb3",
          fontSize: 10,
        }},
      }}],
    }});

    window.addEventListener("resize", () => {{
      lineChart.resize();
      barChart.resize();
    }});
  </script>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def main() -> None:
    start_date, end_date = _hist_date_range()
    print(f"行情区间: {start_date} ~ {end_date}（截取最近 {TRADING_DAYS} 个交易日）")

    stats, series_list, start_date, end_date = collect_data()

    print("\n=== 近 30 个交易日涨跌幅 ===\n")
    print(stats.sort_values("近30交易日涨跌幅(%)", ascending=False).to_string(index=False))

    out_html = _root / "top20_30d_comparison.html"
    render_html(stats, series_list, start_date, end_date, out_html)
    print(f"\n网页已保存: {out_html}")
    print("用浏览器打开该文件即可查看交互图表。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n执行失败: {type(e).__name__}: {e}")
        sys.exit(1)
