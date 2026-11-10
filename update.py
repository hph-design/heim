#!/usr/bin/env python3
"""Heim.fo – dagleg dagføring.

Les dagsins rádátu (meklarin.txt, betriheim.txt, skyn.txt, ogn.txt, skift.txt) úr RAW,
dagførir history.json (fyrsta dag sædd, prísbroytingar, myndaslóðir) og
byggir Heim.fo.html úr template.html.

Brúk:  python3 update.py RAW_DIR KIT_DIR OUT_DIR YYYY-MM-DD
  RAW_DIR  – mappa við dagsins rádátum
  KIT_DIR  – mappa við template.html (og history.json, um hon er til)
  OUT_DIR  – har history.json og Heim.fo.html verða skrivað
"""
import json, re, sys, os, urllib.parse
from datetime import date

RAW, KIT, OUT, TODAY = sys.argv[1:5]
SEED_DATE = "2026-11-07"   # fyrsti dagur við dagføring; ognir sæddar tá: "í minsta lagi"
SEED_DATES = {SEED_DATE, os.environ.get("HEIM_SEED", "")} - {""}  # HEIM_SEED: ein dagur, har nýggjar keldur verða sæddar
AGENT_SEED = {'skift': '2026-11-10'}   # fyrsti dagur hjá nýggjum meklara

AREA = {'Streymoy suður': 'Suðurstreymoy', 'Streymoy norð': 'Norðstreymoy'}
TOWN = {}
for a, ts in {
    'Suðurstreymoy': 'Hoyvík Kaldbak Tórshavn Argir Velbastaður Nólsoy Hestur Kirkjubøur Syðradalur Norðradalur',
    'Norðstreymoy': 'Vestmanna Leynar Kvívík Kollafjørður Hósvík Hvalvík Langasandur Streymnes Saksun Haldórsvík Tjørnuvík Signabøur Hvítanes Skælingur Stykkið',
    'Norðoyggjar': 'Hvannasund Klaksvík Kunoy Árnafjørður Mikladalur Viðareiði Svínoy Fugloy Haraldssund Húsar Norðdepil',
    'Eysturoy': 'Leirvík Strendur Norðragøta Elduvík Skála Glyvrar Syðrugøta Gøtugjógv Selatrað Oyndarfjørður Toftir Rituvík Oyri Oyrarbakki Norðskáli Saltangará Eiði Runavík Fuglafjørður Nes Æðuvík Gjógv Funningur Ljósá Søldarfjørður Lambi Lamba Kolbanargjógv Morskranes Hellur',
    'Vágar': 'Sandavágur Sørvágur Miðvágur Bøur Gásadalur Mykines',
    'Sandoy': 'Sandur Skopun Skálavík Húsavík Dalur Skúvoy',
    'Suðuroy': 'Trongisvágur Tvøroyri Sumba Vágur Froðba Fámjin Hov Porkeri Hvalba Øravík Nes Lopra Akrar Sandvík'}.items():
    for t in ts.split():
        TOWN.setdefault(t, a)
TOWN['Innan Glyvur'] = 'Eysturoy'
TOWN['Við Gjógv'] = 'Eysturoy'

def num(s):
    s = (s or '').strip()
    m = re.match(r'^(?:uml\.\s*)?([\d.]+)(?:,\d+)?$', s, re.I)
    if not m: return None
    v = int(m.group(1).replace('.', ''))
    return v or None

def guess(addr, size, plot):
    a = addr.lower()
    if 'íbúð' in a: return 'Íbúð'
    if a.startswith('matr') or (not size and plot): return 'Grundstykki'
    return 'Sethús'

def lines(name):
    p = os.path.join(RAW, name)
    if not os.path.exists(p): return []
    return [l for l in open(p, encoding='utf8').read().split('\n') if l.strip() and not l.startswith('#')]

L = []
# Meklarin: area|types|img|slug|built|address|city|rooms|plot|size|new|sold|openhouse|price|bid|newbid|validuntil|bidexpired|newprice
for i, l in enumerate(lines('meklarin.txt')):
    f = l.split('|') + [''] * 19
    area, types, img, slug, built, addr, town, rooms, plot, size, new, sold, openh, price, bid, newbid, valid, bidexp, newprice = f[:19]
    st = 'sold' if sold == '1' else 'bid' if (bid and bidexp != '1') else 'new' if new == '1' else 'price' if newprice == '1' else ''
    L.append(dict(agent='meklarin', url='https://www.meklarin.fo/ogn/' + slug, img='https://www.meklarin.fo/wp-content/uploads/' + img,
        type=types.split(',')[0].strip() or 'Sethús', address=addr, town=town, area=AREA.get(area, area), price=num(price),
        bid=num(bid), bidText=('galdandi til ' + valid) if st == 'bid' and valid else '', expired=bool(bid and bidexp == '1'),
        built=built.strip() or None, size=num(size), plot=num(plot), rooms=rooms.strip() or None, floors=None,
        status=st, open=openh, rank=i))
# Betri Heim: slug|img(path after /savn/, with query)|status|address|zip town|price|bid|built|size|plot|rooms|floors|openhouse
for i, l in enumerate(lines('betriheim.txt')):
    f = l.split('|') + [''] * 13
    slug, img, st, addr, ztown, price, bid, built, size, plot, rooms, floors, openh = f[:13]
    z, town = (ztown.split(' ', 1) + [''])[:2]
    sz, pl = num(size), num(plot)
    L.append(dict(agent='betriheim', url='https://www.betriheim.fo/heim-til-soelu/' + slug,
        img=('https://betriheim.cdn.fo/savn/' + img) if img else '',
        type=guess(addr, sz, pl), address=addr, town=town, zip=z, area=TOWN.get(town, ''), price=num(price), bid=num(bid), bidText='',
        expired=st == 'expired', built=built or None, size=sz, plot=pl, rooms=rooms or None, floors=floors or None,
        status='' if st == 'expired' else st, open=openh, rank=100 + i))
# Skyn: pid|imgpath|status|address|town|size|plot|rooms|floors|built|price|bid|validuntil|openhouse
for i, l in enumerate(lines('skyn.txt')):
    f = l.split('|') + [''] * 14
    pid, img, st, addr, town, size, plot, rooms, floors, built, price, bid, valid, openh = f[:14]
    sz, pl = num(size), num(plot)
    L.append(dict(agent='skyn', url='https://www.skyn.fo/default.aspx?id=212&ProductID=PROD' + pid,
        img=('https://www.skyn.fo/admin/public/getimage.ashx?Image=' + urllib.parse.quote('/Files/Images/Ognir/' + img) +
             '&Width=720&Height=496&Crop=6&format=webp&quality=75') if img else '',
        type=guess(addr, sz, pl), address=addr, town=town, area=TOWN.get(town, ''), price=num(price), bid=num(bid),
        bidText=('galdandi til ' + valid) if st == 'bid' and valid else '', expired=st == 'expired',
        built=(built if built not in ('', '0') else None), size=sz, plot=pl,
        rooms=(rooms if rooms not in ('', '0') else None), floors=(floors if floors not in ('', '0') else None),
        status={'expired': '', 'fixed': 'fixed'}.get(st, st), open=openh, rank=200 + i))
# Ogn.fo: id|img(path after /upload/)|type|title|town|price|size|rooms|floors|built|plot|status
for i, l in enumerate(lines('ogn.txt')):
    f = l.split('|') + [''] * 12
    pid, img, typ, title, town, price, size, rooms, floors, built, plot, st = f[:12]
    L.append(dict(agent='ogn', url='https://ogn.fo/properties/property/' + pid, img=('https://ogn.fo/upload/' + img) if img else '',
        type=typ or 'Annað', address=title, town=town, area=TOWN.get(town, ''), price=num(price), bid=None, bidText='', expired=False,
        built=built or None, size=num(size), plot=num(plot), rooms=rooms or None, floors=floors or None, status=st, open='', rank=50 + i))

# Skift: slug|img(path after /wp-content/uploads/)|status|address|town|area|size|plot|rooms|floors|built|price|bid|validuntil|openhouse
SKIFT_AREA = {'Norðurstreymoy': 'Norðstreymoy', 'Suðurstreymur': 'Suðurstreymoy', 'Suðurstrymoy': 'Suðurstreymoy'}
for i, l in enumerate(lines('skift.txt')):
    f = l.split('|') + [''] * 15
    slug, img, st, addr, town, area, size, plot, rooms, floors, built, price, bid, valid, openh = f[:15]
    sz, pl = num(size), num(plot)
    L.append(dict(agent='skift', url='https://www.skift.fo/properties/' + slug + '/',
        img=('https://www.skift.fo/wp-content/uploads/' + img) if img else '',
        type=guess(addr, sz, pl), address=addr, town=town, area=TOWN.get(town) or SKIFT_AREA.get(area, area), price=num(price), bid=num(bid),
        bidText=('galdandi til ' + valid) if st == 'bid' and valid else '', expired=st == 'expired',
        built=built or None, size=sz, plot=pl, rooms=rooms or None, floors=floors or None,
        status='' if st == 'expired' else st, open=openh, rank=300 + i))

# ---------- Søga ----------
hp = os.path.join(OUT, 'history.json')
if not os.path.exists(hp): hp = os.path.join(KIT, 'history.json')
H = json.load(open(hp, encoding='utf8')) if os.path.exists(hp) else {}

d0 = date.fromisoformat(TODAY)
seen_today = set()
for o in L:
    k = o['url']; seen_today.add(k)
    h = H.get(k)
    if h is None:
        h = H[k] = {'firstSeen': TODAY, 'seed': TODAY in SEED_DATES or TODAY == AGENT_SEED.get(o['agent']), 'prices': [], 'img': ''}
    h['lastSeen'] = TODAY
    h['address'] = o['address']
    if o['price'] and (not h['prices'] or h['prices'][-1][1] != o['price']):
        h['prices'].append([TODAY, o['price']])
    if o['img']: h['img'] = o['img']
    elif h.get('img'): o['img'] = h['img']           # goym myndaslóð, um hon ikki varð funnin í dag
    if o['status'] == 'sold' and not h.get('soldSeen'): h['soldSeen'] = TODAY
    # boð: goym hvørja nýggja boðsupphædd
    if o.get('bid') and not o.get('expired') and o['status'] != 'sold':
        bids = h.setdefault('bids', [])
        if not bids or bids[-1][1] != o['bid']:
            bids.append([TODAY, o['bid']])
        o['bidNewOn'] = bids[-1][0]
        o['bidSeed'] = bids[-1][0] in SEED_DATES or bids[-1][0] == AGENT_SEED.get(o['agent'])
        if len(bids) > 1: o['bidPrev'] = bids[-2][1]
    o['firstSeen'] = h['firstSeen']
    o['seed'] = h.get('seed', False)
    o['days'] = (d0 - date.fromisoformat(h['firstSeen'])).days
    ps = [p for _, p in h['prices']]
    if len(ps) > 1:
        o['priceFirst'] = ps[0]
        o['priceChange'] = ps[-1] - ps[0]
        o['priceChangedOn'] = h['prices'][-1][0]
for k, h in H.items():
    if k not in seen_today and not h.get('goneSince'):
        h['goneSince'] = TODAY
    elif k in seen_today and h.get('goneSince'):
        h['backOn'] = TODAY; h.pop('goneSince')
for o in L:
    if H[o['url']].get('backOn'): o['backOn'] = H[o['url']]['backOn']

for n, o in enumerate(L): o['id'] = n + 1
os.makedirs(OUT, exist_ok=True)
json.dump(H, open(os.path.join(OUT, 'history.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)

tpl = open(os.path.join(KIT, 'template.html'), encoding='utf8').read()
active = sum(1 for o in L if o['status'] != 'sold')
d = d0
months = ['jan.', 'feb.', 'mars', 'apr.', 'mai', 'juni', 'juli', 'aug.', 'sept.', 'okt.', 'nov.', 'des.']
html = (tpl.replace('__DATA__', json.dumps(L, ensure_ascii=False))
           .replace('__TODAY__', TODAY)
           .replace('__UPDATED__', f'{d.day}. {months[d.month-1]} {d.year}')
           .replace('__COUNT__', str(active)))
open(os.path.join(OUT, 'Heim.fo.html'), 'w', encoding='utf8').write(html)

from collections import Counter
new_today = [o['address'] for o in L if o['firstSeen'] == TODAY and not o['seed']]
newbids = [f"{o['address']}: {o['bid']:,}".replace(',', '.') for o in L if o.get('bidNewOn') == TODAY and not o.get('bidSeed')]
changed = [f"{o['address']}: {o['priceChange']:+,}".replace(',', '.') for o in L if o.get('priceChangedOn') == TODAY]
gone = [h['address'] for h in H.values() if h.get('goneSince') == TODAY]
print(json.dumps({'listings': len(L), 'active': active, 'perAgent': Counter(o['agent'] for o in L),
                  'newToday': new_today, 'priceChangesToday': changed, 'newBidsToday': newbids, 'goneToday': gone,
                  'missingArea': [o['address'] for o in L if not o['area']],
                  'missingImg': [o['url'] for o in L if not o['img']]}, ensure_ascii=False, indent=1))
