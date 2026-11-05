#!/usr/bin/env python3
"""各社の RSS を取得し、アプリ（news-globe.html）が読む news.json を作る。

GitHub Actions（.github/workflows/news-feed.yml）から1時間ごとに実行し、
結果は news-data ブランチに置く。API キーは使わない。

使い方: python3 tools/fetch_news.py --feeds tools/feeds.json --html news-globe.html \
            --prev out/news.json --out out/news.json
"""
import argparse
import concurrent.futures as cf
import email.utils
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

KEEP_DAYS = 7          # アプリの期間の上限（1d / 3d / 7d）に合わせる
MAX_ITEMS = 4000       # JSON が大きくなりすぎないための上限
SUMMARY_LEN = 160      # 照合用の要約の長さ（表示はしない）
UA = "NewsGlobe-feed-bot/1.0 (+https://github.com/velqiron/news-globe)"

# アプリの言語名（GDELT の表記。アプリ側の表 ma で言語コードに変換される）
LANG_NAME = {"en": "English", "ja": "Japanese", "zh": "Chinese", "ko": "Korean",
             "es": "Spanish", "fr": "French", "pt": "Portuguese", "de": "German",
             "ar": "Arabic", "hi": "Hindi", "th": "Thai", "vi": "Vietnamese"}
# 単語の区切りに空白を使わない言語は部分一致で照合する
NO_SPACE = {"ja", "zh", "th"}


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child_text(el, *names):
    for c in el:
        if local(c.tag) in names:
            if local(c.tag) == "link" and not (c.text or "").strip():
                href = c.get("href")
                if href and c.get("rel", "alternate") == "alternate":
                    return href
                continue
            return (c.text or "").strip()
    return ""


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
        if d is not None:
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_feed(raw):
    root = ET.fromstring(raw)
    out = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        title = strip_tags(child_text(el, "title"))
        link = child_text(el, "link") or child_text(el, "guid")
        summ = strip_tags(child_text(el, "description", "summary", "encoded", "content"))
        date = parse_date(child_text(el, "pubDate", "published", "updated", "date"))
        if title and link.startswith("http"):
            out.append((title, link.strip(), summ, date))
    return out


def build_tagger(html_path):
    """国名（CLDR・12言語）と人口100万以上の都市名（アプリ内の地名データ）から、
    言語ごとの照合表を作る。一致したら国コード（cc）と英語の都市名（k）を記事に付ける。"""
    from babel import Locale

    page = open(html_path, encoding="utf-8").read()

    def data(i):
        m = re.search(r'<script type="application/json" id="%s">' % i, page)
        st = m.end()
        return json.loads(page[st:page.index("</script>", st)])

    places, names = data("d-places"), data("d-names")
    en = Locale("en").territories
    # アプリ内の英語の別名・形容詞の表（qb。例: JP → Japanese、TR → Turkish）
    alias = {}
    m = re.search(r"(?<![\w$.])qb=(\{[^}]*\})", page)
    if m:
        body = re.sub(r"([{,])([A-Z]{2}):", r'\1"\2":', m.group(1))
        body = re.sub(r"\\x([0-9A-Fa-f]{2})", r"\\u00\1", body)
        for cc, lst in json.loads(body).items():
            # 「US」は小文字にすると代名詞の us と区別できないので、点付きの U.S. だけ使う
            alias[cc] = [x for x in lst if not re.fullmatch(r"[A-Z]{2,3}", x)]
    countries = {cc: en[cc] for cc in en if re.fullmatch(r"[A-Z]{2}", cc) and cc not in ("EU", "EZ", "UN", "XA", "XB", "QO", "ZZ")}
    tables = {}
    for lg in LANG_NAME:
        terms = {}  # 小文字の語 → ("cc", コード) / ("k", 英語の都市名)
        loc = Locale.parse("zh_Hans" if lg == "zh" else lg)
        for cc in countries:
            for nm in {loc.territories.get(cc), en.get(cc), *alias.get(cc, [])}:
                if nm and len(nm) >= 2:
                    terms.setdefault(nm.lower(), ("cc", cc))
        for idx, p in enumerate(places):
            if p[4] < 1_000_000:
                continue
            local_nm = p[2] if lg == "ja" else (names["p"][lg][idx] if lg in names["p"] else None)
            for nm in {p[3], local_nm}:
                if nm and len(nm) >= 2:
                    terms.setdefault(nm.lower(), ("k", p[3]))
        alts = sorted(terms, key=len, reverse=True)
        body = "|".join(re.escape(a) for a in alts)
        rx = re.compile(body if lg in NO_SPACE else r"(?<![\w])(?:%s)(?![\w])" % body)
        tables[lg] = (rx, terms)

    def tag(text, lg):
        rx, terms = tables[lg]
        ccs, ks = set(), set()
        for m in rx.finditer(text.lower()):
            kind, val = terms[m.group(0)]
            (ccs if kind == "cc" else ks).add(val)
        return sorted(ccs), sorted(ks)

    return tag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feeds", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--prev")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    feeds = json.load(open(a.feeds, encoding="utf-8"))
    tag = build_tagger(a.html)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=KEEP_DAYS)

    prev = {}
    if a.prev:
        try:
            for it in json.load(open(a.prev, encoding="utf-8")).get("items", []):
                prev[it["u"]] = it
        except (OSError, ValueError, KeyError):
            pass

    def one(f):
        t0 = time.time()
        try:
            return f, parse_feed(fetch(f["url"])), None, time.time() - t0
        except Exception as e:  # 1件の失敗で全体を止めない
            return f, [], f"{type(e).__name__}: {e}"[:200], time.time() - t0

    status, items = [], dict(prev)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for f, arts, err, dt in ex.map(one, feeds):
            status.append({"id": f["id"], "ok": err is None, "n": len(arts), "err": err})
            print(f"{'OK ' if err is None else 'NG '} {f['id']:<20} {len(arts):>4} {dt:5.1f}s {err or ''}", flush=True)
            for title, url, summ, date in arts:
                old = items.get(url)
                d = date or (datetime.strptime(old["p"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc) if old else now)
                if d > now + timedelta(hours=1):  # 未来の日付は取得時刻に丸める
                    d = now
                summ = summ[:SUMMARY_LEN]
                ccs, ks = tag(f"{title} {summ}", f["lang"])
                # 国内向けの媒体（feeds.json の home）で国名が出てこない記事は、その国の記事とみなす
                if not ccs and f.get("home"):
                    ccs = [f["home"]]
                host = urlsplit(url).hostname or ""
                items[url] = {"t": title, "s": summ, "u": url,
                              "d": host[4:] if host.startswith("www.") else host,
                              "l": LANG_NAME[f["lang"]], "c": f["country"],
                              "p": d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                              "cc": ccs, "k": ks}

    keep = [it for it in items.values()
            if datetime.strptime(it["p"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc) >= cutoff]
    keep.sort(key=lambda it: it["p"], reverse=True)
    keep = keep[:MAX_ITEMS]
    out = {"v": 1, "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "feeds": status, "items": keep}
    with open(a.out, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
    ok = sum(s["ok"] for s in status)
    print(f"feeds ok {ok}/{len(status)}, items {len(keep)}")
    if ok == 0:
        sys.exit(1)  # 全滅なら前回のデータを上書きしない


if __name__ == "__main__":
    main()
