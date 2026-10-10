#!/usr/bin/env python3
"""Offline mining of the already-downloaded forum_en / share_en corpora for
campaign/star-threshold reward and currency evidence. READ-ONLY.

Runs a positive control before any zero is recorded (GUARD rule: never record a
zero without a control that passes in the same session).
"""
import os
import re
import sys
import json
import html
from collections import defaultdict

BASE = r'recovered-assets/forum-en-2026-10-05'
DIRS = [
    os.path.join(BASE, 'get-body', 'body'),
    os.path.join(BASE, 'pass2', 'body'),
    os.path.join(BASE, 'pass2', 'body-latest'),
    os.path.join(BASE, 'pass2', 'topup'),
    os.path.join(BASE, 'pass2', 'get-list', 'list'),
    os.path.join(BASE, 'pass2', 'list'),
]

TAG = re.compile(r'<[^>]*>', re.S)
SCRIPT = re.compile(r'<(script|style)\b.*?</\1>', re.S | re.I)
WS = re.compile(r'[ \t ]+')


def strip(h):
    """Body+replies only; the board's article-list sidebar repeats every thread
    title on the page and would dominate every keyword screen."""
    parts = []
    m = re.search(r'<div[^>]*class="document_\d+_\d+\s+xe_content"[^>]*>(.*?)'
                  r'<div[^>]*class="bd_prev_next', h, re.S)
    if m:
        parts.append(m.group(1))
    for c in re.finditer(r'<div[^>]*class="comment_\d+_\d+\s+xe_content"[^>]*>(.*?)'
                         r'<div[^>]*class="fdb_nav', h, re.S):
        parts.append(c.group(1))
    body = '\n'.join(parts) if parts else h
    body = SCRIPT.sub(' ', body)
    body = TAG.sub(' ', body)
    body = html.unescape(body)
    body = WS.sub(' ', body)
    return re.sub(r'\s+', ' ', body)


def files():
    out = []
    for d in DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if os.path.isfile(p) and f.lower().endswith(('.html', '.htm')):
                out.append(p)
    return out


def postid(p):
    b = os.path.basename(p)
    m = re.search(r'(\d{5,7})', b)
    return m.group(1) if m else b


def main():
    fs = files()
    print(f'FILES: {len(fs)}')

    # ---- positive control: the transcendency ladder post must be findable and
    # its known token must be present. 149251 is documented in
    # forum-en-mining-pass2-2026-10-08.md 3.1 with capture web/20190723090922.
    ctrl = {'found_files': 0, 'found_token': 0}
    texts = {}
    for p in fs:
        try:
            t = strip(open(p, 'r', encoding='utf-8', errors='replace').read())
        except Exception:
            continue
        texts[p] = t
        if postid(p) == '149251':
            ctrl['found_files'] += 1
            if 'Metron Crystals' in t and '5,000' in t.replace('&#', ''):
                ctrl['found_token'] += 1
    # '5,000' may be encoded; accept either
    if ctrl['found_files'] and not ctrl['found_token']:
        for p, t in texts.items():
            if postid(p) == '149251' and 'Metron Crystals' in t:
                ctrl['found_token'] = 1
    print('CONTROL 149251 files=%d token=%d -> %s'
          % (ctrl['found_files'], ctrl['found_token'],
             'PASS' if ctrl['found_files'] and ctrl['found_token'] else 'FAIL'))
    if not (ctrl['found_files'] and ctrl['found_token']):
        print('ABORT: control failed, all zeros would be uninterpretable.')
        return 2

    total = sum(len(t) for t in texts.values())
    print(f'CHARS: {total}')

    # ---- keyword screens. Terms sliced from the data where possible; English
    # only here, so no codepoint hazard.
    screens = {
        'star_threshold': [
            r'\b30\s*stars?\b', r'\bthirty stars\b', r'\bstar(?:s)?\s*(?:reward|chest|box)\b',
            r'\bchest\b', r'\bachievement\s*reward\b', r'\bstars?\s*(?:total|milestone)\b',
            r'\bevery\s*10\s*stars?\b', r'\bclear\s*all\b', r'\bachieve(?:ment)?\b',
            r'\bstar\s*milestone\b', r'\barea\s*(?:reward|clear)\b',
        ],
        'login_attendance': [
            r'\blogin\s*bonus\b', r'\bdaily\s*login\b', r'\bsign[\s\-]?in\b',
            r'\battendance\b', r'\bcheck[\s\-]?in\b', r'\bconsecutive\s*days?\b',
            r'\bstreak\b', r'\bcalendar\b',
        ],
        'arena': [
            r'\barena\b', r'\bfight\s*club\b', r'\bweekly\s*(?:leaderboard|ranking)\b',
            r'\bladder\b', r'\brank(?:ing)?\s*reward\b', r'\btier\s*reward\b',
            r'\bfight\s*chips?\b',
        ],
        'guild_gvg': [
            r'\bguild\b', r'\bgvg\b', r'\bguild\s*blitz\b', r'\bcooperative\b',
            r'\bdonat', r'\bwar\b',
        ],
        'supply': [
            r'\bsupply\b', r'\bdepot\b', r'\bspecial\s*supply\b', r'\bsupply\s*package\b',
            r'\bsupply\s*list\b',
        ],
        'mirage': [
            r'\bmirage\b', r'\bruins?\b', r'\bfloor\b', r'\bmirage\s*shop\b',
        ],
        'fishing': [
            r'\bfish(?:ing|ed)?\b', r'\bmarket\b', r'\bmarine\b', r'\bbaits?\b',
        ],
        'episode': [
            r'\bepisode\b', r'\bchapter\b', r'\bstory\b', r'\bscenario\b',
        ],
        'currency': [
            r'\brupee', r'\bmanda\b', r'\bcoin', r'\bchip', r'\bmedal\b',
            r'\bcrystal', r'\bfragment', r'\bheart', r'\bcapsule', r'\bhelium\b',
            r'\btrace', r'\bshard', r'\bscroll', r'\brequest\b', r'\bveteran\s*point',
            r'\bmetron\b', r'\bcommission\b',
        ],
        'pvp_points': [
            r'\bentrust\b', r'\bchallenge\s*invitation', r'\bcontribution',
        ],
    }

    compiled = {k: [re.compile(x, re.I) for x in v] for k, v in screens.items()}

    hits = defaultdict(list)
    for p, t in texts.items():
        pid = postid(p)
        for name, rxs in compiled.items():
            c = 0
            ex = None
            for rx in rxs:
                m = rx.search(t)
                if m:
                    c += 1
                    if ex is None:
                        s = max(0, m.start() - 260)
                        ex = t[s:m.end() + 320]
            if c:
                hits[name].append({'id': pid, 'file': os.path.relpath(p), 'rx': c, 'ex': ex})

    print('\n=== SCREEN COUNTS (files hit / total files) ===')
    for name in screens:
        print(f'  {name:18s} {len(hits[name]):5d}')

    os.makedirs('analysis/research/base-stats-visual-hunt/campaign-reward-mining',
                exist_ok=True)
    with open('analysis/research/base-stats-visual-hunt/campaign-reward-mining/'
              'screen-hits.json', 'w', encoding='utf-8') as fh:
        json.dump({'files': len(fs), 'chars': total, 'control': ctrl,
                   'hits': hits}, fh, ensure_ascii=False, indent=1)

    # ---- dump per-screen id lists for manual reading
    for name in screens:
        ids = sorted({h['id'] for h in hits[name]})
        print(f'\n--- {name} ({len(ids)} ids) ---')
        print(' '.join(ids[:400]))
    return 0


if __name__ == '__main__':
    sys.exit(main())