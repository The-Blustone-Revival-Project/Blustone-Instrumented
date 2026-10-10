import os
import re
import html as _h
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
D = 'recovered-assets/vsfan-reward-2026-10-09'
for f in sorted(os.listdir(D)):
    if not f.endswith('.html'):
        continue
    p = os.path.join(D, f)
    b = open(p, 'rb').read()
    s = b.decode('utf-8', 'replace')
    # MediaWiki: keep the content div, drop nav
    m = re.search(r'<div[^>]*class="[^"]*mw-parser-output[^"]*"[^>]*>(.*)'
                  r'<div[^>]*class="printfooter"', s, re.S)
    body = m.group(1) if m else s
    body = re.sub(r'<(script|style)\b.*?</\1>', ' ', body, flags=re.S | re.I)
    # keep table cell separators
    body = re.sub(r'</t[dh]>', ' | ', body, flags=re.I)
    body = re.sub(r'</tr>', '\n', body, flags=re.I)
    body = re.sub(r'<br\s*/?>', ' / ', body, flags=re.I)
    body = re.sub(r'<[^>]*>', ' ', body)
    body = _h.unescape(body)
    body = re.sub(r'[ \t\xa0]+', ' ', body)
    body = re.sub(r'\n\s*\n+', '\n', body)
    # drop the site-wide nav block that MediaWiki repeats on every page
    cut = re.search(r'\n\s*\|?\s*NPCs\s*\|', body)
    if cut:
        body = body[:cut.start()] + '\n[NAV BLOCK REMOVED]\n'
    out = os.path.join(D, f[:-5] + '.txt')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(body.strip())
    print('%-34s html=%7d txt=%7d' % (f, len(b), len(body)))