#!/usr/bin/env python3
"""
src/stats/daily_stats.py
Daily statistics report: PNG + HTML via Discord webhook (multipart).
Runs at 23:10 KST after backup. Designed to work from day 1.
"""
from __future__ import annotations

import io
import json
import logging
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

PROJECT_ROOT = Path("/srv/Capstone")
OUTPUT_DIR   = PROJECT_ROOT / "outputs" / "stats"
LOG_DIR      = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "daily_stats.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

ENV_FILE = PROJECT_ROOT / ".env"
MYSQL_CONTAINER = "capstone-mysql"
TODAY = date.today().isoformat()


def _load_env() -> dict:
    env = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_ENV           = _load_env()
MYSQL_DB       = _ENV.get("MYSQL_DATABASE", "capstone_db")
MYSQL_PWD      = _ENV.get("MYSQL_ROOT_PASSWORD", "")
WEBHOOK_URL    = _ENV.get("DISCORD_WEBHOOK_URL", "")

# ───────────────────────────── DB helpers ────────────────────────────────────

def _run_sql(sql: str) -> list[list[str]]:
    cmd = [
        "docker", "exec", MYSQL_CONTAINER,
        "mysql", "-h", "127.0.0.1", "-uroot", f"-p{MYSQL_PWD}",
        "-N", "--batch", "--silent", MYSQL_DB, "-e", sql,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if not r.stdout.strip():
            return []
        return [line.split("\t") for line in r.stdout.strip().splitlines()]
    except Exception as e:
        log.error("SQL failed: %s", e)
        return []


def _int(rows: list, default: int = 0) -> int:
    try:
        return int(rows[0][0])
    except Exception:
        return default


# ───────────────────────────── Queries ───────────────────────────────────────

def q_summary() -> dict:
    today_obs   = _int(_run_sql(f"SELECT COUNT(DISTINCT observation_id) FROM search_observation WHERE DATE(observed_at)='{TODAY}'"))
    today_offer = _int(_run_sql(f"""
        SELECT COUNT(f.offer_observation_id) FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE DATE(s.observed_at)='{TODAY}'"""))
    total_obs   = _int(_run_sql("SELECT COUNT(*) FROM search_observation"))
    total_offer = _int(_run_sql("SELECT COUNT(*) FROM flight_offer_observation"))
    dpd_cnt     = _int(_run_sql(f"SELECT COUNT(DISTINCT dpd) FROM search_observation WHERE DATE(observed_at)='{TODAY}'"))
    official    = _int(_run_sql(f"""
        SELECT COUNT(*) FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE DATE(s.observed_at)='{TODAY}' AND f.price_status='official_price'"""))
    return {
        "today_obs":   today_obs,
        "today_offer": today_offer,
        "total_obs":   total_obs,
        "total_offer": total_offer,
        "dpd_cnt":     dpd_cnt,
        "official_rate": round(official / max(today_offer, 1) * 100, 1),
    }


def q_daily_trend():
    rows = _run_sql("""
        SELECT DATE(s.observed_at) as day,
               COUNT(DISTINCT s.observation_id),
               COUNT(f.offer_observation_id)
        FROM search_observation s
        LEFT JOIN flight_offer_observation f ON s.observation_id=f.observation_id
        GROUP BY DATE(s.observed_at) ORDER BY day""")
    dates, obs, offers = [], [], []
    for r in rows:
        if len(r) == 3:
            dates.append(r[0].strip())
            try:
                obs.append(int(r[1]))
                offers.append(int(r[2]))
            except Exception:
                pass
    return dates, obs, offers


def q_route_dist():
    rows = _run_sql(f"""
        SELECT CONCAT(origin_iata,'\u2192',destination_iata), COUNT(DISTINCT observation_id)
        FROM search_observation
        WHERE DATE(observed_at)='{TODAY}' AND route_type='oneway'
        GROUP BY origin_iata,destination_iata ORDER BY 2 DESC""")
    routes, counts = [], []
    for r in rows:
        if len(r) == 2:
            routes.append(r[0].strip())
            try: counts.append(int(r[1]))
            except Exception: pass
    return routes, counts


def q_dpd_price(origin="ICN", dest="NRT"):
    rows = _run_sql(f"""
        SELECT s.dpd, MIN(f.price_krw), ROUND(AVG(f.price_krw))
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE s.route_type='oneway' AND s.origin_iata='{origin}'
          AND s.destination_iata='{dest}' AND f.price_krw IS NOT NULL
          AND DATE(s.observed_at)='{TODAY}'
        GROUP BY s.dpd ORDER BY s.dpd""")
    dpds, mins, avgs = [], [], []
    for r in rows:
        if len(r) == 3:
            try:
                dpds.append(int(r[0]))
                mins.append(float(r[1]))
                avgs.append(float(r[2]))
            except Exception:
                pass
    return dpds, mins, avgs


def q_slot_summary():
    rows = _run_sql(f"""
        SELECT HOUR(observed_at),
               COUNT(DISTINCT CASE WHEN route_type='oneway'    THEN observation_id END),
               COUNT(DISTINCT CASE WHEN route_type='roundtrip' THEN observation_id END)
        FROM search_observation
        WHERE DATE(observed_at)='{TODAY}'
        GROUP BY HOUR(observed_at) ORDER BY 1""")
    slots = {}
    for r in rows:
        if len(r) == 3:
            try:
                label = f"{int(r[0]):02d}:00"
                slots[label] = {"oneway": int(r[1]), "roundtrip": int(r[2])}
            except Exception:
                pass
    return slots


def q_route_stats():
    return _run_sql(f"""
        SELECT CONCAT(s.origin_iata,'\u2192',s.destination_iata), s.route_type,
               COUNT(DISTINCT s.observation_id),
               COUNT(f.offer_observation_id),
               MIN(f.price_krw), ROUND(AVG(f.price_krw))
        FROM search_observation s
        LEFT JOIN flight_offer_observation f ON s.observation_id=f.observation_id
        WHERE DATE(s.observed_at)='{TODAY}' AND f.price_krw IS NOT NULL
        GROUP BY s.origin_iata, s.destination_iata, s.route_type
        ORDER BY 3 DESC""")


def q_dpd_table(origin="ICN", dest="NRT"):
    return _run_sql(f"""
        SELECT s.dpd, COUNT(DISTINCT s.observation_id),
               MIN(f.price_krw), ROUND(AVG(f.price_krw)), MAX(f.price_krw)
        FROM search_observation s
        LEFT JOIN flight_offer_observation f ON s.observation_id=f.observation_id
        WHERE DATE(s.observed_at)='{TODAY}' AND s.route_type='oneway'
          AND s.origin_iata='{origin}' AND s.destination_iata='{dest}'
          AND f.price_krw IS NOT NULL
        GROUP BY s.dpd ORDER BY s.dpd LIMIT 40""")


# ───────────────────────────── PNG ───────────────────────────────────────────

C = {
    "bg":      "#0F1117",
    "panel":   "#1A1D2E",
    "text":    "#E8EAF0",
    "muted":   "#6B7280",
    "grid":    "#2A2D3E",
    "blue":    "#2B5BE0",
    "green":   "#1DB954",
    "orange":  "#FF6B35",
    "purple":  "#9B59B6",
}


def _style_ax(ax):
    ax.set_facecolor(C["panel"])
    ax.tick_params(colors=C["text"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(C["grid"])
    ax.xaxis.label.set_color(C["text"])
    ax.yaxis.label.set_color(C["text"])
    ax.title.set_color(C["text"])
    ax.grid(True, color=C["grid"], linewidth=0.5, alpha=0.6, zorder=0)


def generate_png(summary: dict) -> bytes:
    fig = plt.figure(figsize=(14, 9), facecolor=C["bg"])
    gs  = gridspec.GridSpec(2, 3, figure=fig,
                            hspace=0.5, wspace=0.38,
                            left=0.07, right=0.97, top=0.83, bottom=0.08)

    fig.text(0.5, 0.94, f"AirChoice Daily Stats \u2014 {TODAY}",
             ha="center", fontsize=14, fontweight="bold", color=C["text"])
    fig.text(0.5, 0.89,
             f"Today: search {summary['today_obs']:,}  /  offer {summary['today_offer']:,}  /  "
             f"DPD {summary['dpd_cnt']}/120  /  official_price {summary['official_rate']}%  /  "
             f"Cumulative: {summary['total_obs']:,} / {summary['total_offer']:,}",
             ha="center", fontsize=8.5, color=C["muted"])

    # ── Panel 1: Daily trend (top-left, span 2 cols) ──
    ax1 = fig.add_subplot(gs[0, 0:2])
    dates, obs, offers = q_daily_trend()
    if dates:
        x = list(range(len(dates)))
        ax1.bar(x, obs, color=C["blue"], alpha=0.8, width=0.4, label="search_obs", zorder=2)
        ax1r = ax1.twinx()
        ax1r.plot(x, offers, color=C["green"], marker="o", ms=4, lw=2, label="offers", zorder=3)
        ax1r.tick_params(colors=C["text"], labelsize=8)
        for sp in ax1r.spines.values(): sp.set_color(C["grid"])
        ax1r.set_ylabel("offers", fontsize=8, color=C["text"])
        ax1.set_xticks(x)
        ax1.set_xticklabels([d[-5:] for d in dates], fontsize=7, rotation=30)
        ax1.set_ylabel("search obs", fontsize=8)
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        ax1.legend(
            [Patch(fc=C["blue"], alpha=0.8), Line2D([0],[0],color=C["green"],marker="o",ms=4)],
            ["search_obs","offers"], loc="upper left", fontsize=7,
            facecolor=C["panel"], labelcolor=C["text"], framealpha=0.8,
        )
    else:
        ax1.text(0.5, 0.5, "No data yet", ha="center", va="center",
                 color=C["muted"], transform=ax1.transAxes, fontsize=10)
    ax1.set_title("Daily Accumulation Trend", fontsize=10, pad=6)
    _style_ax(ax1)

    # ── Panel 2: Slot summary (top-right) ──
    ax2 = fig.add_subplot(gs[0, 2])
    slots = q_slot_summary()
    if slots:
        labels  = sorted(slots.keys())
        ow_vals = [slots[l]["oneway"]    for l in labels]
        rt_vals = [slots[l]["roundtrip"] for l in labels]
        x2 = list(range(len(labels)))
        w  = 0.35
        ax2.bar([i - w/2 for i in x2], ow_vals, w, label="oneway",    color=C["blue"],   alpha=0.85)
        ax2.bar([i + w/2 for i in x2], rt_vals, w, label="roundtrip", color=C["orange"], alpha=0.85)
        ax2.set_xticks(x2)
        ax2.set_xticklabels(labels, fontsize=8)
        ax2.legend(fontsize=7, facecolor=C["panel"], labelcolor=C["text"], framealpha=0.8)
    else:
        ax2.text(0.5, 0.5, "No data yet", ha="center", va="center",
                 color=C["muted"], transform=ax2.transAxes, fontsize=10)
    ax2.set_title("Today Slots", fontsize=10, pad=6)
    _style_ax(ax2)

    # ── Panel 3: DPD price curve (bottom-left, span 2 cols) ──
    ax3 = fig.add_subplot(gs[1, 0:2])
    dpds, mins, avgs = q_dpd_price("ICN", "NRT")
    if dpds:
        ax3.plot(dpds, [m/10000 for m in mins], color=C["green"],  lw=1.8, label="min",  alpha=0.9)
        ax3.plot(dpds, [a/10000 for a in avgs], color=C["orange"], lw=1.8, label="avg",
                 linestyle="--", alpha=0.9)
        ax3.fill_between(dpds, [m/10000 for m in mins], [a/10000 for a in avgs],
                         alpha=0.12, color=C["blue"])
        ax3.set_xlabel("DPD", fontsize=8)
        ax3.set_ylabel("Price (\ub9cc\uc6d0)", fontsize=8)
        ax3.legend(fontsize=7, facecolor=C["panel"], labelcolor=C["text"], framealpha=0.8)
    else:
        ax3.text(0.5, 0.5, "No data yet", ha="center", va="center",
                 color=C["muted"], transform=ax3.transAxes, fontsize=10)
    ax3.set_title("ICN\u2192NRT Price Curve (Today, Oneway)", fontsize=10, pad=6)
    _style_ax(ax3)

    # ── Panel 4: Route distribution (bottom-right) ──
    ax4 = fig.add_subplot(gs[1, 2])
    routes, counts = q_route_dist()
    if routes:
        bar_colors = [C["blue"], C["green"], C["orange"], C["purple"]]
        ax4.barh(routes, counts,
                 color=[bar_colors[i % 4] for i in range(len(routes))],
                 alpha=0.85, height=0.55)
        for i, c in enumerate(counts):
            ax4.text(c + max(counts) * 0.01, i, f"{c:,}",
                     va="center", color=C["text"], fontsize=7)
    else:
        ax4.text(0.5, 0.5, "No data yet", ha="center", va="center",
                 color=C["muted"], transform=ax4.transAxes, fontsize=10)
    ax4.set_title("Route Dist (oneway, today)", fontsize=10, pad=6)
    _style_ax(ax4)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ───────────────────────────── HTML ──────────────────────────────────────────

def generate_html(summary: dict) -> str:
    slots      = q_slot_summary()
    route_rows_data = q_route_stats()
    dpd_data   = q_dpd_table()

    slot_rows = ""
    for label in sorted(slots.keys()):
        s = slots[label]
        total = s["oneway"] + s["roundtrip"]
        slot_rows += f"<tr><td>{label}</td><td>{s['oneway']:,}</td><td>{s['roundtrip']:,}</td><td>{total:,}</td></tr>"

    route_html = ""
    for r in route_rows_data:
        if len(r) >= 6:
            try:
                min_p = f"{int(float(r[4])):,}\uc6d0" if r[4] not in ("","NULL","None") else "-"
                avg_p = f"{int(float(r[5])):,}\uc6d0" if r[5] not in ("","NULL","None") else "-"
                route_html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{int(r[2]):,}</td><td>{int(r[3]):,}</td><td>{min_p}</td><td>{avg_p}</td></tr>"
            except Exception:
                pass

    dpd_html = ""
    for r in dpd_data:
        if len(r) >= 5:
            try:
                min_p = f"{int(float(r[2])):,}\uc6d0" if r[2] not in ("","NULL","None") else "-"
                avg_p = f"{int(float(r[3])):,}\uc6d0" if r[3] not in ("","NULL","None") else "-"
                max_p = f"{int(float(r[4])):,}\uc6d0" if r[4] not in ("","NULL","None") else "-"
                dpd_html += f"<tr><td>{r[0]}</td><td>{int(r[1]):,}</td><td>{min_p}</td><td>{avg_p}</td><td>{max_p}</td></tr>"
            except Exception:
                pass

    no_data = "<tr><td colspan='10' style='text-align:center;color:#6B7280;padding:16px'>No data</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>AirChoice Daily Stats \u2014 {TODAY}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#0F1117;color:#E8EAF0;margin:0;padding:24px}}
.header{{text-align:center;padding:20px 0 12px}}
.header h1{{font-size:22px;color:#fff;margin:0}}
.header p{{color:#6B7280;font-size:13px;margin:6px 0}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}}
.card{{background:#1A1D2E;border-radius:10px;padding:18px;text-align:center}}
.card .label{{font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:.05em}}
.card .value{{font-size:26px;font-weight:700;color:#2B5BE0;margin:6px 0}}
.card .sub{{font-size:11px;color:#9CA3AF}}
section{{margin:28px 0}}
h2{{font-size:14px;color:#9CA3AF;border-bottom:1px solid #2A2D3E;padding-bottom:8px;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#1A1D2E;color:#6B7280;text-align:left;padding:8px 12px;font-weight:500}}
td{{padding:7px 12px;border-bottom:1px solid #1A1D2E;color:#E8EAF0}}
tr:hover td{{background:#1A1D2E}}
.footer{{text-align:center;color:#374151;font-size:11px;margin-top:40px;padding:20px 0}}
</style>
</head>
<body>
<div class="header">
  <h1>AirChoice Daily Stats</h1>
  <p>{TODAY} &mdash; Generated {datetime.now().strftime('%H:%M:%S')} KST</p>
</div>
<div class="grid">
  <div class="card">
    <div class="label">Today Search Obs</div>
    <div class="value">{summary['today_obs']:,}</div>
    <div class="sub">Cumulative {summary['total_obs']:,}</div>
  </div>
  <div class="card">
    <div class="label">Today Offers</div>
    <div class="value">{summary['today_offer']:,}</div>
    <div class="sub">Cumulative {summary['total_offer']:,}</div>
  </div>
  <div class="card">
    <div class="label">DPD Coverage</div>
    <div class="value">{summary['dpd_cnt']}<span style="font-size:14px;color:#6B7280">/120</span></div>
    <div class="sub">official_price {summary['official_rate']}%</div>
  </div>
</div>
<section>
  <h2>\uc218\uc9d1 \uc2ac\ub86f\ubcc4 \ud604\ud669 (\uc624\ub298)</h2>
  <table><tr><th>\uc2ac\ub86f</th><th>\ud3b8\ub3c4 obs</th><th>\uc655\ubcf5 obs</th><th>\uc804\uccb4 obs</th></tr>
  {slot_rows or no_data}</table>
</section>
<section>
  <h2>\ub178\uc120\ubcc4 \uc218\uc9d1 \ud604\ud669 (\uc624\ub298)</h2>
  <table><tr><th>\ub178\uc120</th><th>route_type</th><th>obs</th><th>offers</th><th>\ucd5c\uc800\uac00</th><th>\ud3c9\uade0\uac00</th></tr>
  {route_html or no_data}</table>
</section>
<section>
  <h2>DPD\ubcc4 \uac00\uaca9 \ud604\ud669 \u2014 ICN\u2192NRT (\uc624\ub298, \ud3b8\ub3c4, \uc0c1\uc704 40 DPD)</h2>
  <table><tr><th>DPD</th><th>obs \uc218</th><th>\ucd5c\uc800\uac00</th><th>\ud3c9\uade0\uac00</th><th>\ucd5c\uace0\uac00</th></tr>
  {dpd_html or no_data}</table>
</section>
<div class="footer">AirChoice &middot; Capstone Design 2026 &middot; daily_stats.py</div>
</body></html>"""


# ───────────────────────────── Discord ───────────────────────────────────────

def send_webhook(png_bytes: bytes, html_str: str, summary: dict) -> bool:
    if not WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL not set")
        return False
    try:
        import requests as req
    except ImportError:
        log.error("requests not installed — run: pip3 install requests --break-system-packages")
        return False

    message = (
        f"**[AirChoice Daily Stats] {TODAY}**\n"
        f"search {summary['today_obs']:,} / offer {summary['today_offer']:,} / "
        f"DPD {summary['dpd_cnt']}/120 / official_price {summary['official_rate']}%"
    )
    import time
    for attempt in range(3):
        try:
            resp = req.post(
                WEBHOOK_URL,
                data={"payload_json": json.dumps({"content": message})},
                files={
                    "files[0]": ("daily_summary.png", png_bytes,            "image/png"),
                    "files[1]": ("report.html",       html_str.encode("utf-8"), "text/html"),
                },
                timeout=30,
            )
            if resp.status_code in (200, 204):
                log.info("Webhook sent (attempt %d)", attempt + 1)
                return True
            log.warning("Webhook attempt %d: HTTP %d", attempt + 1, resp.status_code)
        except Exception as e:
            log.warning("Webhook attempt %d failed: %s", attempt + 1, e)
        if attempt < 2:
            time.sleep(5 * (attempt + 1))

    log.error("Webhook failed after 3 attempts")
    return False


def send_fail_webhook(stage: str, error: str) -> None:
    if not WEBHOOK_URL:
        return
    try:
        import requests as req
        req.post(
            WEBHOOK_URL,
            json={"content": f"**[AirChoice Daily Stats] FAILED {TODAY}**\nstage=`{stage}`\n```{error[:300]}```"},
            timeout=10,
        )
    except Exception:
        pass


# ───────────────────────────── Main ──────────────────────────────────────────

def main() -> None:
    log.info("=== daily stats start: %s ===", TODAY)
    today_dir  = OUTPUT_DIR / TODAY
    latest_dir = OUTPUT_DIR / "latest"
    today_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = q_summary()
        log.info("summary: %s", summary)
    except Exception as e:
        log.error("q_summary failed: %s", e)
        send_fail_webhook("q_summary", str(e))
        return

    try:
        log.info("generating PNG...")
        png_bytes = generate_png(summary)
        (today_dir  / "daily_summary.png").write_bytes(png_bytes)
        (latest_dir / "daily_summary.png").write_bytes(png_bytes)
        log.info("PNG saved (%d bytes)", len(png_bytes))
    except Exception as e:
        log.error("generate_png failed: %s", e)
        send_fail_webhook("generate_png", str(e))
        return

    try:
        log.info("generating HTML...")
        html_str = generate_html(summary)
        (today_dir  / "report.html").write_text(html_str, encoding="utf-8")
        (latest_dir / "report.html").write_text(html_str, encoding="utf-8")
        log.info("HTML saved")
    except Exception as e:
        log.error("generate_html failed: %s", e)
        send_fail_webhook("generate_html", str(e))
        return

    try:
        send_webhook(png_bytes, html_str, summary)
    except Exception as e:
        log.error("send_webhook failed: %s", e)
        send_fail_webhook("send_webhook", str(e))

    log.info("=== daily stats done: %s ===", TODAY)


if __name__ == "__main__":
    main()
