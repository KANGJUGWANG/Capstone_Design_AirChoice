#!/usr/bin/env python3
"""
src/stats/daily_stats.py
Daily PNG (10 panels) + Cumulative PNG (10 panels) via Discord webhook.
Korean font (NanumGothic). No HTML attachment.
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
import numpy as np

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


# ─── env ─────────────────────────────────────────────────────────────────────
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


# ─── 한글 폰트 ─────────────────────────────────────────────────────────────────
def setup_font():
    import matplotlib.font_manager as fm
    nanum = [f for f in fm.findSystemFonts(fontext="ttf")
             if "NanumGothic" in f or "nanumgothic" in f.lower()]
    if nanum:
        fm.fontManager.addfont(nanum[0])
        plt.rcParams["font.family"] = "NanumGothic"
        log.info("font: NanumGothic")
    else:
        plt.rcParams["font.family"] = "DejaVu Sans"
        log.info("font: DejaVu Sans")
    plt.rcParams["axes.unicode_minus"] = False


# ─── DB helpers ───────────────────────────────────────────────────────────────
def _run_sql(sql: str) -> list[list[str]]:
    cmd = ["docker", "exec", MYSQL_CONTAINER,
           "mysql", "-h", "127.0.0.1", "-uroot", f"-p{MYSQL_PWD}",
           "-N", "--batch", "--silent", MYSQL_DB, "-e", sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return [l.split("\t") for l in r.stdout.strip().splitlines()] if r.stdout.strip() else []
    except Exception as e:
        log.error("SQL 실패: %s", e)
        return []


def _int(rows, default=0):
    try: return int(rows[0][0])
    except: return default


# ─── Queries ──────────────────────────────────────────────────────────────────
def q_summary() -> dict:
    today_obs   = _int(_run_sql(f"SELECT COUNT(DISTINCT observation_id) FROM search_observation WHERE DATE(observed_at)='{TODAY}'"))
    today_offer = _int(_run_sql(f"SELECT COUNT(f.offer_observation_id) FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id WHERE DATE(s.observed_at)='{TODAY}'"))
    total_obs   = _int(_run_sql("SELECT COUNT(*) FROM search_observation"))
    total_offer = _int(_run_sql("SELECT COUNT(*) FROM flight_offer_observation"))
    dpd_cnt     = _int(_run_sql(f"SELECT COUNT(DISTINCT dpd) FROM search_observation WHERE DATE(observed_at)='{TODAY}'"))
    official    = _int(_run_sql(f"SELECT COUNT(*) FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id WHERE DATE(s.observed_at)='{TODAY}' AND f.price_status='official_price'"))
    days_cnt    = _int(_run_sql("SELECT COUNT(DISTINCT DATE(observed_at)) FROM search_observation"))
    return {"today_obs": today_obs, "today_offer": today_offer, "total_obs": total_obs,
            "total_offer": total_offer, "dpd_cnt": dpd_cnt,
            "official_rate": round(official / max(today_offer, 1) * 100, 1), "days_cnt": days_cnt}


def q_daily_trend():
    rows = _run_sql("SELECT DATE(s.observed_at), COUNT(DISTINCT s.observation_id), COUNT(f.offer_observation_id) FROM search_observation s LEFT JOIN flight_offer_observation f ON s.observation_id=f.observation_id GROUP BY DATE(s.observed_at) ORDER BY 1")
    dates, obs, offers = [], [], []
    for r in rows:
        if len(r)==3:
            dates.append(r[0].strip())
            try: obs.append(int(r[1])); offers.append(int(r[2]))
            except: pass
    return dates, obs, offers


def q_slot_summary(today_only=True):
    where = f"WHERE DATE(observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"SELECT HOUR(observed_at), COUNT(DISTINCT CASE WHEN route_type='oneway' THEN observation_id END), COUNT(DISTINCT CASE WHEN route_type='roundtrip' THEN observation_id END) FROM search_observation {where} GROUP BY HOUR(observed_at) ORDER BY 1")
    slots = {}
    for r in rows:
        if len(r)==3:
            try: slots[f"{int(r[0]):02d}:00"] = {"oneway": int(r[1]), "roundtrip": int(r[2])}
            except: pass
    return slots


def q_route_dist(today_only=True):
    where = f"WHERE DATE(observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"SELECT CONCAT(origin_iata,'→',destination_iata), route_type, COUNT(DISTINCT observation_id) FROM search_observation {where} GROUP BY origin_iata,destination_iata,route_type ORDER BY 3 DESC")
    result = []
    for r in rows:
        if len(r)==3:
            try: result.append((r[0].strip(), r[1].strip(), int(r[2])))
            except: pass
    return result


def q_dpd_price(origin="ICN", dest="NRT", today_only=True):
    wd = f"AND DATE(s.observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"SELECT s.dpd, MIN(f.price_krw), ROUND(AVG(f.price_krw)), MAX(f.price_krw), COUNT(f.price_krw) FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id WHERE s.route_type='oneway' AND s.origin_iata='{origin}' AND s.destination_iata='{dest}' AND f.price_krw IS NOT NULL {wd} GROUP BY s.dpd ORDER BY s.dpd")
    dpds, mins, avgs, maxs, cnts = [], [], [], [], []
    for r in rows:
        if len(r)==5:
            try: dpds.append(int(r[0])); mins.append(float(r[1])); avgs.append(float(r[2])); maxs.append(float(r[3])); cnts.append(int(r[4]))
            except: pass
    return dpds, mins, avgs, maxs, cnts


def q_dpd_density(today_only=True):
    wd = f"WHERE DATE(observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"SELECT dpd, COUNT(DISTINCT observation_id) FROM search_observation {wd} {'AND' if wd else 'WHERE'} route_type='oneway' GROUP BY dpd ORDER BY dpd".replace("WHERE AND", "WHERE"))
    # fix: 조건 처리
    if today_only:
        rows = _run_sql(f"SELECT dpd, COUNT(DISTINCT observation_id) FROM search_observation WHERE DATE(observed_at)='{TODAY}' AND route_type='oneway' GROUP BY dpd ORDER BY dpd")
    else:
        rows = _run_sql("SELECT dpd, COUNT(DISTINCT observation_id) FROM search_observation WHERE route_type='oneway' GROUP BY dpd ORDER BY dpd")
    dpds, cnts = [], []
    for r in rows:
        if len(r)==2:
            try: dpds.append(int(r[0])); cnts.append(int(r[1]))
            except: pass
    return dpds, cnts


def q_dpd_bin_volatility(today_only=False):
    wd = f"AND DATE(s.observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"""
        SELECT CASE WHEN s.dpd BETWEEN 1 AND 14 THEN '1-14일' WHEN s.dpd BETWEEN 15 AND 30 THEN '15-30일'
               WHEN s.dpd BETWEEN 31 AND 60 THEN '31-60일' WHEN s.dpd BETWEEN 61 AND 90 THEN '61-90일'
               WHEN s.dpd BETWEEN 91 AND 120 THEN '91-120일' ELSE '기타' END as bin,
               ROUND(STDDEV(f.price_krw)), COUNT(f.price_krw)
        FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE s.route_type='oneway' AND s.origin_iata='ICN' AND s.destination_iata='NRT'
          AND f.price_krw IS NOT NULL {wd}
        GROUP BY bin ORDER BY MIN(s.dpd)""")
    bins, stds, cnts = [], [], []
    for r in rows:
        if len(r)==3:
            try: bins.append(r[0].strip()); stds.append(float(r[1])); cnts.append(int(r[2]))
            except: pass
    return bins, stds, cnts


def q_dpd_price_band(origin="ICN", dest="NRT", today_only=True):
    """DPD별 가격 p25/median/p75 (Python numpy로 계산)"""
    wd = f"AND DATE(s.observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"""SELECT s.dpd, GROUP_CONCAT(f.price_krw ORDER BY f.price_krw SEPARATOR ',')
        FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE s.route_type='oneway' AND s.origin_iata='{origin}' AND s.destination_iata='{dest}'
          AND f.price_krw IS NOT NULL {wd}
        GROUP BY s.dpd ORDER BY s.dpd""")
    dpds, p25s, medians, p75s = [], [], [], []
    for r in rows:
        if len(r)==2 and r[1].strip():
            try:
                prices = np.array([float(x) for x in r[1].split(",") if x.strip()])
                if len(prices) >= 3:
                    dpds.append(int(r[0]))
                    p25s.append(np.percentile(prices, 25)/10000)
                    medians.append(np.percentile(prices, 50)/10000)
                    p75s.append(np.percentile(prices, 75)/10000)
            except: pass
    return dpds, p25s, medians, p75s


def q_all_routes_dpd_min(today_only=True):
    """편도 4노선 DPD별 최저가 비교"""
    wd = f"AND DATE(s.observed_at)='{TODAY}'" if today_only else ""
    routes = [("ICN","NRT"),("ICN","HND"),("NRT","ICN"),("HND","ICN")]
    result = {}
    for o, d in routes:
        rows = _run_sql(f"SELECT s.dpd, MIN(f.price_krw) FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id WHERE s.route_type='oneway' AND s.origin_iata='{o}' AND s.destination_iata='{d}' AND f.price_krw IS NOT NULL {wd} GROUP BY s.dpd ORDER BY s.dpd")
        dpds, mins = [], []
        for r in rows:
            if len(r)==2:
                try: dpds.append(int(r[0])); mins.append(float(r[1])/10000)
                except: pass
        result[f"{o}→{d}"] = (dpds, mins)
    return result


def q_price_histogram(origin="ICN", dest="NRT", today_only=True):
    wd = f"AND DATE(s.observed_at)='{TODAY}'" if today_only else ""
    rows = _run_sql(f"SELECT f.price_krw FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id WHERE s.route_type='oneway' AND s.origin_iata='{origin}' AND s.destination_iata='{dest}' AND f.price_krw IS NOT NULL {wd} ORDER BY f.price_krw")
    prices = []
    for r in rows:
        try: prices.append(float(r[0])/10000)
        except: pass
    return prices


def q_slot_quality():
    rows = _run_sql(f"""SELECT HOUR(s.observed_at), ROUND(SUM(CASE WHEN f.price_status='official_price' THEN 1 ELSE 0 END)*100.0/COUNT(*),1)
        FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE DATE(s.observed_at)='{TODAY}'
        GROUP BY HOUR(s.observed_at) ORDER BY 1""")
    labels, rates = [], []
    for r in rows:
        if len(r)==2:
            try: labels.append(f"{int(r[0]):02d}:00"); rates.append(float(r[1]))
            except: pass
    return labels, rates


def q_routetype_price():
    """편도 vs 왕복 가격 분포"""
    rows = _run_sql(f"SELECT s.route_type, GROUP_CONCAT(f.price_krw ORDER BY f.price_krw SEPARATOR ',') FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id WHERE DATE(s.observed_at)='{TODAY}' AND f.price_krw IS NOT NULL GROUP BY s.route_type")
    result = {}
    for r in rows:
        if len(r)==2 and r[1].strip():
            try: result[r[0].strip()] = np.array([float(x) for x in r[1].split(",") if x.strip()])/10000
            except: pass
    return result


def q_date_slot_heatmap():
    """날짜 × 슬롯 수집 현황 (누적)"""
    rows = _run_sql("SELECT DATE(observed_at), HOUR(observed_at), COUNT(DISTINCT observation_id) FROM search_observation GROUP BY DATE(observed_at), HOUR(observed_at) ORDER BY 1, 2")
    data = {}
    for r in rows:
        if len(r)==3:
            try:
                d = r[0].strip(); h = int(r[1]); cnt = int(r[2])
                if d not in data: data[d] = {}
                data[d][h] = cnt
            except: pass
    return data


def q_rolling_zscore(origin="ICN", dest="NRT"):
    """현재가 상대 위치 (날짜별 평균가 기반 z-score)"""
    rows = _run_sql(f"SELECT DATE(s.observed_at), s.dpd, AVG(f.price_krw), STDDEV(f.price_krw) FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id WHERE s.route_type='oneway' AND s.origin_iata='{origin}' AND s.destination_iata='{dest}' AND f.price_krw IS NOT NULL GROUP BY DATE(s.observed_at), s.dpd ORDER BY 1, 2")
    dates_dpd = {}
    for r in rows:
        if len(r)==4:
            try:
                d = r[0].strip(); dpd = int(r[1]); avg = float(r[2]); std = float(r[3]) if r[3] and r[3]!='NULL' else 0
                dates_dpd[(d, dpd)] = (avg, std)
            except: pass
    return dates_dpd


def q_repeat_obs_sample(origin="ICN", dest="NRT", max_dpd=30):
    """반복 관측 시계열: dpd 30 이하 날짜별 최저가 추이"""
    rows = _run_sql(f"""SELECT s.dpd, DATE(s.observed_at), MIN(f.price_krw)
        FROM flight_offer_observation f JOIN search_observation s ON f.observation_id=s.observation_id
        WHERE s.route_type='oneway' AND s.origin_iata='{origin}' AND s.destination_iata='{dest}'
          AND f.price_krw IS NOT NULL AND s.dpd <= {max_dpd}
        GROUP BY s.dpd, DATE(s.observed_at) ORDER BY s.dpd, DATE(s.observed_at)""")
    series = {}
    for r in rows:
        if len(r)==3:
            try:
                dpd = int(r[0]); d = r[1].strip(); p = float(r[2])/10000
                if dpd not in series: series[dpd] = []
                series[dpd].append((d, p))
            except: pass
    return {k: v for k, v in series.items() if len(v) >= 2}


# ─── Colors & helpers ─────────────────────────────────────────────────────────
C = {"bg": "#0F1117", "panel": "#1A1D2E", "text": "#E8EAF0", "muted": "#6B7280",
     "grid": "#2A2D3E", "blue": "#2B5BE0", "green": "#1DB954", "orange": "#FF6B35",
     "purple": "#9B59B6", "red": "#ED4245"}
ROUTE_C = [C["blue"], C["green"], C["orange"], C["purple"]]


def _sa(ax, xlabel=None, ylabel=None):
    ax.set_facecolor(C["panel"]); ax.tick_params(colors=C["text"], labelsize=7.5)
    for sp in ax.spines.values(): sp.set_color(C["grid"])
    ax.title.set_color(C["text"])
    ax.grid(True, color=C["grid"], linewidth=0.4, alpha=0.6, zorder=0)
    ax.xaxis.label.set_color(C["text"]); ax.yaxis.label.set_color(C["text"])
    if xlabel: ax.set_xlabel(xlabel, fontsize=7.5)
    if ylabel: ax.set_ylabel(ylabel, fontsize=7.5)


def _nd(ax):
    ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center",
            color=C["muted"], transform=ax.transAxes, fontsize=10)


def _leg(ax, **kw):
    ax.legend(fontsize=6.5, facecolor=C["panel"], labelcolor=C["text"], framealpha=0.8, **kw)


def _make_fig(title: str, subtitle: str) -> tuple:
    fig = plt.figure(figsize=(18, 14), facecolor=C["bg"])
    gs  = gridspec.GridSpec(5, 2, figure=fig, hspace=0.7, wspace=0.32,
                            left=0.07, right=0.97, top=0.88, bottom=0.05)
    fig.text(0.5, 0.945, title, ha="center", fontsize=13, fontweight="bold", color=C["text"])
    fig.text(0.5, 0.912, subtitle, ha="center", fontsize=8, color=C["muted"])
    axes = [fig.add_subplot(gs[r, c]) for r in range(5) for c in range(2)]
    return fig, axes


def _save_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─── Daily PNG (10패널) ────────────────────────────────────────────────────────
def generate_daily_png(summary: dict) -> bytes:
    fig, axes = _make_fig(
        f"AirChoice 데일리 통계 — {TODAY}",
        f"오늘 수집: search {summary['today_obs']:,}건 / offer {summary['today_offer']:,}건 / "
        f"DPD커버 {summary['dpd_cnt']}/120 / 공식가격 {summary['official_rate']}% / "
        f"누적: {summary['total_obs']:,} / {summary['total_offer']:,}건"
    )

    # ① 수집 슬롯별 현황
    ax = axes[0]; ax.set_title("① 수집 슬롯별 현황 (편도/왕복)", fontsize=9, pad=5)
    slots = q_slot_summary(today_only=True)
    if slots:
        lbls = sorted(slots.keys()); x = list(range(len(lbls))); w = 0.35
        ax.bar([i-w/2 for i in x], [slots[l]["oneway"] for l in lbls], w, label="편도", color=C["blue"], alpha=0.85)
        ax.bar([i+w/2 for i in x], [slots[l]["roundtrip"] for l in lbls], w, label="왕복", color=C["orange"], alpha=0.85)
        ax.set_xticks(x); ax.set_xticklabels(lbls, fontsize=8); _leg(ax)
    else: _nd(ax)
    _sa(ax, ylabel="관측 수")

    # ② ICN→NRT DPD별 가격 곡선
    ax = axes[1]; ax.set_title("② ICN→NRT DPD별 가격 곡선 (오늘, 편도)", fontsize=9, pad=5)
    dpds, mins, avgs, maxs, _ = q_dpd_price("ICN", "NRT", today_only=True)
    if dpds:
        ax.plot(dpds, [m/10000 for m in mins], color=C["green"],  lw=2, label="최저가")
        ax.plot(dpds, [a/10000 for a in avgs], color=C["orange"], lw=2, label="평균가", linestyle="--")
        ax.plot(dpds, [m/10000 for m in maxs], color=C["red"],    lw=1.2, label="최고가", linestyle=":")
        ax.fill_between(dpds, [m/10000 for m in mins], [a/10000 for a in avgs], alpha=0.1, color=C["blue"])
        _leg(ax, loc="upper left")
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="가격 (만원)")

    # ③ DPD별 가격 밴드 (p25/median/p75)
    ax = axes[2]; ax.set_title("③ DPD별 가격 밴드 ICN→NRT (p25/median/p75)", fontsize=9, pad=5)
    bdpds, p25s, meds, p75s = q_dpd_price_band("ICN", "NRT", today_only=True)
    if bdpds:
        ax.fill_between(bdpds, p25s, p75s, alpha=0.25, color=C["blue"], label="IQR (p25-p75)")
        ax.plot(bdpds, meds, color=C["green"], lw=2, label="중앙값")
        ax.plot(bdpds, p25s, color=C["blue"], lw=1, linestyle="--", alpha=0.7)
        ax.plot(bdpds, p75s, color=C["blue"], lw=1, linestyle="--", alpha=0.7)
        _leg(ax)
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="가격 (만원)")

    # ④ 노선별 관측 분포 (편도/왕복)
    ax = axes[3]; ax.set_title("④ 노선별 관측 분포 (오늘)", fontsize=9, pad=5)
    rdata = q_route_dist(today_only=True)
    if rdata:
        rows_ow, rows_rt = {}, {}
        for route, rt, cnt in rdata:
            if rt=="oneway": rows_ow[route]=cnt
            else: rows_rt[route]=cnt
        ar = sorted(set(list(rows_ow)+list(rows_rt)))
        x3 = list(range(len(ar)))
        ax.barh(x3, [rows_ow.get(r,0) for r in ar], color=C["blue"], alpha=0.85, label="편도", height=0.38)
        ax.barh([i+0.4 for i in x3], [rows_rt.get(r,0) for r in ar], color=C["orange"], alpha=0.85, label="왕복", height=0.38)
        ax.set_yticks([i+0.19 for i in x3]); ax.set_yticklabels(ar, fontsize=7.5); _leg(ax)
    else: _nd(ax)
    _sa(ax, xlabel="관측 수")

    # ⑤ 편도 4노선 DPD 최저가 비교
    ax = axes[4]; ax.set_title("⑤ 편도 4노선 DPD 최저가 비교 (오늘)", fontsize=9, pad=5)
    all_routes = q_all_routes_dpd_min(today_only=True)
    has_data = False
    for i, (route, (ds, ms)) in enumerate(all_routes.items()):
        if ds: ax.plot(ds, ms, color=ROUTE_C[i%4], lw=1.8, label=route, alpha=0.9); has_data=True
    if has_data: _leg(ax, loc="upper left")
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="최저가 (만원)")

    # ⑥ DPD별 관측 밀도
    ax = axes[5]; ax.set_title("⑥ DPD별 관측 밀도 (오늘, 편도)", fontsize=9, pad=5)
    dpd_d, cnt_d = q_dpd_density(today_only=True)
    if dpd_d:
        ax.bar(dpd_d, cnt_d, color=C["purple"], alpha=0.8, width=1.0)
        ax.axhline(y=4, color=C["green"], lw=1.2, linestyle="--", label="목표 4노선")
        _leg(ax, loc="lower right")
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="관측 수")

    # ⑦ DPD 구간별 가격 변동성 (ICN→NRT)
    ax = axes[6]; ax.set_title("⑦ DPD 구간별 가격 변동성 (ICN→NRT)", fontsize=9, pad=5)
    bins, stds, b_cnts = q_dpd_bin_volatility(today_only=False)
    if bins and any(s>0 for s in stds):
        colors7 = [C["blue"],C["green"],C["orange"],C["purple"],C["red"]]
        bars = ax.bar(bins, [s/10000 for s in stds], color=[colors7[i%5] for i in range(len(bins))], alpha=0.85)
        for bar, cnt in zip(bars, b_cnts):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max([s/10000 for s in stds],default=0)*0.02,
                    f"n={cnt}", ha="center", va="bottom", color=C["muted"], fontsize=6.5)
    else: _nd(ax)
    _sa(ax, xlabel="DPD 구간", ylabel="표준편차 (만원)")

    # ⑧ 오늘 가격 히스토그램 (ICN→NRT)
    ax = axes[7]; ax.set_title("⑧ 오늘 가격 히스토그램 ICN→NRT (편도)", fontsize=9, pad=5)
    prices = q_price_histogram("ICN", "NRT", today_only=True)
    if len(prices) >= 5:
        ax.hist(prices, bins=30, color=C["blue"], alpha=0.8, edgecolor=C["grid"])
        ax.axvline(np.median(prices), color=C["green"], lw=1.5, linestyle="--", label=f"중앙값 {np.median(prices):.1f}만")
        _leg(ax)
    else: _nd(ax)
    _sa(ax, xlabel="가격 (만원)", ylabel="빈도")

    # ⑨ 슬롯별 공식가격 비율
    ax = axes[8]; ax.set_title("⑨ 슬롯별 공식가격(official_price) 비율", fontsize=9, pad=5)
    qlabels, qrates = q_slot_quality()
    if qlabels:
        bars9 = ax.bar(qlabels, qrates, color=C["green"], alpha=0.85)
        ax.axhline(y=100, color=C["muted"], lw=0.8, linestyle=":")
        for bar, rate in zip(bars9, qrates):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                    f"{rate:.0f}%", ha="center", va="bottom", color=C["text"], fontsize=7.5)
        ax.set_ylim(0, 115)
    else: _nd(ax)
    _sa(ax, ylabel="공식가격 비율 (%)")

    # ⑩ 편도 vs 왕복 가격 분포 비교
    ax = axes[9]; ax.set_title("⑩ 편도 vs 왕복 가격 분포 비교 (오늘)", fontsize=9, pad=5)
    rtype_prices = q_routetype_price()
    if len(rtype_prices) >= 1:
        box_data = []; box_labels = []
        for rt in ["oneway", "roundtrip"]:
            if rt in rtype_prices:
                box_data.append(rtype_prices[rt])
                box_labels.append("편도" if rt=="oneway" else "왕복")
        if box_data:
            bp = ax.boxplot(box_data, labels=box_labels, patch_artist=True,
                            medianprops={"color": C["green"], "lw": 2},
                            flierprops={"marker": "o", "ms": 3, "alpha": 0.4,
                                        "markerfacecolor": C["muted"]})
            for patch, color in zip(bp["boxes"], [C["blue"], C["orange"]]):
                patch.set_facecolor(color); patch.set_alpha(0.6)
        else: _nd(ax)
    else: _nd(ax)
    _sa(ax, ylabel="가격 (만원)")

    return _save_png(fig)


# ─── Cumulative PNG (10패널) ───────────────────────────────────────────────────
def generate_cumul_png(summary: dict) -> bytes:
    fig, axes = _make_fig(
        f"AirChoice 누적 통계 — {summary['days_cnt']}일차",
        f"수집 시작: 2026-04-16 / 누적 search {summary['total_obs']:,}건 / offer {summary['total_offer']:,}건"
    )

    # ① 날짜별 누적 수집 추이
    ax = axes[0]; ax.set_title("① 날짜별 누적 수집 추이", fontsize=9, pad=5)
    dates, obs, offers = q_daily_trend()
    if dates:
        x = list(range(len(dates)))
        ax.bar(x, obs, color=C["blue"], alpha=0.8, width=0.4, label="search 관측", zorder=2)
        ax2r = ax.twinx()
        ax2r.plot(x, offers, color=C["green"], marker="o", ms=4, lw=2, label="offers", zorder=3)
        ax2r.tick_params(colors=C["text"], labelsize=7); ax2r.set_ylabel("offer 수", fontsize=7.5, color=C["text"])
        for sp in ax2r.spines.values(): sp.set_color(C["grid"])
        ax.set_xticks(x); ax.set_xticklabels([d[5:] for d in dates], fontsize=7.5, rotation=30)
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        ax.legend([Patch(fc=C["blue"],alpha=0.8), Line2D([0],[0],color=C["green"],marker="o",ms=4)],
                  ["search 관측","offers"], loc="upper left", fontsize=6.5,
                  facecolor=C["panel"], labelcolor=C["text"], framealpha=0.8)
    else: _nd(ax)
    _sa(ax, ylabel="search 관측 수")

    # ② 누적 노선별 관측 분포
    ax = axes[1]; ax.set_title("② 누적 노선별 관측 분포", fontsize=9, pad=5)
    rdata_all = q_route_dist(today_only=False)
    if rdata_all:
        rows_ow, rows_rt = {}, {}
        for route, rt, cnt in rdata_all:
            if rt=="oneway": rows_ow[route]=cnt
            else: rows_rt[route]=cnt
        ar = sorted(set(list(rows_ow)+list(rows_rt)))
        x2 = list(range(len(ar)))
        ax.barh(x2, [rows_ow.get(r,0) for r in ar], color=C["blue"], alpha=0.85, label="편도", height=0.38)
        ax.barh([i+0.4 for i in x2], [rows_rt.get(r,0) for r in ar], color=C["orange"], alpha=0.85, label="왕복", height=0.38)
        ax.set_yticks([i+0.19 for i in x2]); ax.set_yticklabels(ar, fontsize=7.5); _leg(ax)
    else: _nd(ax)
    _sa(ax, xlabel="관측 수")

    # ③ ICN→NRT 누적 DPD 가격 곡선
    ax = axes[2]; ax.set_title("③ ICN→NRT 누적 DPD 가격 곡선 (전체 기간)", fontsize=9, pad=5)
    dpds, mins, avgs, maxs, _ = q_dpd_price("ICN", "NRT", today_only=False)
    if dpds:
        ax.plot(dpds, [m/10000 for m in mins], color=C["green"],  lw=2, label="최저가")
        ax.plot(dpds, [a/10000 for a in avgs], color=C["orange"], lw=2, label="평균가", linestyle="--")
        ax.fill_between(dpds, [m/10000 for m in mins], [a/10000 for a in avgs], alpha=0.12, color=C["blue"])
        _leg(ax)
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="가격 (만원)")

    # ④ DPD별 누적 가격 밴드 (p25/median/p75)
    ax = axes[3]; ax.set_title("④ ICN→NRT 누적 가격 밴드 (p25/median/p75)", fontsize=9, pad=5)
    bdpds, p25s, meds, p75s = q_dpd_price_band("ICN", "NRT", today_only=False)
    if bdpds:
        ax.fill_between(bdpds, p25s, p75s, alpha=0.25, color=C["blue"], label="IQR")
        ax.plot(bdpds, meds, color=C["green"], lw=2, label="중앙값")
        ax.plot(bdpds, p25s, color=C["blue"], lw=1, linestyle="--", alpha=0.7)
        ax.plot(bdpds, p75s, color=C["blue"], lw=1, linestyle="--", alpha=0.7)
        _leg(ax)
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="가격 (만원)")

    # ⑤ 편도 4노선 누적 DPD 최저가 비교
    ax = axes[4]; ax.set_title("⑤ 편도 4노선 누적 DPD 최저가 비교", fontsize=9, pad=5)
    all_routes = q_all_routes_dpd_min(today_only=False)
    has_data = False
    for i, (route, (ds, ms)) in enumerate(all_routes.items()):
        if ds: ax.plot(ds, ms, color=ROUTE_C[i%4], lw=1.8, label=route, alpha=0.9); has_data=True
    if has_data: _leg(ax, loc="upper left")
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="최저가 (만원)")

    # ⑥ DPD별 누적 관측 밀도
    ax = axes[5]; ax.set_title("⑥ DPD별 누적 관측 밀도 (전체 기간, 편도)", fontsize=9, pad=5)
    dpd_d, cnt_d = q_dpd_density(today_only=False)
    if dpd_d:
        ax.bar(dpd_d, cnt_d, color=C["purple"], alpha=0.8, width=1.0)
    else: _nd(ax)
    _sa(ax, xlabel="DPD", ylabel="누적 관측 수")

    # ⑦ DPD 구간별 누적 변동성 (전체 기간)
    ax = axes[6]; ax.set_title("⑦ DPD 구간별 누적 가격 변동성 (ICN→NRT)", fontsize=9, pad=5)
    bins, stds, b_cnts = q_dpd_bin_volatility(today_only=False)
    if bins and any(s>0 for s in stds):
        colors7 = [C["blue"],C["green"],C["orange"],C["purple"],C["red"]]
        bars = ax.bar(bins, [s/10000 for s in stds], color=[colors7[i%5] for i in range(len(bins))], alpha=0.85)
        for bar, cnt in zip(bars, b_cnts):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max([s/10000 for s in stds],default=0)*0.02,
                    f"n={cnt}", ha="center", va="bottom", color=C["muted"], fontsize=6.5)
    else: _nd(ax)
    _sa(ax, xlabel="DPD 구간", ylabel="표준편차 (만원)")

    # ⑧ 날짜×슬롯 수집 현황 (heatmap)
    ax = axes[7]; ax.set_title("⑧ 날짜×슬롯 수집 현황", fontsize=9, pad=5)
    hm_data = q_date_slot_heatmap()
    if hm_data:
        all_dates = sorted(hm_data.keys())
        hours = [0, 8, 16]
        matrix = np.array([[hm_data.get(d, {}).get(h, 0) for h in hours] for d in all_dates])
        im = ax.imshow(matrix.T, aspect="auto", cmap="Blues",
                       vmin=0, origin="lower")
        ax.set_xticks(range(len(all_dates))); ax.set_xticklabels([d[5:] for d in all_dates], fontsize=7.5, rotation=30)
        ax.set_yticks(range(len(hours))); ax.set_yticklabels([f"{h:02d}:00" for h in hours], fontsize=7.5)
        for r in range(len(hours)):
            for c in range(len(all_dates)):
                v = matrix[c, r]
                if v > 0:
                    ax.text(c, r, str(int(v)), ha="center", va="center",
                            color="white" if v > matrix.max()*0.5 else C["text"], fontsize=7)
    else: _nd(ax)
    _sa(ax)

    # ⑨ 반복 관측 시계열 (DPD 30 이하)
    ax = axes[8]; ax.set_title("⑨ 반복 관측 시계열 — ICN→NRT DPD≤30", fontsize=9, pad=5)
    repeat_series = q_repeat_obs_sample("ICN", "NRT", max_dpd=30)
    if repeat_series:
        sample_dpds = sorted(repeat_series.keys())[:8]
        cmap = plt.cm.get_cmap("tab10", len(sample_dpds))
        for i, dpd in enumerate(sample_dpds):
            pts = repeat_series[dpd]
            xs = list(range(len(pts))); ys = [p[1] for p in pts]
            ax.plot(xs, ys, marker="o", ms=4, lw=1.5,
                    color=cmap(i), label=f"DPD={dpd}", alpha=0.9)
        ax.set_xticks([]); _leg(ax, loc="upper right", ncol=2)
    else: _nd(ax)
    _sa(ax, xlabel="관측 회차", ylabel="최저가 (만원)")

    # ⑩ 전체 가격 히스토그램 (ICN→NRT)
    ax = axes[9]; ax.set_title("⑩ 누적 가격 히스토그램 ICN→NRT (편도)", fontsize=9, pad=5)
    prices_all = q_price_histogram("ICN", "NRT", today_only=False)
    if len(prices_all) >= 5:
        ax.hist(prices_all, bins=40, color=C["blue"], alpha=0.8, edgecolor=C["grid"])
        ax.axvline(np.median(prices_all), color=C["green"], lw=1.5, linestyle="--",
                   label=f"중앙값 {np.median(prices_all):.1f}만")
        _leg(ax)
    else: _nd(ax)
    _sa(ax, xlabel="가격 (만원)", ylabel="빈도")

    return _save_png(fig)


# ─── Discord ──────────────────────────────────────────────────────────────────
def _send_png_webhook(png_bytes: bytes, filename: str,
                      title: str, desc: str, color: int) -> bool:
    if not WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL 미설정")
        return False
    try:
        import requests as req
    except ImportError:
        log.error("requests 미설치"); return False

    embed = {"title": title, "description": desc, "color": color,
             "image": {"url": f"attachment://{filename}"}}
    for attempt in range(3):
        try:
            resp = req.post(
                WEBHOOK_URL,
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={"files[0]": (filename, png_bytes, "image/png")},
                timeout=30,
            )
            if resp.status_code in (200, 204):
                log.info("Webhook 전송: %s (시도 %d)", title, attempt+1)
                return True
            log.warning("Webhook %s HTTP %d", title, resp.status_code)
        except Exception as e:
            log.warning("Webhook 실패 (시도 %d): %s", attempt+1, e)
        if attempt < 2: time.sleep(5*(attempt+1))
    log.error("Webhook 최종 실패: %s", title)
    return False


def send_fail_webhook(stage: str, error: str) -> None:
    if not WEBHOOK_URL: return
    try:
        import requests as req
        req.post(WEBHOOK_URL,
                 json={"content": f"**[AirChoice Stats] FAILED {TODAY}**\nstage=`{stage}`\n```{error[:300]}```"},
                 timeout=10)
    except Exception: pass


# ─── Main ─────────────────────────────────────────────────────────────────────
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
        log.error("q_summary 실패: %s", e); send_fail_webhook("q_summary", str(e)); return

    # Daily PNG
    try:
        log.info("daily PNG 생성 중...")
        daily_png = generate_daily_png(summary)
        (today_dir/"daily_summary.png").write_bytes(daily_png)
        (latest_dir/"daily_summary.png").write_bytes(daily_png)
        log.info("daily PNG 저장 (%d bytes)", len(daily_png))
    except Exception as e:
        log.error("generate_daily_png 실패: %s", e); send_fail_webhook("generate_daily_png", str(e)); return

    # Cumulative PNG
    try:
        log.info("cumulative PNG 생성 중...")
        cumul_png = generate_cumul_png(summary)
        (today_dir/"cumulative_summary.png").write_bytes(cumul_png)
        (latest_dir/"cumulative_summary.png").write_bytes(cumul_png)
        log.info("cumulative PNG 저장 (%d bytes)", len(cumul_png))
    except Exception as e:
        log.error("generate_cumul_png 실패: %s", e); send_fail_webhook("generate_cumul_png", str(e)); return

    # Webhook 1: 데일리
    _send_png_webhook(
        daily_png, "daily_summary.png",
        f"[AirChoice] 데일리 통계 — {TODAY}",
        f"오늘 수집: **search {summary['today_obs']:,}건** / **offer {summary['today_offer']:,}건**\n"
        f"DPD 커버: **{summary['dpd_cnt']}/120** · 공식가격 **{summary['official_rate']}%**",
        0x5865F2
    )
    time.sleep(2)

    # Webhook 2: 누적
    _send_png_webhook(
        cumul_png, "cumulative_summary.png",
        f"[AirChoice] 누적 통계 — {summary['days_cnt']}일차",
        f"누적: **search {summary['total_obs']:,}건** / **offer {summary['total_offer']:,}건**\n"
        f"수집 {summary['days_cnt']}일차 · 시작: 2026-04-16",
        0x9B59B6
    )

    log.info("=== daily stats 완료: %s ===", TODAY)


if __name__ == "__main__":
    main()
