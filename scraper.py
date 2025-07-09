#!/usr/bin/env python3
"""
CIRJE Workshop Scraper  (Macroeconomics / Urban Economics / Applied Statistics)
--------------------------------------------------------------------
ワークショップごとに独立した parse_*() を呼び出し、
今日以降の予定を HTML & JSON で出力。

使い方
  python scraper.py --debug   抽出結果だけターミナル表示
  python scraper.py           docs/index.html と events.json を上書き
"""

from __future__ import annotations
import datetime as dt
import json, re, sys
from pathlib import Path
from typing import Dict, List, Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as du


# ─── 共通定数 & ヘルパ ────────────────────────────────────
TODAY = dt.date.today()
BASE_TOP = "https://www.cirje.e.u-tokyo.ac.jp/research/03research03ws.html"

MONTH_RE = re.compile(
    r"\b("
    "January|February|March|April|May|June|July|August|September|October|November|December"
    r")\s+\d{1,2}\b",
    re.I,
)
DATE_JP_RE = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日")

def fetch_html(url: str) -> str:
    """文字コード混在対策: UTF-8 → EUC-JP → Shift_JIS 順に試す"""
    resp = requests.get(url, timeout=30)
    for enc in ("utf-8", "euc_jp", "shift_jis", "cp932"):
        try:
            return resp.content.decode(enc)
        except UnicodeDecodeError:
            continue
    return resp.text            # 最後の手段

def strip_weekday(s: str) -> str:
    """“July 10 (Thu) 10:25-12:10” → “July 10”"""
    return re.sub(r"[（(].*?[）)]", "", s).strip()

def normalize_date(date_raw: str, base_year: int) -> dt.date | None:
    """
    “July 10”, “2025年7月10日” など → datetime.date
    学年度を想定: 1–3 月で今日より過去なら翌年に繰り上げ
    """
    try:
        d = du.parse(
            date_raw,
            fuzzy=True,
            default=dt.datetime(base_year, 1, 1),
            dayfirst=False,
            yearfirst=False,
        ).date()
    except (du.ParserError, ValueError):
        return None
    if d < TODAY and d.month <= 3:
        d = d.replace(year=d.year + 1)
    return d


# ─── 1. Macroeconomics Workshop ─────────────────────────
URL_MACRO = "https://www.cirje.e.u-tokyo.ac.jp/research/workshops/macro/macro.html"

def parse_macro(url: str = URL_MACRO) -> List[Dict]:
    """
    1 つのブロック構造
        Date & Time: ...
        Venue: ...
        Speaker:
        (1 行以上)
        Title:
        (1 行以上)
    Speaker: 行の次行から “次の Date ラベル行” 直前までを
    すべて集め、改行ごとに ', ' で連結して info に入れる。
    どこかに 'TBA' があれば info は 'TBA'。
    """
    lines = [
        ln.strip()
        for ln in BeautifulSoup(fetch_html(url), "html.parser").get_text("\n").splitlines()
        if ln.strip()
    ]

    events: List[Dict] = []
    base_year = 2025
    i, n = 0, len(lines)

    while i < n:
        # Past Seminars で打ち切り
        if "past seminars" in lines[i].lower():
            break

        # ---- Date ラベル行 -------------------------------------------------
        if lines[i].lower().startswith("date"):
            if i + 1 >= n:
                break
            date_raw = strip_weekday(lines[i + 1])
            i += 2

            # ---- Speaker ラベルを探す -----------------------------------
            while i < n and not lines[i].lower().startswith("speaker"):
                i += 1
            if i >= n - 1:
                break
            i += 1  # ← Speaker ラベル行を飛ばし、内容開始

            # ---- コンテンツ収集 -----------------------------------------
            content = []
            while i < n and not lines[i].lower().startswith("date"):
                if lines[i].lower().startswith("title"):
                    i += 1          # 'Title:' ラベル自体はスキップ
                    continue
                if lines[i]:
                    content.append(lines[i].strip("“”\""))
                i += 1

            if not content:
                continue

            # TBA 判定 & 連結
            info = ", ".join(content)

            d = normalize_date(date_raw, base_year)
            if d and d >= TODAY:
                events.append(
                    {"date": d.isoformat(),
                     "ws":   "Macroeconomics WS",
                     "info": info}
                )
            continue
        i += 1
    return events


# ─── 2. Urban Economics Workshop ────────────────────────
URL_URBAN = "https://www.cirje.e.u-tokyo.ac.jp/research/workshops/urban/urban.html"

def parse_urban(url: str = URL_URBAN) -> List[Dict]:
    lines = [
        ln.strip()
        for ln in BeautifulSoup(fetch_html(url), "html.parser").get_text("\n").splitlines()
        if ln.strip()
    ]

    LABEL_RE = re.compile(r"^(日時|Venue|報告|Speaker)", re.I)
    ABS_RE   = re.compile(r"(abstract|要旨)", re.I)

    events: List[Dict] = []
    base_year = 2025
    i, n = 0, len(lines)

    while i < n:
        # 過年度セクションで終了
        if "past seminars" in lines[i].lower():
            break

        # ── 日時ラベル ─────────────────────────────
        if lines[i].startswith("日時"):
            if i + 1 >= n:
                break
            date_raw = strip_weekday(lines[i + 1])
            i += 2

            # ── 報告ラベル検索 ────────────────────
            while i < n and not lines[i].startswith("報告"):
                i += 1
            if i >= n - 1:
                break
            i += 1  # 報告ラベル行を飛ばして内容開始

            content = []
            while (
                i < n
                and not lines[i].startswith("日時")
                and not LABEL_RE.match(lines[i])
                and not ABS_RE.search(lines[i])
            ):
                if lines[i]:
                    content.append(lines[i].strip("“”\""))
                i += 1

            if not content:
                continue

            # info 組み立て
            info = ", ".join(content)

            d = normalize_date(date_raw, base_year)
            if d and d >= TODAY:
                events.append(
                    {"date": d.isoformat(), "ws": "Urban Economics WS", "info": info}
                )
            continue
        i += 1
    return events

# ─── 3. Applied Statistics Workshop ─────────────────────
URL_STATS = "https://www.cirje.e.u-tokyo.ac.jp/research/workshops/stateng/stateng.html"

def parse_stats(url: str = URL_STATS) -> List[Dict]:
    """日時＋報告を収集し、行間は ', ' で連結。Abstract 以降は除外"""
    lines = [
        ln.strip()
        for ln in BeautifulSoup(fetch_html(url), "html.parser").get_text("\n").splitlines()
        if ln.strip()
    ]

    events: List[Dict] = []
    base_year = 2025
    i, n = 0, len(lines)

    LABEL_RE   = re.compile(r"^(日時|Venue|報告|Speaker)", re.I)
    ABS_RE     = re.compile(r"abstract", re.I)

    while i < n:
        if lines[i].startswith("日時"):
            if i + 1 >= n:
                break
            date_raw = strip_weekday(lines[i + 1])
            i += 2

            # --- 報告ラベル検索 ----------------------------------------
            while i < n and not lines[i].startswith("報告"):
                i += 1
            if i >= n - 1:                # 内容行が無ければブレーク
                break
            i += 1                        # 報告ラベルを飛ばして内容開始

            content = []
            while i < n and not lines[i].startswith("日時") and not ABS_RE.search(lines[i]) and not LABEL_RE.match(lines[i]):
                if lines[i]:
                    content.append(lines[i].strip("“”\""))
                i += 1

            if not content:
                continue

            # info 組み立て
            info = ", ".join(content)

            d = normalize_date(date_raw, base_year)
            if d and d >= TODAY:
                events.append({"date": d.isoformat(),
                               "ws": "Applied Statistics WS",
                               "info": info})
            continue
        i += 1
    return events

# ── Empirical Microeconomics Workshop ───────────────────
URL_EMPIRICAL = "https://www.cirje.e.u-tokyo.ac.jp/research/workshops/emf/emf.html"

def parse_empirical(url: str = URL_EMPIRICAL) -> list[dict]:
    soup  = BeautifulSoup(fetch_html(url), "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]

    DATE_RE   = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}", re.I)
    ST_RE     = re.compile(r"speaker\s*(?:&|and)\s*title", re.I)
    LABEL_RE  = re.compile(r"^(date|venue|speaker)", re.I)
    ABS_RE    = re.compile(r"abstract", re.I)

    events, last_date = [], None
    i, n = 0, len(lines)

    while i < n:
        txt = lines[i]

        # Past Seminars で打ち切り
        if "past seminars" in txt.lower() or "以下本年度終了分" in txt:
            break

        # 日付行
        if DATE_RE.search(txt):
            last_date = strip_weekday(txt)
            i += 1
            continue

        # Speaker & Title ラベル
        if ST_RE.search(txt):
            content = []
            j = i + 1
            while j < n and not LABEL_RE.match(lines[j]) and not ABS_RE.search(lines[j]):
                if lines[j]:                         # 空行除外
                    content.append(lines[j].strip("“”\""))
                j += 1

            if not last_date or not content:
                i = j
                continue

            # info 組み立て
            info = ", ".join(content)

            d = normalize_date(last_date, 2025)
            if d and d >= TODAY:
                events.append({
                    "date": d.isoformat(),
                    "ws":   "Empirical Micro WS",
                    "info": info
                })
            i = j
            continue

        i += 1
    return events

URL_MICRO = (
    "https://www.computer-services.e.u-tokyo.ac.jp/wp/"
    "events/list/?tribe_eventcategory%5B0%5D=7&tribe_eventcategory%5B1%5D=8"
)

def parse_micro(url: str = URL_MICRO) -> list[dict]:
    list_soup = BeautifulSoup(fetch_html(url), "html.parser")
    ev_divs   = list_soup.select("div.tribe-events-calendar-list__event-wrapper")

    events = []
    for div in ev_divs:
        # 1) 日付
        t = div.find("time")
        if not t or "datetime" not in t.attrs:
            continue
        d_iso = t["datetime"].split("T")[0]
        if dt.date.fromisoformat(d_iso) < TODAY:
            continue

        # 2) 詳細ページ
        a = div.find("a", class_="tribe-events-calendar-list__event-title-link")
        if not a or "href" not in a.attrs:
            continue
        detail_soup = BeautifulSoup(fetch_html(a["href"]), "html.parser")
        lines = [
            ln.strip()
            for ln in detail_soup.get_text("\n").splitlines()
            if ln.strip()
        ]

        author = title = None
        for idx, ln in enumerate(lines):
            if "Microeconomic Theory Workshop" in ln:
                author = ln.split("Microeconomic Theory Workshop")[0].strip("　 ").rstrip()
            if ln.lower().startswith(("title:", "タイトル:")):
                title = ln.split(":", 1)[-1].split("：", 1)[-1].strip()
            if author and title:
                break

        # info 組み立て
        if not author or not title:
            continue
        if "tba" in (author + title).lower():
            info = "TBA"
        else:
            info = f"{author}, {title}"

        events.append(
            {"date": d_iso, "ws": "Micro Theory WS", "info": info}
        )

    return events


# ─── 4. パーサ一覧 & 実行 ──────────────────────────────
PARSERS: Dict[str, Callable[[], List[Dict]]] = {
    "macro": parse_macro,
    "urban": parse_urban,
    "stats": parse_stats,
    "emf": parse_empirical,
    "micro":  parse_micro,          
}

def fetch_all(debug: bool = False) -> List[Dict]:
    all_events: List[Dict] = []
    for key, fn in PARSERS.items():
        try:
            evs = fn()
            all_events.extend(evs)
            if debug:
                print(f"[{key}] {len(evs)} events")
        except Exception as e:
            print(f"[ERROR] {key}: {e}", file=sys.stderr)
    all_events.sort(key=lambda x: x["date"])
    if debug:
        for e in all_events:
            print(e)
    return all_events


# ─── 5. 出力────────────────────────────────────────────
def render_html(events: List[Dict]) -> str:
    items = "\n".join(
        f'    <li>{e["date"]} – <strong>{e["ws"]}</strong> – {e["info"]}</li>'
        for e in events
    )
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M JST")
    return f"""<!DOCTYPE html>
<html lang="ja">
<meta charset="utf-8">
<title>CIRJE Workshops – Upcoming</title>
<body>
  <h2>今後のセミナー予定（自動更新）</h2>
  <ul>
{items}
  </ul>
  <p style="font-size:smaller">Last updated: {now}</p>
</body>
</html>"""


def main():
    debug = "--debug" in sys.argv
    ev = fetch_all(debug=debug)
    if debug:
        return
    Path("docs/index.html").write_text(render_html(ev), encoding="utf-8")
    Path("events.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()