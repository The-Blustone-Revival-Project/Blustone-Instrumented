#!/usr/bin/env python3
"""Single low-cost probe of the archive: is it responding at all right now?

Used to decide whether a further fetch pass is worth attempting. One request
per invocation, short timeout, so it cannot add meaningful load.
"""
import io
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TARGETS = {
    "control": "http://web.archive.org/web/2021/https://bs.visualshower.com/files/attach/images/75605/303/534/001/725a8e175454a533e96dac68fc5fdb49.jpg",
    "192349": "http://web.archive.org/web/20180215142507/http://bs.visualshower.com/index.php?mid=forum_en&document_srl=192349&l=en",
    "list1": "http://web.archive.org/web/20190819231953/https://bs.visualshower.com/index.php?mid=forum_en&l=en&page=108&l=en&sort_index=readed_count&order_type=desc",
}

name = sys.argv[1] if len(sys.argv) > 1 else "control"
url = TARGETS[name]
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 blustone-research/1.0"})
t0 = time.time()
try:
    r = s.get(url, timeout=45)
    dt = time.time() - t0
    b = r.content or b""
    print(f"{name}: status={r.status_code} bytes={len(b)} elapsed={dt:.1f}s sig={b[:8].hex()}")
except Exception as exc:  # noqa: BLE001
    dt = time.time() - t0
    print(f"{name}: TRANSPORT FAILURE ({type(exc).__name__}) elapsed={dt:.1f}s -> 000")
