#!/usr/bin/env python3
import datetime as dt
import json, re, sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cirje.e.u-tokyo.ac.jp/research/03research03ws.html"
WORKSHOPS = {
    "Macroeconomics Workshop":      r"Macroeconomics Workshop",
    "Microeconomic Theory Workshop":r"Microeconomic Theory Workshop",
    "Urban Economics Workshop":     r"Urban Economics Workshop",
    "Applied Statistics Workshop":  r"The Applied Statistics Workshop",
    "Empirical Microeconomics Workshop": r"Empirical Microeconomics Workshop",
}

TODAY = dt.date.today()

def fetch():
    html = requests.get(BASE_URL, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for ws_name, pattern in WORKSHOPS.items():
        header = soup.find("h3", string=re.compile(pattern, re.I))
        if not header:
            continue
        # テーブル or <p> リスト直後を探す
        node = header.find_next(["table", "ul", "ol", "p"])
        rows = node.select("tr") or node.select("p")  # 形式揺れ対策
        for r in rows:
            text = " ".join(r.stripped_strings)
            # 例: "2025年7月24日 (木)  Masao Fukui  “Optimal Dynamic Spatial Policy”"
            m = re.match(r"(\d{4})年?(\d{1,2})月(\d{1,2})日.*?([A-Z][^“”]+?)\s+[“\"]?(.+?)[”\"]?$", text)
            if not m:
                continue
            y, mth, d, speaker, title = m.groups()
            event_date = dt.date(int(y), int(mth), int(d))
            if event_date >= TODAY:
                events.append({
                    "date": event_date.isoformat(),
                    "ws": ws_name,
                    "speaker": speaker.strip(),
                    "title": title.strip(),
                })
    return sorted(events, key=lambda x: x["date"])

def render_html(events):
    items = "\n".join(
        f'    <li>{e["date"]} – <strong>{e["ws"]}</strong> – '
        f'{e["speaker"]} – “{e["title"]}”</li>'
        for e in events
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<meta charset="utf-8">
<title>CIRJE Workshops – Upcoming</title>
<body>
  <h2>今後のセミナー予定（自動更新）</h2>
  <ul>
{items}
  </ul>
  <p style="font-size:smaller">Last updated: {dt.datetime.now():%Y-%m-%d %H:%M JST}</p>
</body>
</html>
"""

def main():
    ev = fetch()
    Path("docs/index.html").write_text(render_html(ev), encoding="utf-8")
    # JSON も残しておくと他の用途に便利
    Path("events.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

