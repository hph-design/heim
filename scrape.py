#!/usr/bin/env python3
"""Heim.fo – heintar ognir frá Meklarin, Betri Heim, Skyn, Ogn.fo og Skift.

Skrivar raw/meklarin.txt, raw/betriheim.txt, raw/skyn.txt, raw/ogn.txt og raw/skift.txt
í sama sniði sum RUN.md lýsir, so update.py kann brúka tær óbroyttar.
Um ein kelda svíkur, verður gamla fílan standandi, og feilurin verður
skrivaður í raw/status.json.

Brúk:  python3 scrape.py RAW_DIR
"""
import html, json, os, re, sys, time, urllib.parse
import requests
from bs4 import BeautifulSoup

RAW = sys.argv[1] if len(sys.argv) > 1 else 'raw'
os.makedirs(RAW, exist_ok=True)
S = requests.Session()
S.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
    'Accept-Language': 'fo,da;q=0.9,en;q=0.8',
})

def get(url, **kw):
    for i in range(3):
        try:
            r = S.get(url, timeout=30, **kw)
            r.raise_for_status()
            return r
        except Exception:
            if i == 2: raise
            time.sleep(3)

def clean(s):
    s = html.unescape(str(s if s is not None else ''))
    return re.sub(r'\s+', ' ', s.replace('|', '/')).strip()

def digits(s):
    m = re.search(r'\d[\d.]*', s or '')
    return m.group(0).replace('.', '') if m else ''

def txt(el):
    return clean(el.get_text(' ')) if el else ''

def truthy(v):
    return v is True or str(v).strip().lower() in ('true', '1', 'yes')


# ---------- Meklarin ----------
def js_string(raw):
    """Afkoda ein JS-streng ('…'), sum inniheldur JSON."""
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c == '\\' and i + 1 < len(raw):
            n = raw[i + 1]
            if n == "'": out.append("'")
            else: out.append(c + n)
            i += 2; continue
        out.append('\\"' if c == '"' else c)
        i += 1
    return json.loads('"' + ''.join(out) + '"')

def meklarin():
    page = get('https://www.meklarin.fo/').text
    m = re.search(r"ALL_PROPERTIES\s*=\s*JSON\.parse\('((?:\\.|[^'\\])*)'\)", page, re.S)
    if not m: raise RuntimeError('ALL_PROPERTIES ikki funnið')
    props = json.loads(js_string(m.group(1)))
    rows = []
    for p in props:
        rows.append('|'.join(clean(x) for x in [
            p.get('areas'), p.get('types'),
            (p.get('featured_image') or '').replace('https://www.meklarin.fo/wp-content/uploads/', ''),
            (p.get('permalink') or '').replace('https://www.meklarin.fo/ogn/', ''),
            p.get('build'), p.get('address'), p.get('city'), p.get('bedrooms'),
            p.get('house_area'), p.get('area_size'),
            1 if truthy(p.get('new')) else 0, 1 if truthy(p.get('sold')) else 0,
            p.get('open_house_start_date') if truthy(p.get('open_house')) else '',
            p.get('price'), p.get('bid'), 1 if truthy(p.get('new_bid')) else 0,
            p.get('bid_valid_until'), 1 if truthy(p.get('bid_expired')) else 0, p.get('new_price')]))
    return rows


# ---------- Betri Heim ----------
BH_TAG = {'nýggj-ogn': 'new', 'nýtt-heim': 'new', 'nýtt-boð': 'bid', 'selt': 'sold', 'útgingið-boð': 'expired'}

def betriheim():
    arts, seen, skip = [], set(), 0
    for _ in range(30):
        j = get('https://www.betriheim.fo/api/properties/filter',
                params={'area': '', 'type': '', 'skip': skip}).json()
        soup = BeautifulSoup(j.get('html', ''), 'html.parser')
        page = soup.select('article')
        arts += page
        if not j.get('hasMore') or not page: break
        skip += len(page)
    rows = []
    for a in arts:
        link = a.select_one('a[href*="/heim-til-soelu/"]')
        if not link: continue
        slug = link['href'].split('/heim-til-soelu/')[1].split('?')[0].split('#')[0]
        if slug in seen: continue
        seen.add(slug)
        img = a.select_one('picture img') or a.select_one('img')
        src = img.get('src', '') if img else ''
        src = src.replace('https://betriheim.cdn.fo/savn/', '') if 'betriheim.cdn.fo/savn/' in src else ''
        tag = a.select_one('.tag')
        st = ''
        if tag:
            cls = [c for c in tag.get('class', []) if c != 'tag']
            st = BH_TAG.get(cls[0] if cls else '', '')
            if not st:
                t = txt(tag).lower()
                st = 'sold' if 'selt' in t else 'bid' if 'boð' in t and 'útgingið' not in t else 'expired' if 'útgingið' in t else 'new' if 'nýggj' in t or 'nýtt' in t else ''
        offer = a.select_one('.latest-offer')
        valid = a.select_one('.valid')
        if not st and offer: st = 'bid' if valid else 'expired'
        addr_el = a.select_one('address')
        parts = [clean(x) for x in addr_el.get_text('\n').split('\n') if clean(x)] if addr_el else []
        addr = parts[0] if parts else ''
        ztown = parts[1] if len(parts) > 1 else ''
        f = lambda sel: digits(txt(a.select_one(sel)).split(' ', 1)[-1]) if a.select_one(sel) else ''
        oh = a.select_one('.open-house')
        rows.append('|'.join([slug, src, st, addr, ztown, digits(txt(a.select_one('.price'))),
                              digits(txt(offer)), f('.facts .date'), f('.facts .building-size'), f('.facts .land-size'),
                              f('.facts .rooms'), f('.facts .floors'), txt(oh)]))
    return rows


# ---------- Skyn ----------
SKYN_BADGE = {'nyttbod': 'bid', 'nyggjogn': 'new', 'seld': 'sold', 'nyggjurprisur': 'price', 'fasturprisur': 'fixed'}
SKYN_ICON = {'icon-size.png': 'size', 'icon-ground-size.png': 'plot', 'icon-bedrooms.png': 'rooms',
             'icon-floors.png': 'floors', 'icon-buildyear.png': 'built'}

def skyn():
    soup = BeautifulSoup(get('https://www.skyn.fo/ognir-til-soelu').text, 'html.parser')
    rows, seen = [], set()
    for a in soup.select('a.ogn-card'):
        m = re.search(r'ProductID=PROD(\d+)', a.get('href', ''))
        if not m or m.group(1) in seen: continue
        pid = m.group(1); seen.add(pid)
        img = a.select_one('.ogn-thumb img')
        p = urllib.parse.unquote(html.unescape(img.get('src', ''))) if img else ''
        im = re.search(r'/Files/Images/Ognir/([^&]+?)(&|$)', p)
        st = ''
        for b in a.select('.ogn-badge'):
            for c in b.get('class', []):
                if c in SKYN_BADGE and not st: st = SKYN_BADGE[c]
        offer = a.select_one('.ogn-offer')
        expired = bool(offer and 'expired' in offer.get('class', []))
        if expired and st in ('', 'bid'): st = 'expired'
        if not st and offer and not expired: st = 'bid'
        v = {}
        for ic in a.select('.ogn-icon'):
            i = ic.select_one('img')
            k = SKYN_ICON.get((i.get('src', '') if i else '').split('/')[-1])
            if k: v[k] = digits(txt(ic.select_one('span') or ic))
        valid = re.sub(r'^Galdandi til\s*', '', txt(a.select_one('.ogn-validto')))
        rows.append('|'.join([pid, im.group(1) if im else '', st, txt(a.select_one('.ogn-headline')), txt(a.select_one('.ogn-city')),
                              v.get('size', ''), v.get('plot', ''), v.get('rooms', ''), v.get('floors', ''), v.get('built', ''),
                              digits(txt(a.select_one('.ogn-price-amount'))), digits(txt(a.select_one('.ogn-offer-amount'))),
                              valid, txt(a.select_one('.ogn-opidhus-text'))]))
    return rows


# ---------- Ogn.fo ----------
def ogn_type(title):
    t = title.lower()
    if 'grund' in t or 'økir' in t or t.startswith('øki'): return 'Grundstykki'
    if 'íbúð' in t: return 'Íbúð'
    if 'vinnu' in t or 'konkurs' in t or 'bygningur' in t or 'rakstur' in t: return 'Vinnubygningur'
    return 'Sethús'

def ogn():
    soup = BeautifulSoup(get('https://ogn.fo/properties').text, 'html.parser')
    rows, seen = [], set()
    for a in soup.select('a[href*="/properties/property/"]'):
        pid = a['href'].rstrip('/').split('/')[-1]
        if pid in seen: continue
        seen.add(pid)
        img = a.select_one('img')
        src = img.get('src', '') if img else ''
        src = re.sub(r'^(https://ogn\.fo)?/upload/', '', src) if '/upload/' in src else ''
        ic = lambda k: (lambda t: '' if t in ('-', '') else digits(t))(txt(a.select_one('.properties--icon--' + k)))
        title = txt(a.select_one('.properties--title'))
        rows.append('|'.join([pid, src, ogn_type(title), title, txt(a.select_one('.properties--address')),
                              digits(txt(a.select_one('.properties--price-suggestion'))),
                              ic('size'), ic('rooms'), ic('stories'), ic('year'), ic('land-size'), '']))
    return rows


# ---------- Skift ----------
def skift():
    soup = BeautifulSoup(get('https://www.skift.fo/').text, 'html.parser')
    rows, seen = [], set()
    num = lambda t: re.sub(r'\D', '', re.sub(r'm\s*2|m²', '', t or ''))
    for a in soup.select('a.property-card'):
        slug = a.get('href', '').split('/properties/')[-1].strip('/')
        if not slug or slug in seen: continue
        seen.add(slug)
        st_txt = ','.join(txt(e).lower() for e in a.select('.property-card--status'))
        if 'selt' in st_txt or 'seld' in st_txt: continue          # seldar ognir verða ikki tiknar við
        img = a.select_one('.property-card--image-container img')
        src = (img.get('data-src') or img.get('src') or '') if img else ''
        src = '' if src.startswith('data:') else src.replace('https://www.skift.fo/wp-content/uploads/', '').split('?')[0]
        info = a.select_one('.property-card--text-info')
        h = txt(info.select_one('h5') if info else None) or (txt(info).split('  ')[0] if info else '')
        parts = [x.strip() for x in h.split(',')]
        town = parts.pop() if len(parts) > 1 else ''
        area = txt(info.select_one('p')) if info else ''
        f = {}
        for e in a.select('.property-card--size'):
            i = e.select_one('img')
            k = ((i.get('data-src') or i.get('src') or '') if i else '').split('/')[-1].split('?')[0].replace('icon-', '').replace('.svg', '')
            f[k] = txt(e)
        price = bid = valid = ''
        for r in a.select('.property-card--price-row'):
            t = txt(r)
            if re.search(r'Seinasta boð', t, re.I): bid = num(t.replace(',- kr.', ''))
            elif re.search(r'Galdandi til', t, re.I): valid = re.sub(r'(?i)Galdandi til:?\s*', '', t).strip()
            elif re.search(r'Prísuppskot', t, re.I): price = num(t.replace(',- kr.', ''))
        st = 'bid' if bid else 'new' if ('nýtt' in st_txt or 'nýggj' in st_txt) else ''
        rows.append('|'.join(clean(x) for x in [slug, src, st, ', '.join(parts), town, area, num(f.get('building-size')), num(f.get('plot-size')),
                              f.get('rooms', ''), f.get('floors', ''), f.get('build-year', ''), price, bid, valid,
                              'opið hús' if 'opið hús' in st_txt else '']))
    return rows


status = {}
for name, fn, minimum in [('meklarin', meklarin, 5), ('betriheim', betriheim, 5), ('skyn', skyn, 5), ('ogn', ogn, 1), ('skift', skift, 1)]:
    try:
        rows = fn()
        if len(rows) < minimum: raise RuntimeError(f'bert {len(rows)} ognir')
        open(os.path.join(RAW, name + '.txt'), 'w', encoding='utf8').write('\n'.join(rows) + '\n')
        status[name] = {'ok': True, 'count': len(rows)}
    except Exception as e:
        status[name] = {'ok': False, 'error': f'{type(e).__name__}: {e}'[:300]}
json.dump(status, open(os.path.join(RAW, 'status.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(json.dumps(status, ensure_ascii=False, indent=1))
if not any(s['ok'] for s in status.values()):
    sys.exit('Ongin kelda riggaði')
