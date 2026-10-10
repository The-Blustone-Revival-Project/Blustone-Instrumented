#!/usr/bin/env python3
"""Fetch selected vsfan.net wiki pages from the Wayback Machine.

GUARD compliance:
  * http:// ONLY (https is refused on this host)
  * ONE requests.Session per thread (reused, keep-alive)
  * low worker count (archive.org refuses at 8)
  * positive control run FIRST; every zero is uninterpretable if it fails
  * hash every body; reject the "Temporarily Offline" page
"""
import argparse
import hashlib
import os
import re
import sys
import threading
import time

import requests
from requests.adapters import HTTPAdapter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CONTROL = ('http://web.archive.org/web/2021/'
           'https://bs.visualshower.com/files/attach/images/75605/303/534/001/'
           '725a8e175454a533e96dac68fc5fdb49.jpg')

OUT = 'recovered-assets/vsfan-reward-2026-10-09'
_local = threading.local()


def session():
    s = getattr(_local, 's', None)
    if s is None:
        s = requests.Session()
        s.headers.update({'User-Agent': 'blustone-reward-research/1.0 '
                                      '(read-only archive fetch)'})
        ad = HTTPAdapter(pool_connections=4, pool_maxsize=4)
        s.mount('http://', ad)
        _local.s = s
    return s


def get(url, tries=4):
    for i in range(tries):
        try:
            r = session().get(url, timeout=60)
            return r.status_code, r.content
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    return 0, b''


def control():
    code, body = get(CONTROL)
    sig = body[:4].hex() if body else '--'
    ok = (code == 200 and len(body) == 57414 and sig.startswith('ffd8ffe1'))
    print('POSITIVE CONTROL: code=%s size=%s sig=%s -> %s'
          % (code, len(body), sig, 'PASS' if ok else 'FAIL'), flush=True)
    return ok


PAGES = {
    'Expedition_Area': '20190826070239',
    'Abyss_Area': '20190826081454',
    'Fight_Club': '20190826065802',
    'Fight_Club_Shop': '20190821024117',
    'Hunter_Supply_Station': '20190821024536',
    'Hunter_Supply_Office': '20190821011235',
    'Hunter_Shop': '20190826073011',
    'List_of_Blustone_Items': '20190821024134',
    'List_of_Blustone_Stories': '20190821034342',
    'Lottery_Mouse': '20190826065659',
    'Suspicious_Shop': '20190821024010',
    'Midgard_Snowfields': '20190821033703',
    'Midgard_Ice_Zone': '20190826065711',
    'Guide_to_Blustone': '20190923072038',
    'Hidden_Functions': '20190923065811',
    'Challenge': '20190923070045',
    'Hunter_Gym': '20190826075402',
    'Post_Office': '20190826074307',
    'Main_Page': '20170825063314',
    'Midgard': '20190821033429',
    'Rotation_Area': '20190821024755',
    'Hunters%27_Drop_Rate': '20190821010227',
    'Blustone': '20190821004409',
    'Hunter': '20190826072145',
    'Hunters': '20190821012252',
    'Pet_guidebook': '20190923075956',
    # --- batch 2: reward-bearing pages named in the earlier ledger ---
    'Aircraft_Entrance': '20190826081220',
    'Ornithopter_Platform': '20190826082800',
    'Blood_Red_Canyon': '20190826065800',
    'Blue_Wing_Valley': '20190821035109',
    'Burning_Forest': '20190821034040',
    'Crescent_Hill': '20190821035813',
    'Crimson_Chasm': '20190826081047',
    'Emerald_Canyon': '20190821031309',
    'Giant%27s_Shelter': '20190826073039',
    'Gray_Valley': '20190826075814',
    'Mt._Black_Rock': '20190821005017',
    'Non-melting_Forest': '20190821034028',
    'North_Highlands': '20190821031719',
    'Silent_Forest': '20190821031811',
    'Peppermint': '20190923075326',
    'Cryogenic_Abyss': '20190821024057',
    'Electric_Abyss': '20190821004044',
    'Golden_Abyss': '20190821025613',
    'Halloween_Abyss': '20190821025827',
    'Hunters%27_Drop_Rate_2': '20190923065811',
    'Jewels': '20190826071600',
    'Items': '20190821024134',
    'Tribes': '20190826065800',
    'Purchase': '20190821011108',
    'Awake': '20190920181814',
    'Certification': '20190920181814',
    'Fate': '20190826065800',
    'Veteran': '20190821011200',
    'Veteran_Status': '20190821011200',
    'GvG': '20190821000000',
    'Guild': '20190821000000',
    'Mirage_Ruins': '20190821000000',
    'Mirage_Ruins_Shop': '20190821000000',
    'List_of_Blustone_Monsters': '20190923070011',
    'Patch_1.1.7.0_(Blustone)': '20190821013731',
    'Patch_1.1.6.0_(Blustone)': '20190821010464',
    'Patch_1.1.5.0_(Blustone)': '20190821011813',
    'Patch_1.1.4.0_(Blustone)': '20190821013551',
    'Patch_1.1.3.0_(Blustone)': '20190821017423',
    'Patch_1.1.2.0_(Blustone)': '20190923071523',
    'Patch_1.0.8.0_(Blustone)': '20190821004145',
    'Patch_1.0.7.3_(Blustone)': '20190923071803',
    'Patch_1.0.7.0_(Blustone)': '20190821012448',
    'Patch_1.0.6.1_(Blustone)': '20190923070153',
    'Patch_1.0.5.0_(Blustone)': '20190821010755',
    'Patch_1.0.4.0_(Blustone)': '20190821010709',
    'Patch_1.0.3.0_(Blustone)': '20190821010864',
    'Patch_1.0.2.0_(Blustone)': '20190923080834',
    'Patch_1.0.1.1_(Blustone)': '20190821012956',
    'Patch_1.0.1.0_(Blustone)': '20190821011208',
    'Patch_1.0.0.3_(Blustone)': '20190821012352',
    'Patch_1.0.0_(Blustone)': '20190920184555',
    # --- independent re-captures of the two decisive pages, to show the
    # --- statement survived edits rather than being one lucky revision
    'Expedition_Area_c2': '20191020021916',
    'Expedition_Area_c3': '20191214021916',
    'List_of_Blustone_Items_c2': '20191214021916',
    'Guide_to_Blustone_c2': '20191214021916',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args()

    if not control():
        print('ABORT: control failed; every zero below would be meaningless.')
        return 2

    os.makedirs(OUT, exist_ok=True)
    ts = threading.local()
    idx = list(PAGES.items())
    lock = threading.Lock()
    results = {}
    done = [0]

    def work(item):
        name, stamp = item
        url = ('http://web.archive.org/web/%sid_/'
               'https://vsfan.net/wiki/%s' % (stamp, name.replace(' ', '_')))
        code, body = get(url, tries=5)
        h = hashlib.sha256(body).hexdigest() if body else ''
        text = ''
        bad = (b'Temporarily Offline' in body[:4000]
               or b'not archived' in body[:4000]
               or b'Got an HTTP 302' in body[:4000])
        if code == 200 and body and not bad:
            p = os.path.join(OUT, name + '.html')
            with open(p, 'wb') as fh:
                fh.write(body)
            try:
                import html as _h
                import html.parser  # noqa
                txt = re.sub(r'<(script|style)\b.*?</\1>', ' ', body.decode(
                    'utf-8', 'replace'), flags=re.S | re.I)
                txt = re.sub(r'<[^>]*>', ' ', txt)
                txt = _h.unescape(txt)
                txt = re.sub(r'\s+', ' ', txt)
                text = txt
                with open(os.path.join(OUT, name + '.txt'), 'w',
                          encoding='utf-8') as fh:
                    fh.write(txt)
            except Exception:
                pass
        with lock:
            done[0] += 1
            results[name] = (code, len(body), h[:16], len(text))
            print('[%2d/%2d] %-26s code=%s bytes=%s sha=%s text=%s'
                  % (done[0], len(idx), name, code, len(body), h[:16],
                     len(text)), flush=True)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, idx))

    print('\nSUMMARY')
    for k, v in results.items():
        print('%-26s %s' % (k, v))
    return 0


if __name__ == '__main__':
    sys.exit(main())