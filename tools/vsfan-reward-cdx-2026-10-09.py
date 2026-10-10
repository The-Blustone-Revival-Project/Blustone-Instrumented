#!/usr/bin/env python3
"""CDX query for exact vsfan URLs, then fetch each capture. http:// only."""
import sys
import re
import hashlib
import requests
from requests.adapters import HTTPAdapter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
S = requests.Session()
S.headers.update({'User-Agent': 'blustone-reward-research/1.0'})
S.mount('http://', HTTPAdapter(pool_connections=2, pool_maxsize=2))

CONTROL = ('http://web.archive.org/web/2021/'
           'https://bs.visualshower.com/files/attach/images/75605/303/534/001/'
           '725a8e175454a533e96dac68fc5fdb49.jpg')


def ctl():
    r = S.get(CONTROL, timeout=60)
    ok = r.status_code == 200 and len(r.content) == 57414
    print('CONTROL code=%s size=%s -> %s' % (r.status_code, len(r.content),
                                            'PASS' if ok else 'FAIL'),
          flush=True)
    return ok


TITLES = ['Expedition_Area', 'List_of_Blustone_Items', 'Guide_to_Blustone',
          'Fight_Club', 'Hunter_Shop', 'Hunter_Supply_Station', 'Abyss_Area',
          'Veteran_Status', 'Hunters%27_Drop_Rate']

if not ctl():
    print('ABORT')
    sys.exit(2)

for t in TITLES:
    url = 'http://web.archive.org/cdx/search/cdx?url=vsfan.net/wiki/%s' % t
    url += '&matchType=exact&output=json&limit=200&collapse=digest'
    for attempt in range(4):
        try:
            r = S.get(url, timeout=90)
            if r.status_code == 200:
                break
        except Exception:
            pass
    try:
        rows = r.json()
    except Exception:
        print('%-26s CDX FAIL %s' % (t, r.status_code))
        continue
    if not rows or len(rows) < 2:
        print('%-26s CDX %d rows' % (t, 0 if not rows else len(rows) - 1))
        continue
    hdr, data = rows[0], rows[1:]
    print('%-26s CDX %d captures: %s' % (
        t, len(data), ', '.join(x[1] for x in data[:8])))
    for row in data:
        ts = row[1]
        orig = row[2]
        f = 'http://web.archive.org/web/%sid_/%s' % (ts, orig)
        for a in range(4):
            try:
                rr = S.get(f, timeout=90)
                if rr.status_code == 200:
                    break
            except Exception:
                pass
        b = rr.content
        bad = (b'Temporarily Offline' in b[:4000] or b'not archived' in b[:4000])
        h = hashlib.sha256(b).hexdigest()[:16]
        import html as _h
        s = b.decode('utf-8', 'replace')
        m = re.search(r'mw-parser-output(.*?)printfooter', s, re.S)
        body = m.group(1) if m else s
        k = re.search(r'Regional rewards(.{0,700})', body)
        flag = ''
        if k:
            txt = re.sub(r'<[^>]*>', ' ', k.group(0))
            txt = re.sub(r'\s+', ' ', _h.unescape(txt))
            flag = ' || REGIONAL: ' + txt[:400]
        print('    %s code=%s bytes=%s sha=%s%s' % (ts, rr.status_code,
                                                    len(b), h, flag), flush=True)
        base = t.replace('%27', "'")
        open('recovered-assets/vsfan-reward-2026-10-09/%s__%s.html'
             % (base, ts), 'wb').write(b)