#!/usr/bin/env python3
"""Add new background collections to the photo library WITHOUT touching what is there (Kat, 23/11: «Background có 1286 …
lên hết 3000»; one collection per kind of podcast / review: books, cinema, cars, fashion, food, travel by country…).

Same source and rules as build-images.py (Openverse, CC0 / PDM photographs only, wide ≥ 1920 px, resized, EXIF dropped),
using its own functions. Existing photos, theme photos and collections stay as they are; a photo already in the library
is never taken twice. Appends to images.json (images + collections) and CREDITS-IMAGES.md.

Usage: python3 scripts/add-collections.py [--dry-run] [--only <collection,…>]
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('build_images', os.path.join(HERE, 'build-images.py'))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

ROOT = B.ROOT

PAGES = 4


def search_pages(q, wide):
    """Like build-images.search, over the first PAGES pages (one page of 20 rarely holds 40 wide CC0 photos)."""
    out = []
    for page in range(1, PAGES + 1):
        os.makedirs(B.CACHE, exist_ok=True)
        key = os.path.join(B.CACHE, B.slug(f'{q}-{"wide" if wide else "any"}-p{page}') + '.json')
        if os.path.exists(key):
            res = json.load(open(key))
        else:
            params = {'q': q, 'license': 'cc0,pdm', 'category': 'photograph', 'source': 'stocksnap,flickr,wikimedia', 'size': 'large', 'mature': 'false', 'page_size': '20', 'page': str(page)}
            if wide:
                params['aspect_ratio'] = 'wide'
            body = B.curl('https://api.openverse.org/v1/images/?' + B.urllib.parse.urlencode(params))
            B.time.sleep(4)
            try:
                res = json.loads(body).get('results', []) if body else []
            except ValueError:
                res = []
            if body:
                json.dump(res, open(key, 'w'))
        out += res
        if len(res) < 20:
            break
    return out


B.search = search_pages
DRY = '--dry-run' in sys.argv
ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None

W = 45  # photos per collection
# (id, label, queries) — every collection a kind of video people make on Kat
NEW = [
    # reviews & culture
    ('books', 'Books & reading', ['library bookshelf', 'open book', 'reading book', 'old books', 'bookstore']),
    ('cinema', 'Cinema & film', ['cinema theater', 'movie theater seats', 'film projector', 'film reel', 'popcorn']),
    ('music', 'Music & concerts', ['concert crowd', 'guitar', 'piano keys', 'vinyl record player', 'music studio']),
    ('gaming', 'Games & arcade', ['arcade', 'video game', 'game controller', 'neon arcade', 'retro computer']),
    ('art', 'Art & museums', ['art museum', 'painting gallery', 'sculpture', 'street art mural', 'artist studio']),
    # vehicles
    ('cars', 'Cars', ['sports car', 'classic car', 'car interior', 'car on road', 'vintage car']),
    ('motorbikes', 'Motorbikes', ['motorcycle', 'motorbike road', 'scooter', 'motorcycle rider', 'vintage motorcycle']),
    ('roads', 'Roads & road trips', ['highway', 'mountain road', 'desert road', 'country road', 'road trip']),
    ('trains', 'Trains & stations', ['train station', 'railway', 'train window', 'subway', 'tram']),
    ('aviation', 'Planes & airports', ['airplane', 'airport', 'airplane window', 'aircraft sky', 'runway']),
    # lifestyle
    ('fashion', 'Fashion & style', ['fashion', 'clothing store', 'clothes rack', 'shoes', 'fabric textile']),
    ('beauty', 'Beauty & care', ['cosmetics', 'flowers vase', 'spa', 'perfume', 'mirror']),
    ('food', 'Food & cooking', ['food table', 'cooking kitchen', 'fresh vegetables', 'bakery bread', 'restaurant']),
    ('coffee', 'Coffee & tea', ['coffee cup', 'coffee beans', 'tea cup', 'cafe', 'latte']),
    ('fitness', 'Sport & fitness', ['gym', 'running track', 'stadium', 'yoga', 'cycling']),
    ('pets', 'Pets & animals', ['dog', 'cat', 'puppy', 'kitten', 'horse']),
    ('wildlife', 'Wildlife', ['wildlife', 'birds', 'deer', 'butterfly', 'fox']),
    ('kids', 'Kids & play', ['toys', 'playground', 'children playing', 'colorful balloons', 'crayons']),
    ('home', 'Home & interiors', ['interior design', 'bedroom', 'kitchen interior', 'window light', 'plants indoor']),
    ('work', 'Work & business', ['office', 'meeting room', 'laptop desk', 'skyscraper', 'coworking']),
    ('tech', 'Tech & science', ['circuit board', 'computer', 'laboratory', 'robot', 'server room']),
    ('money', 'Money & finance', ['coins', 'stock market', 'bank', 'calculator', 'money']),
    ('health', 'Health & calm', ['meditation', 'forest path', 'calm lake', 'sunrise', 'zen stones']),
    ('garden', 'Gardens & flowers', ['garden', 'flower field', 'roses', 'tulips', 'greenhouse']),
    # places
    ('japan', 'Japan', ['kyoto', 'tokyo street', 'japanese temple', 'torii', 'japanese garden']),
    ('china', 'China', ['great wall', 'chinese temple', 'chinese lantern', 'shanghai', 'guilin']),
    ('korea', 'Korea', ['seoul', 'korean palace', 'hanok', 'busan', 'korea temple']),
    ('vietnam', 'Vietnam', ['vietnam', 'hanoi', 'ha long bay', 'hoi an', 'rice terraces']),
    ('southeast-asia', 'Southeast Asia', ['bangkok', 'bali', 'angkor wat', 'singapore', 'tropical beach']),
    ('uk', 'United Kingdom', ['london', 'scotland highlands', 'english countryside', 'big ben', 'london bus']),
    ('usa', 'United States', ['new york city', 'grand canyon', 'route 66', 'san francisco', 'las vegas']),
    ('europe', 'Europe', ['paris', 'rome', 'venice', 'santorini', 'prague']),
    ('mountains', 'Mountains & snow', ['snowy mountains', 'alps', 'glacier', 'ski', 'mountain peak']),
    ('desert', 'Desert & canyons', ['desert dunes', 'canyon', 'sahara', 'cactus', 'desert sunset']),
    ('islands', 'Islands & tropics', ['island', 'palm trees beach', 'lagoon', 'coral reef', 'tropical sunset']),
    ('rivers', 'Rivers & lakes', ['river', 'lake reflection', 'waterfall forest', 'boat lake', 'stream']),
    # moods
    ('night', 'Night & city lights', ['night street', 'neon lights', 'city night rain', 'night bridge', 'night market']),
    ('rain', 'Rain & fog', ['rain window', 'fog forest', 'rainy street', 'umbrella rain', 'misty lake']),
    ('vintage', 'Vintage & retro', ['vintage', 'retro', 'old camera', 'typewriter', 'jukebox']),
    ('festivals', 'Festivals & lights', ['fireworks', 'lanterns festival', 'carnival', 'christmas lights', 'sparklers']),
    ('minimal', 'Minimal & clean', ['minimal', 'white wall', 'architecture minimal', 'geometric', 'shadow']),
    ('space', 'Sky & space', ['milky way', 'galaxy', 'aurora', 'moon', 'starry sky']),
    ('autumn', 'Autumn', ['autumn forest', 'fall leaves', 'pumpkins', 'autumn road', 'maple']),
    ('winter', 'Winter', ['snow forest', 'winter village', 'frozen lake', 'snowfall', 'winter cabin']),
    ('spring', 'Spring & summer', ['cherry blossom', 'spring flowers', 'summer meadow', 'sunflowers', 'lavender field']),
    ('ocean', 'Ocean & waves', ['ocean waves', 'surf', 'sea cliffs', 'lighthouse', 'underwater']),
    ('architecture', 'Architecture', ['architecture', 'staircase', 'cathedral', 'modern building', 'bridge']),
    ('villages', 'Villages & farms', ['village', 'farm', 'barn', 'countryside house', 'vineyard']),
    ('sunsets', 'Sunsets & golden hour', ['sunset', 'golden hour', 'sunset clouds', 'sunset field', 'sunset silhouette']),
    ('streets', 'Streets & cafés', ['street cafe', 'old street', 'alley', 'market street', 'shop front']),
    ('macro', 'Close-ups & textures', ['macro flower', 'water drops', 'leaf texture', 'bokeh lights', 'feather']),
    ('celebrations', 'Celebrations', ['wedding', 'birthday cake', 'party balloons', 'confetti', 'champagne']),
    ('study', 'Study & school', ['classroom', 'school desk', 'notebook pen', 'university campus', 'library study']),
]


def main():
    lib_path = os.path.join(ROOT, 'images.json')
    lib = json.load(open(lib_path))
    have_cols = {c['id'] for c in lib['collections']}
    # never take a photo the library already has (ids end with the first 6 chars of the Openverse id)
    have = {i['id'].rsplit('-', 1)[1] for i in lib['images']}
    added, cols = [], []
    for col, label, queries in NEW:
        if col in have_cols or (ONLY and col not in ONLY):
            continue
        chosen = [c for c in B.pick(col, 'background', W + 10, queries) if c['r']['id'][:6] not in have][:W]
        print(f'{col:16} {len(chosen)}/{W}', flush=True)
        if DRY:
            continue
        folder = os.path.join(ROOT, 'images', col)
        os.makedirs(folder, exist_ok=True)
        got = []
        for c in chosen:
            r = c['r']
            rel = f"images/{col}/{c['id']}.jpg"
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                data = B.curl(r['url'], binary=True)
                if not data:
                    print('  skip (download failed)', c['id'], flush=True)
                    continue
                try:
                    B.save(B.Image.open(B.io.BytesIO(data)), 'background', path)
                except Exception as e:
                    print('  skip (bad image)', c['id'], e, flush=True)
                    continue
            with B.Image.open(path) as im:
                size = im.size
            raw = open(path, 'rb').read()
            tags = sorted({t['name'].lower() for t in (r.get('tags') or []) if t.get('name') and len(t['name']) <= 24 and t['name'].isascii()})[:12]
            got.append({
                'id': c['id'], 'kind': 'background', 'collection': col, 'title': c['title'],
                'author': (r.get('creator') or '').strip() or None, 'source': r['source'],
                'sourcePage': r.get('foreign_landing_url'), 'originalUrl': r['url'],
                'license': B.OV_LICENSE[r['license']],
                'file': rel, 'url': B.RAW + rel, 'cdnUrl': B.CDN + rel,
                'thumb': rel.replace('.jpg', '.thumb.webp'), 'thumbCdnUrl': B.CDN + rel.replace('.jpg', '.thumb.webp'),
                'width': size[0], 'height': size[1], 'bytes': len(raw), 'sha256': B.hashlib.sha256(raw).hexdigest(),
                'query': c['query'], 'tags': tags,
            })
            have.add(r['id'][:6])
        added += got
        cols.append({'id': col, 'kind': 'background', 'label': label, 'count': len(got)})
        # write after every collection: a stop half-way keeps what is done
        lib['images'] += got
        lib['collections'] += [cols[-1]]
        lib['count'] = len(lib['images'])
        lib['totalBytes'] = sum(i['bytes'] for i in lib['images'])
        json.dump(lib, open(lib_path, 'w'), indent=1, ensure_ascii=False)
        with open(os.path.join(ROOT, 'CREDITS-IMAGES.md'), 'a') as f:
            f.write('\n' + '\n'.join([f'## {label} (background)', ''] + [f"- {i['title']} — {i['author'] or 'unknown'} · {i['source']} · {i['license']} · {i['sourcePage'] or i['originalUrl']}" for i in got]) + '\n')
    print('added', len(added), 'photos in', len(cols), 'collections', flush=True)


if __name__ == '__main__':
    main()
