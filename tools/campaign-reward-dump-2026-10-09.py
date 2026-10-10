#!/usr/bin/env python3
"""Dump keyword contexts from the already-downloaded forum corpora. READ-ONLY.

Usage:
  python tools/campaign-reward-dump-2026-10-09.py --ids 149251,12345 --rx 'star' --ctx 500
Control: prints the documented 149251 ladder marker; aborts if absent.
"""
import os
import re
import sys
import json
import html
import argparse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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
WS = re.compile(r'[ \t  ]+')


def strip(h):
    """Extract ONLY the post body + reply bodies, not the board's article-list
    sidebar (which repeats every thread title on the page and otherwise
    dominates every keyword screen)."""
    # 1. post body: <div class="document_<id>_<n> xe_content"> ... up to bd_prev_next
    parts = []
    m = re.search(r'<div[^>]*class="document_\d+_\d+\s+xe_content"[^>]*>(.*?)'
                  r'<div[^>]*class="bd_prev_next', h, re.S)
    if m:
        parts.append(m.group(1))
    # 2. every comment body
    for c in re.finditer(r'<div[^>]*class="comment_\d+_\d+\s+xe_content"[^>]*>(.*?)'
                         r'<div[^>]*class="fdb_nav', h, re.S):
        parts.append(c.group(1))
    body = '\n'.join(parts) if parts else h
    body = SCRIPT.sub(' ', body)
    body = TAG.sub(' ', body)
    body = html.unescape(body)
    body = WS.sub(' ', body)
    # collapse every whitespace run (incl. newlines) to one space so contexts
    # are readable; Board templates emit huge blank runs.
    body = re.sub(r'\s+', ' ', body)
    return body


def load():
    out = {}
    for d in DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if not (os.path.isfile(p) and f.lower().endswith(('.html', '.htm'))):
                continue
            try:
                out[p] = strip(open(p, 'r', encoding='utf-8', errors='replace').read())
            except Exception:
                pass
    return out


def pid(p):
    m = re.search(r'(\d{5,7})', os.path.basename(p))
    return m.group(1) if m else os.path.basename(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='')
    ap.add_argument('--rx', default='')
    ap.add_argument('--ctx', type=int, default=500)
    ap.add_argument('--max', type=int, default=200)
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    sink = []
    def emit(s):
        if a.out:
            sink.append(s)
        else:
            print(s)

    T = load()
    # POSITIVE CONTROL
    ctl = any(pid(p) == '149251' and 'Metron Crystals' in t for p, t in T.items())
    print('CONTROL 149251/"Metron Crystals":', 'PASS' if ctl else 'FAIL',
          '| files', len(T))
    if not ctl:
        print('ABORT')
        return 2

    if a.ids:
        want = {x.strip() for x in a.ids.split(',') if x.strip()}
        sel = [(p, t) for p, t in T.items() if pid(p) in want]
        print('selected files:', len(sel), 'ids', len({pid(p) for p, _ in sel}))
    else:
        sel = list(T.items())

    rx = re.compile(a.rx, re.I) if a.rx else None
    n = 0
    out = []

    def emit(s):
        out.append(s)
        if not a.out:
            print(s)

    for p, t in sorted(sel, key=lambda kv: pid(kv[0])):
        if not rx:
            emit('\n##### %s  (%s)' % (pid(p), os.path.relpath(p)))
            emit(t[:4000])
            n += 1
            if n >= a.max:
                break
            continue
        for m in rx.finditer(t):
            s = max(0, m.start() - a.ctx)
            e = min(len(t), m.end() + a.ctx)
            emit('\n##### %s  (%s)  @%d' % (pid(p), os.path.relpath(p), m.start()))
            emit(t[s:e])
            n += 1
            if n >= a.max:
                emit('\n[max contexts reached: %d]' % n)
                if a.out:
                    open(a.out, 'w', encoding='utf-8').write('\n'.join(out))
                return 0
    if a.out:
        open(a.out, 'w', encoding='utf-8').write('\n'.join(out))
    print('[contexts: %d]' % n, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())