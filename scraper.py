#!/usr/bin/env python3
import datetime as dt
import re, sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as du  # ← NEW

BASE_URL = "https://www.cirje.e.u-tokyo.ac.jp/research/03research03ws.html"
WORKSHOPS = {
    "Macroeconomics Workshop":      r"Macroeconomics Workshop",
    "Microeconomic Theory Workshop":r"Microeconomic Theory Workshop",
    "Urban Economics Workshop":     r"Urban Economics Workshop",
    "The Applied Statistics Workshop": r"The Applied Statistics Workshop",
    "Empirical Microeconomics Workshop": r"Empirical Microeconomics Workshop",
}
TODAY = dt.date.today()

def fetch(debug=False):
    html = requests.get(BASE_URL, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    events = []

    for ws, patt in WORKSHOPS.items():
        # h1〜h4 どれでも拾う
        head = soup.find(re.compile("^h[1-4]$"), string=re.compile(patt, re.I))
        if not head:
            continue

        tbl = head.find_next("table")
        if not tbl:
            continue

        for tr in tbl.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 2:
                continue

            # cells[0] → 日付、cells[1] → 発表者、cells[2] 以降 → タイトル
            date_txt, speaker = cells[0], cells[1]
            title = " ".join(cells[2:]) if len(cells) >= 3 else "TBA"

            # dateutil が大抵の表記をパースしてくれる
            try:
                d = du.parse(date_txt, dayfirst=False, yearfirst=False).date()
            except (du.ParserError, ValueError):
                if debug: print("!! date parse fail:", date_txt, file=sys.stderr)
                continue

            if d >= TODAY:
                events.append(
                    dict(date=d.isoformat(), ws=ws, speaker=speaker, title=title)
                )

    events.sort(key=lambda x: x["date"])
    if debug:
        for e in events: print(e)
    return events

def render_html(events):
    items = "\n".join(
        f'    <li>{e["date"]} – <strong>{e["ws"]}</strong> – '
        f'{e["speaker"]} – “{e["title"]}”</li>'
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
</html>
"""

def main():
    debug = "--debug" in sys.argv
    ev = fetch(debug=debug)
    if debug:
        return
    Path("docs/index.html").write_text(render_html(ev), encoding="utf-8")
    Path("events.json").write_text(str(ev), encoding="utf-8")

if __name__ == "__main__":
    main()