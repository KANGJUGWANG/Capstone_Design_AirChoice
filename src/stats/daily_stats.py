#!/usr/bin/env python3
"""
src/stats/daily_stats.py
- HTML 첨부 제거 (Discord는 HTML 코드로 표시)
- PNG 2장: 데일리(5패널) + 누적(3패널)
- 한글 폰트 (NanumGothic)
- embed 안에 이미지 내장 (attachment 방식)
"""
from __future__ import annotations

import io
import json
import logging
import subprocess
import time
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

ENV_FILE        = PROJECT_ROOT / ".env"
MYSQL_CONTAINER = "capstone-mysql"
TODAY           = date.today().isoformat()


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


_ENV        = _load_env()
MYSQL_DB    = _ENV.get("MYSQL_DATABASE", "capstone_db")
MYSQL_PWD   = _ENV.get("MYSQL_ROOT_PASSWORD", "")
WEBHOOK_URL = _ENV.get("DISCORD_WEBHOOK_URL", "")


# ── 한글 폰트 설정 ─────────────────────────────────────────────────────────
def setup_font():
    import matplotlib.font_manager as fm
    nanum = [
        f for f in fm.findSystemFonts(fontpaths=None, fontext="ttf")
        if "NanumGothic" in f or "nanumgothic" in f.lower()
    ]
    if nanum:
        fm.fontManager.addfont(nanum[0])
        plt.rcParams["font.family"] = "NanumGothic"
        log.info("font: NanumGothic")
    else:
        plt.rcParams["font.family"] = "DejaVu Sans"
        log.info("font: DejaVu Sans (NanumGothic 미설치)")
    plt.rcParams["axes.unicode_minus"] = False


# ── DB helpers ────────────────────────────────────────────────────────────────
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
        log.error("SQL 실패: %s", e)
        return []


def _int(rows, default=0):
    try: return int(rows[0][0])
    except: return default


# ── Queries ────────────────────────────────────────────────────────────────────
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
    days_cnt    = _int(_run_sql("SELECT COUNT(DISTINCT DATE(observed_at)) FROM search_observation"))
    return {
        "today_obs":     today_obs,
        "today_offer":   today_offer,
        "total_obs":     total_obs,
        "total_offer":   total_offer,
        "dpd_cnt":       dpd_cnt,
        "official_rate": round(official / max(today_offer, 1) * 100, 1),
        "days_cnt":      days_cnt,
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
            try: obs.append(int(r[1])); offers.append(int(r[2]))
            except: pass
    return dates, obs, offers


def q_slot_summary():
    rows = _run_sql(f"""
        SELECT HOUR(observed_at),
               COUNT(DISTINCT CASE WHEN route_type='oneway'    THEN observation_id END),
               COUNT(DISTINCT CASE WHEN route_type='roundtrip' THEN observation_id END)
        FROM search_observation WHERE DATE(observed_at)='{TODAY}'
        GROUP BY HOUR(observed_at) ORDER BY 1""")
    slots = {}
    for r in rows:
        if len(r) == 3:
            try:
                label = f"{int(r[0]):02d}:00"
                slots[label] = {"oneway": int(r[1]), "roundtrip": int(r[2])}
            except: pass
    return slots


def q_route_dist(today_only=True):
    where = f"WHERE DATE(observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"""
        SELECT CONCAT(origin_iata,'\u2192',destination_iata), route_type,
               COUNT(DISTINCT observation_id)
        FROM search_observation {where}
        GROUP BY origin_iata,destination_iata,route_type ORDER BY 3 DESC""")
    result = []
    for r in rows:
        if len(r) == 3:
            try: result.append((r[0].strip(), r[1].strip(), int(r[2])))
            except: pass
    return result


def q_dpd_price(origin="ICN", dest="NRT", today_only=True):
    where_date = f"AND DATE(s.observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"""
        SELECT s.dpd,
               MIN(f.price_krw), ROUND(AVG(f.price_krw)), MAX(f.price_krw),
               COUNT(f.price_krw)
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE s.route_type='oneway' AND s.origin_iata='{origin}'
          AND s.destination_iata='{dest}' AND f.price_krw IS NOT NULL
          {where_date}
        GROUP BY s.dpd ORDER BY s.dpd""")
    dpds, mins, avgs, maxs, cnts = [], [], [], [], []
    for r in rows:
        if len(r) == 5:
            try:
                dpds.append(int(r[0])); mins.append(float(r[1]))
                avgs.append(float(r[2])); maxs.append(float(r[3]))
                cnts.append(int(r[4]))
            except: pass
    return dpds, mins, avgs, maxs, cnts


def q_dpd_density():
    rows = _run_sql(f"""
        SELECT dpd, COUNT(DISTINCT observation_id)
        FROM search_observation
        WHERE DATE(observed_at)='{TODAY}' AND route_type='oneway'
        GROUP BY dpd ORDER BY dpd""")
    dpds, cnts = [], []
    for r in rows:
        if len(r) == 2:
            try: dpds.append(int(r[0])); cnts.append(int(r[1]))
            except: pass
    return dpds, cnts


def q_dpd_bin_volatility():
    rows = _run_sql(f"""
        SELECT
            CASE
                WHEN s.dpd BETWEEN 1  AND 14  THEN '1-14\uc77c'
                WHEN s.dpd BETWEEN 15 AND 30  THEN '15-30\uc77c'
                WHEN s.dpd BETWEEN 31 AND 60  THEN '31-60\uc77c'
                WHEN s.dpd BETWEEN 61 AND 90  THEN '61-90\uc77c'
                WHEN s.dpd BETWEEN 91 AND 120 THEN '91-120\uc77c'
                ELSE '\uae30\ud0c0'
            END as bin,
            ROUND(STDDEV(f.price_krw)),
            COUNT(f.price_krw)
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE s.route_type='oneway' AND s.origin_iata='ICN'
          AND s.destination_iata='NRT' AND f.price_krw IS NOT NULL
        GROUP BY bin ORDER BY MIN(s.dpd)""")
    bins, stds, cnts = [], [], []
    for r in rows:
        if len(r) == 3:
            try: bins.append(r[0].strip()); stds.append(float(r[1])); cnts.append(int(r[2]))
            except: pass
    return bins, stds, cnts


# ── Colors & style ─────────────────────────────────────────────────────────────
C = {
    "bg": "#0F1117", "panel": "#1A1D2E",
    "text": "#E8EAF0", "muted": "#6B7280", "grid": "#2A2D3E",
    "blue": "#2B5BE0", "green": "#1DB954", "orange": "#FF6B35",
    "purple": "#9B59B6", "red": "#ED4245",
}


def _style_ax(ax, xlabel=None, ylabel=None):
    ax.set_facecolor(C["panel"])
    ax.tick_params(colors=C["text"], labelsize=8)
    for sp in ax.spines.values(): sp.set_color(C["grid"])
    ax.title.set_color(C["text"])
    ax.grid(True, color=C["grid"], linewidth=0.5, alpha=0.6, zorder=0)
    ax.xaxis.label.set_color(C["text"])
    ax.yaxis.label.set_color(C["text"])
    if xlabel: ax.set_xlabel(xlabel, fontsize=8)
    if ylabel: ax.set_ylabel(ylabel, fontsize=8)


def _no_data(ax):
    ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center",
            color=C["muted"], transform=ax.transAxes, fontsize=11)


def _legend(ax, **kw):
    ax.legend(fontsize=7, facecolor=C["panel"],
              labelcolor=C["text"], framealpha=0.8, **kw)


# ── Daily PNG (5패널) ───────────────────────────────────────────────────────────
def generate_daily_png(summary: dict) -> bytes:
    fig = plt.figure(figsize=(15, 10), facecolor=C["bg"])
    gs  = gridspec.GridSpec(2, 3, figure=fig,
                            hspace=0.52, wspace=0.38,
                            left=0.07, right=0.97, top=0.84, bottom=0.08)

    fig.text(0.5, 0.95, f"AirChoice \ub370일리 통계 \u2014 {TODAY}",
             ha="center", fontsize=14, fontweight="bold", color=C["text"])
    fig.text(
        0.5, 0.905,
        f"오늘 수집: search {summary['today_obs']:,}\uac74  /  offer {summary['today_offer']:,}\uac74  /  "
        f"DPD커버 {summary['dpd_cnt']}/120  /  공식가격 {summary['official_rate']}%  /  "
        f"\ub204적: {summary['total_obs']:,} / {summary['total_offer']:,}\uac74",
        ha="center", fontsize=8.5, color=C["muted"]
    )

    # [0,0] 오늘 수집 슬롯별 현황
    ax1 = fig.add_subplot(gs[0, 0])
    slots = q_slot_summary()
    if slots:
        labels  = sorted(slots.keys())
        ow_vals = [slots[l]["oneway"]    for l in labels]
        rt_vals = [slots[l]["roundtrip"] for l in labels]
        x = list(range(len(labels)))
        w = 0.35
        ax1.bar([i - w/2 for i in x], ow_vals, w, label="편도", color=C["blue"],   alpha=0.85)
        ax1.bar([i + w/2 for i in x], rt_vals, w, label="왕복", color=C["orange"], alpha=0.85)
        ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=8)
        _legend(ax1)
    else:
        _no_data(ax1)
    ax1.set_title("수집 슬롯별 현황 (오늘)", fontsize=10, pad=6)
    _style_ax(ax1, ylabel="관측 수")

    # [0,1:3] DPD별 가격 곡선 ICN→NRT (span 2)
    ax2 = fig.add_subplot(gs[0, 1:3])
    dpds, mins, avgs, maxs, _ = q_dpd_price("ICN", "NRT", today_only=True)
    if dpds:
        ax2.plot(dpds, [m/10000 for m in mins], color=C["green"],  lw=2, label="최저가")
        ax2.plot(dpds, [a/10000 for a in avgs], color=C["orange"], lw=2, label="평균가", linestyle="--")
        ax2.plot(dpds, [m/10000 for m in maxs], color=C["red"],    lw=1.2, label="최고가", linestyle=":")
        ax2.fill_between(dpds, [m/10000 for m in mins], [a/10000 for a in avgs],
                         alpha=0.12, color=C["blue"])
        _legend(ax2, loc="upper left")
    else:
        _no_data(ax2)
    ax2.set_title("ICN\u2192NRT DPD별 가격 곡선 (오늘, 편도)", fontsize=10, pad=6)
    _style_ax(ax2, xlabel="DPD (출발까지 남은 일수)", ylabel="가격 (만원)")

    # [1,0] 노선별 관측 분포 (오늘)
    ax3 = fig.add_subplot(gs[1, 0])
    route_data = q_route_dist(today_only=True)
    if route_data:
        routes_ow, routes_rt = {}, {}
        for route, rtype, cnt in route_data:
            if rtype == "oneway": routes_ow[route] = cnt
            else: routes_rt[route] = cnt
        all_routes = sorted(set(list(routes_ow) + list(routes_rt)))
        x3 = list(range(len(all_routes)))
        ax3.barh(x3, [routes_ow.get(r, 0) for r in all_routes],
                 color=C["blue"], alpha=0.85, label="편도", height=0.4)
        ax3.barh([i+0.4 for i in x3], [routes_rt.get(r, 0) for r in all_routes],
                 color=C["orange"], alpha=0.85, label="왕복", height=0.4)
        ax3.set_yticks([i+0.2 for i in x3])
        ax3.set_yticklabels(all_routes, fontsize=7)
        _legend(ax3)
    else:
        _no_data(ax3)
    ax3.set_title("노선별 관측 분포 (오늘)", fontsize=10, pad=6)
    _style_ax(ax3, xlabel="관측 수")

    # [1,1] DPD 관측 밀도
    ax4 = fig.add_subplot(gs[1, 1])
    dpd_d, cnt_d = q_dpd_density()
    if dpd_d:
        ax4.bar(dpd_d, cnt_d, color=C["purple"], alpha=0.8, width=1.0)
        ax4.axhline(y=4, color=C["green"], lw=1.2, linestyle="--", label="목표(4노선)")
        _legend(ax4, loc="lower right")
    else:
        _no_data(ax4)
    ax4.set_title("DPD별 관측 밀도 (오늘, 편도)", fontsize=10, pad=6)
    _style_ax(ax4, xlabel="DPD", ylabel="관측 수")

    # [1,2] DPD 구간별 변동성
    ax5 = fig.add_subplot(gs[1, 2])
    bins, stds, b_cnts = q_dpd_bin_volatility()
    if bins and any(s > 0 for s in stds):
        colors5 = [C["blue"], C["green"], C["orange"], C["purple"], C["red"]]
        bars = ax5.bar(bins, [s/10000 for s in stds],
                       color=[colors5[i % 5] for i in range(len(bins))], alpha=0.85)
        for bar, cnt in zip(bars, b_cnts):
            ax5.text(bar.get_x() + bar.get_width()/2,
                     bar.get_height() + max([s/10000 for s in stds], default=0) * 0.02,
                     f"n={cnt}", ha="center", va="bottom",
                     color=C["muted"], fontsize=7)
    else:
        _no_data(ax5)
    ax5.set_title("DPD 구간별 가격 변동성 (ICN\u2192NRT)", fontsize=10, pad=6)
    _style_ax(ax5, xlabel="DPD 구간", ylabel="표준편차 (만원)")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── Cumulative PNG (3패널) ──────────────────────────────────────────────────────
def generate_cumul_png(summary: dict) -> bytes:
    fig = plt.figure(figsize=(15, 8), facecolor=C["bg"])
    gs  = gridspec.GridSpec(2, 2, figure=fig,
                            hspace=0.52, wspace=0.35,
                            left=0.07, right=0.97, top=0.84, bottom=0.08)

    fig.text(0.5, 0.95, f"AirChoice 누적 통계 \u2014 {summary['days_cnt']}일차",
             ha="center", fontsize=14, fontweight="bold", color=C["text"])
    fig.text(
        0.5, 0.905,
        f"수집 시작: 2026-04-16  /  누적 search {summary['total_obs']:,}\uac74  /  "
        f"offer {summary['total_offer']:,}\uac74",
        ha="center", fontsize=8.5, color=C["muted"]
    )

    # [0,0:2] 날짜별 누적 관측 추이 (span 2)
    ax1 = fig.add_subplot(gs[0, 0:2])
    dates, obs, offers = q_daily_trend()
    if dates:
        x = list(range(len(dates)))
        ax1.bar(x, obs, color=C["blue"], alpha=0.8, width=0.4, label="search 관측", zorder=2)
        ax1r = ax1.twinx()
        ax1r.plot(x, offers, color=C["green"], marker="o", ms=5, lw=2,
                  label="offer 수", zorder=3)
        ax1r.tick_params(colors=C["text"], labelsize=8)
        for sp in ax1r.spines.values(): sp.set_color(C["grid"])
        ax1r.set_ylabel("offer 수", fontsize=8, color=C["text"])
        ax1.set_xticks(x)
        ax1.set_xticklabels([d[5:] for d in dates], fontsize=8, rotation=30)
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        ax1.legend(
            [Patch(fc=C["blue"], alpha=0.8),
             Line2D([0],[0], color=C["green"], marker="o", ms=5)],
            ["search 관측", "offers"],
            loc="upper left", fontsize=8,
            facecolor=C["panel"], labelcolor=C["text"], framealpha=0.8,
        )
    else:
        _no_data(ax1)
    ax1.set_title("날짜별 누적 수집 추이", fontsize=10, pad=6)
    _style_ax(ax1, ylabel="search 관측 수")

    # [1,0] 누적 노선별 분포
    ax2 = fig.add_subplot(gs[1, 0])
    all_route_data = q_route_dist(today_only=False)
    if all_route_data:
        routes_ow, routes_rt = {}, {}
        for route, rtype, cnt in all_route_data:
            if rtype == "oneway": routes_ow[route] = cnt
            else: routes_rt[route] = cnt
        all_routes = sorted(set(list(routes_ow) + list(routes_rt)))
        x2 = list(range(len(all_routes)))
        ax2.barh(x2, [routes_ow.get(r, 0) for r in all_routes],
                 color=C["blue"], alpha=0.85, label="편도", height=0.4)
        ax2.barh([i+0.4 for i in x2], [routes_rt.get(r, 0) for r in all_routes],
                 color=C["orange"], alpha=0.85, label="왕복", height=0.4)
        ax2.set_yticks([i+0.2 for i in x2])
        ax2.set_yticklabels(all_routes, fontsize=8)
        _legend(ax2)
    else:
        _no_data(ax2)
    ax2.set_title("누적 노선별 관측 분포", fontsize=10, pad=6)
    _style_ax(ax2, xlabel="관측 수")

    # [1,1] 누적 DPD 가격 곡선
    ax3 = fig.add_subplot(gs[1, 1])
    dpds, mins, avgs, maxs, _ = q_dpd_price("ICN", "NRT", today_only=False)
    if dpds:
        ax3.plot(dpds, [m/10000 for m in mins], color=C["green"],  lw=2, label="최저가")
        ax3.plot(dpds, [a/10000 for a in avgs], color=C["orange"], lw=2, label="평균가", linestyle="--")
        ax3.fill_between(dpds, [m/10000 for m in mins], [a/10000 for a in avgs],
                         alpha=0.15, color=C["blue"])
        _legend(ax3)
    else:
        _no_data(ax3)
    ax3.set_title("ICN\u2192NRT 누적 DPD 가격 곡선 (전체 기간)", fontsize=10, pad=6)
    _style_ax(ax3, xlabel="DPD", ylabel="가격 (만원)")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── Discord 웹훅 전송 ───────────────────────────────────────────────────────────
def _send_png_webhook(png_bytes: bytes, filename: str,
                      title: str, desc: str, color: int) -> bool:
    if not WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL 미설정")
        return False
    try:
        import requests as req
    except ImportError:
        log.error("requests 미설치")
        return False

    embed = {
        "title":       title,
        "description": desc,
        "color":       color,
        "image":       {"url": f"attachment://{filename}"},
    }
    for attempt in range(3):
        try:
            resp = req.post(
                WEBHOOK_URL,
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={"files[0]": (filename, png_bytes, "image/png")},
                timeout=30,
            )
            if resp.status_code in (200, 204):
                log.info("Webhook 전송: %s (시도 %d)", title, attempt + 1)
                return True
            log.warning("Webhook %s 시도 %d: HTTP %d", title, attempt + 1, resp.status_code)
        except Exception as e:
            log.warning("Webhook %s 시도 %d 실패: %s", title, attempt + 1, e)
        if attempt < 2:
            time.sleep(5 * (attempt + 1))
    log.error("Webhook 실패: %s", title)
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


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    setup_font()
    log.info("=== daily stats 시작: %s ===", TODAY)
    today_dir  = OUTPUT_DIR / TODAY
    latest_dir = OUTPUT_DIR / "latest"
    today_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    try:
        summary = q_summary()
        log.info("summary: %s", summary)
    except Exception as e:
        log.error("q_summary 실패: %s", e)
        send_fail_webhook("q_summary", str(e))
        return

    # ── Daily PNG ──
    try:
        log.info("daily PNG 생성 중...")
        daily_png = generate_daily_png(summary)
        (today_dir  / "daily_summary.png").write_bytes(daily_png)
        (latest_dir / "daily_summary.png").write_bytes(daily_png)
        log.info("daily PNG 저장 (%d bytes)", len(daily_png))
    except Exception as e:
        log.error("generate_daily_png 실패: %s", e)
        send_fail_webhook("generate_daily_png", str(e))
        return

    # ── Cumulative PNG ──
    try:
        log.info("cumulative PNG 생성 중...")
        cumul_png = generate_cumul_png(summary)
        (today_dir  / "cumulative_summary.png").write_bytes(cumul_png)
        (latest_dir / "cumulative_summary.png").write_bytes(cumul_png)
        log.info("cumulative PNG 저장 (%d bytes)", len(cumul_png))
    except Exception as e:
        log.error("generate_cumul_png 실패: %s", e)
        send_fail_webhook("generate_cumul_png", str(e))
        return

    # ── Webhook 1: 데일리 통계 ──
    desc1 = (
        f"오늘 수집: **search {summary['today_obs']:,}\uac74** / **offer {summary['today_offer']:,}\uac74**\n"
        f"DPD 커버: **{summary['dpd_cnt']}/120** \u00b7 공식가격 **{summary['official_rate']}%**"
    )
    _send_png_webhook(
        daily_png, "daily_summary.png",
        f"[AirChoice] 데일리 통계 \u2014 {TODAY}",
        desc1, 0x5865F2
    )

    time.sleep(2)

    # ── Webhook 2: 누적 통계 ──
    desc2 = (
        f"누적: **search {summary['total_obs']:,}\uac74** / **offer {summary['total_offer']:,}\uac74**\n"
        f"수집 {summary['days_cnt']}일차 \u00b7 시작: 2026-04-16"
    )
    _send_png_webhook(
        cumul_png, "cumulative_summary.png",
        f"[AirChoice] 누적 통계 \u2014 {summary['days_cnt']}일차",
        desc2, 0x9B59B6
    )

    log.info("=== daily stats 완료: %s ===", TODAY)


if __name__ == "__main__":
    main()
