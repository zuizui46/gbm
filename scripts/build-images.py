#!/usr/bin/env python3
"""Build the gbm photo library: real photographs under CC0 / Public Domain Mark only, for video backgrounds and
podcast covers. Writes images/<collection>/<id>.jpg (+ .thumb.webp), images.json and CREDITS-IMAGES.md.

Source: the Openverse API (api.openverse.org) — only `license=cc0,pdm`, `category=photograph`, from StockSnap (all
CC0), Flickr and Wikimedia Commons. CC0 / PDM need no credit; the author and page are still listed for courtesy.
Unsplash / Pexels / Pixabay are NOT copied in: their licences forbid compiling their photos into a similar library.
They are listed in `images.json › sources` as places where people can look for more themselves.

Files are resized (long edge ≤ 2400 for backgrounds, a 1400 px centre square for covers) and re-encoded — allowed by
CC0 / PDM. EXIF is dropped.

Usage: python3 scripts/build-images.py              # fetch what is missing, rebuild images.json + CREDITS-IMAGES.md
       python3 scripts/build-images.py --dry-run    # only print the selection
       python3 scripts/build-images.py --sheets DIR # also write one contact sheet per collection into DIR (review)
       python3 scripts/build-images.py --themes <themes.ts> --theme-photos 6   # Kat theme photos: main + 5 variants
"""
import hashlib, io, json, os, re, subprocess, sys, time, unicodedata, urllib.parse

from PIL import Image, ImageDraw, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = 'https://raw.githubusercontent.com/zuizui46/gbm/main/'
CDN = 'https://cdn.jsdelivr.net/gh/zuizui46/gbm@main/'
UA = 'gbm-library-builder/1.0'
DRY = '--dry-run' in sys.argv
SHEETS = sys.argv[sys.argv.index('--sheets') + 1] if '--sheets' in sys.argv else None
CACHE = os.path.join(ROOT, '.cache', 'openverse')

LICENSES = {
    'CC0-1.0': {'name': 'Creative Commons Zero 1.0 (Public Domain Dedication)', 'url': 'https://creativecommons.org/publicdomain/zero/1.0/', 'attribution': False, 'commercial': True, 'derivatives': True},
    'PDM-1.0': {'name': 'Public Domain Mark 1.0', 'url': 'https://creativecommons.org/publicdomain/mark/1.0/', 'attribution': False, 'commercial': True, 'derivatives': True},
}
OV_LICENSE = {'cc0': 'CC0-1.0', 'pdm': 'PDM-1.0'}

# Places to look for more (shown to people in the app). `inLibrary`: photos of that site are in this library.
SOURCES = [
    {'id': 'stocksnap', 'name': 'StockSnap.io', 'url': 'https://stocksnap.io', 'search': 'https://stocksnap.io/search/{q}', 'license': 'CC0 — free, no credit needed', 'inLibrary': True},
    {'id': 'openverse', 'name': 'Openverse', 'url': 'https://openverse.org', 'search': 'https://openverse.org/search/image?q={q}&license=cc0,pdm', 'license': 'CC0 / public domain filter on', 'inLibrary': True},
    {'id': 'wikimedia', 'name': 'Wikimedia Commons', 'url': 'https://commons.wikimedia.org', 'search': 'https://commons.wikimedia.org/w/index.php?search={q}&title=Special:MediaSearch&type=image', 'license': 'mixed — check each photo', 'inLibrary': True},
    {'id': 'unsplash', 'name': 'Unsplash', 'url': 'https://unsplash.com', 'search': 'https://unsplash.com/s/photos/{q}', 'license': 'Unsplash License — free to use in your videos', 'inLibrary': False},
    {'id': 'pexels', 'name': 'Pexels', 'url': 'https://www.pexels.com', 'search': 'https://www.pexels.com/search/{q}/', 'license': 'Pexels License — free to use in your videos', 'inLibrary': False},
    {'id': 'pixabay', 'name': 'Pixabay', 'url': 'https://pixabay.com', 'search': 'https://pixabay.com/images/search/{q}/', 'license': 'Pixabay Content License — free to use in your videos', 'inLibrary': False},
]

# collection → kind, label, how many, queries (searched in order until full)
COLLECTIONS = [
    # backgrounds (wide photos; vertical videos crop the middle)
    ('nature', 'background', 'Nature', 16, ['forest', 'mountain lake', 'waterfall', 'meadow', 'green hills', 'misty forest']),
    ('sea', 'background', 'Sea & beach', 12, ['ocean waves', 'beach', 'sea sunset', 'coast rocks']),
    ('sky', 'background', 'Sky & night', 12, ['sunset sky', 'clouds', 'night sky stars', 'milky way']),
    ('city', 'background', 'City', 14, ['city night', 'skyline', 'street', 'architecture', 'city lights']),
    ('people', 'background', 'People', 14, ['people walking', 'friends', 'crowd', 'people working', 'family', 'woman reading']),
    ('cozy', 'background', 'Cozy indoors', 12, ['coffee shop', 'library books', 'desk workspace', 'living room', 'cafe interior']),
    ('seasons', 'background', 'Seasons', 12, ['autumn leaves', 'snow winter', 'spring blossom', 'summer field']),
    ('travel', 'background', 'Travel', 12, ['road trip', 'travel', 'temple', 'old town', 'bridge']),
    ('texture', 'background', 'Textures', 12, ['wood texture', 'paper texture', 'concrete wall', 'marble', 'fabric texture']),
    ('abstract', 'background', 'Light & blur', 12, ['bokeh', 'light abstract', 'neon', 'smoke', 'blurred lights']),
    # covers (square crop from the centre)
    ('studio', 'cover', 'Mic & studio', 12, ['microphone', 'headphones', 'recording studio', 'radio', 'vinyl record']),
    ('portrait', 'cover', 'Portraits', 14, ['portrait woman', 'portrait man', 'smiling woman', 'smiling man', 'person portrait']),
    ('topics', 'cover', 'Topics', 16, ['books', 'coffee cup', 'laptop', 'guitar', 'camera', 'plant', 'food', 'running']),
    ('minimal', 'cover', 'Minimal', 12, ['minimal', 'pastel', 'flower closeup', 'leaf closeup', 'sand texture']),
    # occasions: real photos instead of drawn clip-art (Kast draws a tree, a pumpkin, a lantern…)
    ('festive', 'cover', 'Festive', 16, ['christmas lights', 'christmas tree', 'lantern', 'fireworks', 'gift box', 'pumpkin', 'candles', 'heart']),
    ('school', 'cover', 'School', 12, ['school', 'chalkboard', 'notebook pencil', 'student', 'classroom']),
]

# Theme photos (Kat themes, decision 2026-11-20-kast-themes): one wide photo per theme, tagged `theme: <id>` in
# images.json. The list is read from Kat's themes.ts (id + search words) so the two never drift apart; pass its path
# with --themes. Each theme takes the first acceptable result of its words.
THEMES_SRC = sys.argv[sys.argv.index('--themes') + 1] if '--themes' in sys.argv else None
# photos per theme: the first is the theme's main photo, the rest its variants (decision 2026-11-20-quick-themes)
THEME_PHOTOS = int(sys.argv[sys.argv.index('--theme-photos') + 1]) if '--theme-photos' in sys.argv else 1
# themes whose search words run out of good photos (contact sheets 20/11): no refill past this many — their variants
# fill up with other layouts and colours instead
THEME_PHOTO_CAP = {
    'mothers-day': 5,
    'seoul-vibes': 5,
    'buddha-birthday': 5,
    'forest-fables': 5,
    'teachers-day': 3,
    'reindeer-night': 5,
    'family-table': 4,
    'math-play': 4,
    'chalk-and-board': 5,
    'purple-ink': 2,
    'simple-thank-you': 4,
    'apple-pie': 4,
    'mid-autumn': 5,
    'national-day': 5,
    'floating-lanterns': 2,
    'snowy-village': 5,
    'gingerbread': 4,
    'prayer-candle': 2,
    'dove-of-peace': 5,
    'stained-glass': 4,
    'loaves-and-fishes': 5,
    'pink-lotus': 5,
    'dharma-wheel': 4
}

def theme_rows():
    if not THEMES_SRC:
        return []
    src = open(THEMES_SRC).read()
    return re.findall(r"""^\s+\['([a-z0-9-]+)', (?:'[^']*'|"[^"]*"), '([^']+)'""", src, re.M)

# ids taken out after looking at the contact sheets (wrong subject, text / logo in the photo, people too small, weak photo)
EXCLUDE = {
    # fifth pass (20/11)
    'theme-seoul-vibes-d24fdd',
    'theme-mothers-day-75784e',
    # fourth pass (20/11)
    'theme-teachers-day-858774',
    'theme-teachers-day-4707a5',
    'theme-floating-lanterns-833757',
    'theme-floating-lanterns-994c54',
    'theme-floating-lanterns-414dba',
    'theme-forest-fables-e5ba7f',
    'theme-buddha-birthday-e74dce',
    # third pass (20/11)
    'theme-family-table-0ef491',
    'theme-family-table-af3e1a',
    'theme-reindeer-night-e5ba7f',
    'theme-teachers-day-75784e',
    # second pass (20/11): replacements that still miss
    'theme-math-play-da4816',
    'theme-math-play-d99071',
    'theme-chalk-and-board-4fb7a3',
    'theme-purple-ink-333628',
    'theme-purple-ink-e178e9',
    'theme-purple-ink-ced46c',
    'theme-purple-ink-f71dff',
    'theme-simple-thank-you-f4c422',
    'theme-simple-thank-you-d2a43b',
    'theme-apple-pie-60f303',
    'theme-apple-pie-ee752d',
    'theme-mid-autumn-be2529',
    'theme-national-day-5c6017',
    'theme-floating-lanterns-22d02f',
    'theme-snowy-village-d2c440',
    'theme-gingerbread-24f000',
    'theme-gingerbread-1b4d27',
    'theme-prayer-candle-812d4f',
    'theme-prayer-candle-05be1d',
    'theme-dove-of-peace-09122a',
    'theme-stained-glass-a8a18a',
    'theme-stained-glass-37634b',
    'theme-loaves-and-fishes-65de5c',
    'theme-pink-lotus-cafba3',
    'theme-dharma-wheel-721eb9',
    'theme-dharma-wheel-46c811',
    # theme variant photos that do not fit (contact sheets 20/11): text or logos, wrong subject, people out of place, doubles
    'theme-london-corner-95b4c7',
    'theme-london-corner-41b2da',
    'theme-london-corner-0bf278',
    'theme-lofi-study-night-d24fdd',
    'theme-travel-phrases-4ef5b9',
    'theme-travel-phrases-ae2f32',
    'theme-recess-time-1f6eb2',
    'theme-math-play-bbc804',
    'theme-math-play-6e244d',
    'theme-math-play-e91d93',
    'theme-math-play-be1684',
    'theme-chalk-and-board-8d911f',
    'theme-chalk-and-board-31b68e',
    'theme-letter-to-a-teacher-bb5a1a',
    'theme-purple-ink-9966a0',
    'theme-purple-ink-cb66ef',
    'theme-purple-ink-eb3077',
    'theme-purple-ink-f28cce',
    'theme-simple-thank-you-d8c499',
    'theme-simple-thank-you-51d74e',
    'theme-rice-field-sunset-3c3b7f',
    'theme-rice-field-sunset-17161b',
    'theme-apple-pie-ce342a',
    'theme-apple-pie-599bbd',
    'theme-apple-pie-1e3676',
    'theme-apple-pie-348e52',
    'theme-mid-autumn-22d02f',
    'theme-national-day-f33c94',
    'theme-national-day-e0cc19',
    'theme-floating-lanterns-13ffdb',
    'theme-floating-lanterns-f740b9',
    'theme-first-day-of-school-ee9dbd',
    'theme-snowy-village-5c3016',
    'theme-gingerbread-f16a05',
    'theme-carols-812d4f',
    'theme-carols-05be1d',
    'theme-cozy-christmas-1b7a9f',
    'theme-year-end-thanks-5c6017',
    'theme-year-end-thanks-d7c144',
    'theme-once-upon-a-time-629b13',
    'theme-midnight-mysteries-e39377',
    'theme-midnight-mysteries-e5ba7f',
    'theme-romance-novel-c26a78',
    'theme-prayer-candle-06933b',
    'theme-prayer-candle-a37e68',
    'theme-dove-of-peace-789a3b',
    'theme-dove-of-peace-dfd62e',
    'theme-stained-glass-2e23ff',
    'theme-stained-glass-33524b',
    'theme-advent-wreath-0aecfa',
    'theme-loaves-and-fishes-a40981',
    'theme-loaves-and-fishes-f7eade',
    'theme-daily-reflection-9add05',
    'theme-pink-lotus-1f161b',
    'theme-pink-lotus-1dda39',
    'theme-pink-lotus-56f460',
    'theme-temple-bell-0bd0a5',
    'theme-lotus-lanterns-7592f6',
    'theme-lotus-lanterns-2ffeba',
    'theme-dharma-wheel-fe7c5a',
    'theme-dharma-wheel-a7d07c',
    'theme-zen-tea-214d13',
    'theme-morning-chant-b0aa74',
    'theme-lunar-new-year-af0cc5',          # a couple dancing
    'theme-lunar-new-year-a1fe48',          # a Valentine card
    'theme-chalk-and-board-be1684',         # Christmas again
    'theme-lunar-new-year-b9b5a5',          # a stall keeper, signs
    'theme-chalk-and-board-f7b914',         # a café menu, text all over
    'theme-lunar-new-year-13ffdb',          # a dark lamp on a white wall
    'theme-detective-files-e1df71',         # brand logo
    'theme-chalk-and-board-e91d93',         # a Christmas frame, not a classroom
    'theme-lunar-new-year-be2529',          # a concert crowd
    'theme-detective-files-4fdba9',         # a tourist with a viewer
    'city-architecture-buildings-f6a844',   # a sculpture, not a city
    'city-shibuyacrossing-tokyo-d8420e',    # brand billboards
    'people-shibuyacrossing-tokyo-d8420e',
    'people-friends-family-b4a668',         # wine glasses and a hand in front
    'people-friends-people-718ef1',         # people too small: a landscape
    'portrait-alone-background-ebbe8f',     # a tiny figure in water, not a portrait
    'portrait-sad-woman-4998c6',            # figure too small for a cover
    'minimal-flatlay-minimal-296031',       # text in the photo
    'minimal-hotel-minimal-f91188',         # «HOTEL» sign
    'minimal-iphone-8-67e886',              # brand logo
    'cozy-coffee-shop-73bf28',              # big «COFFEE» sign
    'cozy-chocolate-coffee-a4969e',         # a shop's brand name
    'cozy-technology-machines-07e6f6',      # a machine close-up, not a room
    'texture-strawberry-fruit-d89e36',      # fruit, not a texture
    'abstract-girl-woman-987973',           # a person, not light & blur
    'festive-lantern-wall-13ffdb',          # a dark wall
    'festive-sky-lanterns-7fe9ee',          # an empty white sky
    'festive-wood-lanterns-22d02f',         # text all over
    'festive-lights-lanterns-67fa73',       # text all over
    'school-study-school-36b8df',           # a news page on screen
    'school-computer-keyboard-5bfa08',      # «DO MORE.» and a brand logo
    'school-macbook-laptop-210bf9',         # a brand logo
    # theme photos that do not fit their theme (contact sheet 20/11): wrong subject, text, or a person out of place
    'theme-chalk-and-board-f7b614',
    'theme-ruled-page-c3048e',
    'theme-quiet-ferryman-004e7d',
    'theme-milkflower-hanoi-cc091c',
    'theme-lunar-new-year-67fa73',
    'theme-snowy-village-4297c7',
    'theme-string-lights-51c569',
    'theme-snow-globe-86c0be',
    'theme-silent-night-3558c5',
    'theme-year-end-thanks-cb251e',
    'theme-detective-files-4a2ae3',
    'theme-buddha-birthday-13ffdb',
    'theme-lotus-lanterns-7fe9ee',
    'theme-dharma-wheel-0bd0a5',
    'theme-zen-tea-2bfd17',
    'theme-morning-chant-3838dd',
}
# most photos one search word may give a collection (so «festive» is not eight lanterns); the others take as many as fit
PER_QUERY = {'festive': 2, 'school': 3}
TAKEN = set()  # Openverse ids already used by an earlier collection (no photo in two shelves)


def curl(url, binary=False, tries=4):
    cmd = ['curl', '-sSL', '--fail', '--max-time', '120', '-A', UA, url]
    for k in range(tries):
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0:
            return r.stdout if binary else r.stdout.decode('utf-8', 'replace')
        wait = 20 * (k + 1) if b'429' in r.stderr else 3 + k * 3
        print('  retry', url[:100], r.stderr.decode()[:80].strip(), f'(wait {wait}s)', flush=True)
        time.sleep(wait)
    return None


def search(q, wide):
    """Openverse results for one query, cached on disk (anonymous use is rate-limited)."""
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, slug(f'{q}-{"wide" if wide else "any"}') + '.json')
    if os.path.exists(key):
        return json.load(open(key))
    params = {'q': q, 'license': 'cc0,pdm', 'category': 'photograph', 'source': 'stocksnap,flickr,wikimedia', 'size': 'large', 'mature': 'false', 'page_size': '20'}
    if wide:
        params['aspect_ratio'] = 'wide'
    body = curl('https://api.openverse.org/v1/images/?' + urllib.parse.urlencode(params))
    time.sleep(4)
    if not body:
        print('  search failed:', q, flush=True)
        return []
    try:
        res = json.loads(body).get('results', [])
    except ValueError:
        print('  search not JSON:', q, flush=True)
        return []
    json.dump(res, open(key, 'w'))
    return res


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60] or 'photo'


def clean_title(t):
    t = re.sub(r'<[^>]+>', ' ', t or '')
    t = re.sub(r'\.(jpe?g|png|tiff?)$', '', t, flags=re.I)
    t = re.sub(r'[_\s]+', ' ', t).strip()
    return t[:80] or 'Untitled'


def pick(col, kind, want, queries):
    out, seen = [], set()
    cap = PER_QUERY.get(col, want)
    for q in queries:
        took = 0
        for r in search(q, wide=kind == 'background'):
            if took >= cap:
                break
            w, h = r.get('width') or 0, r.get('height') or 0
            if r.get('license') not in OV_LICENSE or not r.get('url'):
                continue
            if kind == 'background' and (w < 1920 or h < 1000 or w < h):
                continue
            if kind == 'cover' and min(w, h) < 1200:
                continue
            title = clean_title(r.get('title'))
            iid = f"{col}-{slug(title)[:40]}-{r['id'][:6]}"
            if iid in EXCLUDE or r['id'] in seen or r['id'] in TAKEN or title.lower() in seen:
                continue
            seen.update([r['id'], title.lower()])
            TAKEN.add(r['id'])
            took += 1
            out.append({'r': r, 'id': iid, 'title': title, 'query': q})
            if len(out) >= want:
                return out
    return out


def save(img, kind, path):
    img = ImageOps.exif_transpose(img).convert('RGB')
    if kind == 'cover':
        s = min(img.size)
        left, top = (img.width - s) // 2, (img.height - s) // 2
        img = img.crop((left, top, left + s, top + s)).resize((1400, 1400), Image.LANCZOS)
    else:
        img.thumbnail((2400, 2400), Image.LANCZOS)
    img.save(path, 'JPEG', quality=82, optimize=True, progressive=True)
    thumb = img.copy()
    thumb.thumbnail((480, 480), Image.LANCZOS)
    thumb.save(path.replace('.jpg', '.thumb.webp'), 'WEBP', quality=72, method=6)
    return img.size


def main():
    images, sheets = [], {}
    for col, kind, label, want, queries in COLLECTIONS:
        chosen = pick(col, kind, want, queries)
        print(f'{col:10} {kind:10} {len(chosen)}/{want}', flush=True)
        if DRY:
            for c in chosen:
                print('   ', c['id'], '|', c['r']['source'], c['r']['license'], c['r']['width'], 'x', c['r']['height'])
            continue
        folder = os.path.join(ROOT, 'images', col)
        os.makedirs(folder, exist_ok=True)
        keep = {c['id'] for c in chosen}
        for f in os.listdir(folder):  # photos dropped from the selection
            if f.split('.')[0] not in keep:
                os.remove(os.path.join(folder, f))
        for c in chosen:
            r = c['r']
            rel = f"images/{col}/{c['id']}.jpg"
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                data = curl(r['url'], binary=True)
                if not data:
                    print('  skip (download failed)', c['id'], flush=True)
                    continue
                try:
                    size = save(Image.open(io.BytesIO(data)), kind, path)
                except Exception as e:  # not an image / broken file
                    print('  skip (bad image)', c['id'], e, flush=True)
                    continue
            with Image.open(path) as im:
                size = im.size
            raw = open(path, 'rb').read()
            tags = sorted({t['name'].lower() for t in (r.get('tags') or []) if t.get('name') and len(t['name']) <= 24 and t['name'].isascii()})[:12]
            images.append({
                'id': c['id'], 'kind': kind, 'collection': col, 'title': c['title'],
                'author': (r.get('creator') or '').strip() or None, 'source': r['source'],
                'sourcePage': r.get('foreign_landing_url'), 'originalUrl': r['url'],
                'license': OV_LICENSE[r['license']],
                'file': rel, 'url': RAW + rel, 'cdnUrl': CDN + rel,
                'thumb': rel.replace('.jpg', '.thumb.webp'), 'thumbCdnUrl': CDN + rel.replace('.jpg', '.thumb.webp'),
                'width': size[0], 'height': size[1], 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                'query': c['query'], 'tags': tags,
            })
            sheets.setdefault(col, []).append((c['id'], path))
    # theme photos: one per theme, wide, never one already used
    themed = []
    ok = lambda tid, r: r.get('license') in OV_LICENSE and r.get('url') and (r.get('width') or 0) >= 1600 and (r.get('width') or 0) >= (r.get('height') or 0) and r['id'] not in TAKEN and f"theme-{tid}-{r['id'][:6]}" not in EXCLUDE
    # two passes: every theme's main photo first (the same pick as with one photo per theme, so the reviewed mains never
    # move), then the variant photos — otherwise an earlier theme's variants would take a later theme's main photo
    def tries_of(words):
        # the theme's words, then each word alone (longest first): a fixed order, so a rebuild picks the same photos
        return [words] + sorted(set(words.split()) - {words}, key=len, reverse=True)
    picks = {}
    # the reviewed main photos stay put: the previous images.json pins each theme's main (search results drift as the
    # cache fills — a query that once failed may answer on the next run)
    pinned = {}
    if os.path.exists(os.path.join(ROOT, 'images.json')):
        for i in json.load(open(os.path.join(ROOT, 'images.json')))['images']:
            if i.get('theme') and not i.get('variant'):
                pinned[i['theme']] = i['id'].rsplit('-', 1)[1]
    for tid, words in theme_rows():
        pin = next((r for q in tries_of(words) for r in search(q, wide=True) if tid in pinned and r['id'].startswith(pinned[tid]) and ok(tid, r)), None)
        if pin:
            picks[tid] = [{'r': pin, 'q': next(q for q in tries_of(words) if any(x['id'] == pin['id'] for x in search(q, wide=True)))}]
            TAKEN.add(pin['id'])
            continue
        for q in tries_of(words):
            res = [r for r in search(q, wide=True) if ok(tid, r)]
            if res:
                picks[tid] = [{'r': res[0], 'q': q}]
                TAKEN.add(res[0]['id'])
                break
        else:
            print('  theme without photo:', tid, words, flush=True)
    # variant photos already in images.json stay too (in their order), so excluding one photo never shuffles the others
    kept = {}
    if os.path.exists(os.path.join(ROOT, 'images.json')):
        for i in sorted(json.load(open(os.path.join(ROOT, 'images.json')))['images'], key=lambda x: x.get('variant') or 0):
            if i.get('theme') and i.get('variant'):
                kept.setdefault(i['theme'], []).append(i['id'].rsplit('-', 1)[1])
    for tid, words in theme_rows():
        picked = picks.get(tid)
        if not picked:
            continue
        want = min(THEME_PHOTOS, THEME_PHOTO_CAP.get(tid, THEME_PHOTOS))
        results = [(q, r) for q in tries_of(words) for r in search(q, wide=True)]
        for oid in kept.get(tid, []):
            hit = next(((q, r) for q, r in results if r['id'].startswith(oid) and r['id'] not in TAKEN and ok(tid, r)), None)
            if hit and len(picked) < want:
                picked.append({'r': hit[1], 'q': hit[0]})
                TAKEN.add(hit[1]['id'])
    for tid, words in theme_rows():
        picked = picks.get(tid)
        if not picked:
            continue
        want = min(THEME_PHOTOS, THEME_PHOTO_CAP.get(tid, THEME_PHOTOS))
        for q in tries_of(words):
            for r in search(q, wide=True):
                if len(picked) >= want:
                    break
                if ok(tid, r):
                    picked.append({'r': r, 'q': q})
                    TAKEN.add(r['id'])
            if len(picked) >= want:
                break
    for tid, _ in theme_rows():
        for v, p in enumerate(picks.get(tid, [])):
            r = p['r']
            themed.append({'r': r, 'id': f"theme-{tid}-{r['id'][:6]}", 'title': clean_title(r.get('title')), 'query': p['q'], 'theme': tid, 'variant': v})
    print('themes', len(themed), 'of', len(theme_rows()), flush=True)
    if themed and not DRY:
        folder = os.path.join(ROOT, 'images', 'themes')
        os.makedirs(folder, exist_ok=True)
        keep = {c['id'] for c in themed}
        for f in os.listdir(folder):
            if f.split('.')[0] not in keep:
                os.remove(os.path.join(folder, f))
        for c in themed:
            r = c['r']
            rel = f"images/themes/{c['id']}.jpg"
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                data = curl(r['url'], binary=True)
                if not data:
                    print('  skip (download failed)', c['id'], flush=True)
                    continue
                try:
                    save(Image.open(io.BytesIO(data)), 'background', path)
                except Exception as e:
                    print('  skip (bad image)', c['id'], e, flush=True)
                    continue
            with Image.open(path) as im:
                size = im.size
            raw = open(path, 'rb').read()
            images.append({
                'id': c['id'], 'kind': 'background', 'collection': 'themes', 'theme': c['theme'], 'variant': c['variant'], 'title': c['title'],
                'author': (r.get('creator') or '').strip() or None, 'source': r['source'],
                'sourcePage': r.get('foreign_landing_url'), 'originalUrl': r['url'], 'license': OV_LICENSE[r['license']],
                'file': rel, 'url': RAW + rel, 'cdnUrl': CDN + rel,
                'thumb': rel.replace('.jpg', '.thumb.webp'), 'thumbCdnUrl': CDN + rel.replace('.jpg', '.thumb.webp'),
                'width': size[0], 'height': size[1], 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                'query': c['query'], 'tags': [],
            })
            sheets.setdefault('themes', []).append((c['id'], path))
    if DRY:
        return
    cols = [{'id': c, 'kind': k, 'label': l, 'count': sum(1 for i in images if i['collection'] == c)} for c, k, l, _, _ in COLLECTIONS]
    if any(i['collection'] == 'themes' for i in images):
        cols.append({'id': 'themes', 'kind': 'background', 'label': 'Themes', 'count': sum(1 for i in images if i['collection'] == 'themes')})
    lib = {
        'name': 'gbm — free photos for video backgrounds and podcast covers', 'version': 1,
        'generated': time.strftime('%Y-%m-%d'), 'baseUrl': RAW, 'cdnBaseUrl': CDN,
        'count': len(images), 'totalBytes': sum(i['bytes'] for i in images),
        'licenses': LICENSES, 'sources': SOURCES, 'collections': cols, 'images': images,
    }
    json.dump(lib, open(os.path.join(ROOT, 'images.json'), 'w'), indent=1, ensure_ascii=False)
    lines = ['# Photo credits', '', 'Every photo here is CC0 or Public Domain Mark: no credit is required. Listed for courtesy.', '']
    for c in cols:
        lines += [f"## {c['label']} ({c['kind']})", '']
        for i in images:
            if i['collection'] == c['id']:
                lines.append(f"- `{i['file']}` — {i['title']}" + (f" by {i['author']}" if i['author'] else '') + f" ({i['source']}, {i['license']}) — {i['sourcePage']}")
        lines.append('')
    open(os.path.join(ROOT, 'CREDITS-IMAGES.md'), 'w').write('\n'.join(lines))
    print('images:', len(images), 'MB:', round(lib['totalBytes'] / 1e6, 1))
    if SHEETS:
        os.makedirs(SHEETS, exist_ok=True)
        for col, items in sheets.items():
            cell, per = 300, 6
            rows = (len(items) + per - 1) // per
            sheet = Image.new('RGB', (cell * per, (cell + 22) * rows), 'white')
            d = ImageDraw.Draw(sheet)
            for n, (iid, path) in enumerate(items):
                with Image.open(path.replace('.jpg', '.thumb.webp')) as im:
                    t = ImageOps.fit(im.convert('RGB'), (cell - 6, cell - 6))
                x, y = (n % per) * cell, (n // per) * (cell + 22)
                sheet.paste(t, (x + 3, y + 3))
                d.text((x + 4, y + cell), f'{n}: {iid[len(col) + 1:][:40]}', fill='black')
            sheet.save(os.path.join(SHEETS, f'{col}.jpg'), quality=70)


if __name__ == '__main__':
    main()
