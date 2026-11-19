#!/usr/bin/env python3
"""Build the gbm background-music library: pick CC0 / CC BY instrumentals, download them, write tracks.json + CREDITS.md.

Sources
  • Incompetech (Kevin MacLeod) — every piece is CC BY 4.0; catalogue at incompetech.com/music/royalty-free/pieces.json
  • ccMixter — query API, only CC0 and CC BY uploads that are NOT remixes (a remix also owes credit to its sources)

Files are stored unmodified (no re-encoding), so the original licence applies to each file as-is.

Usage: python3 scripts/build.py            # download missing files, rebuild tracks.json and CREDITS.md
       python3 scripts/build.py --dry-run  # only print the selection
"""
import hashlib, json, os, re, subprocess, sys, time, unicodedata, urllib.parse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = 'https://raw.githubusercontent.com/zuizui46/gbm/main/'
CDN = 'https://cdn.jsdelivr.net/gh/zuizui46/gbm@main/'
UA = {'User-Agent': 'gbm-library-builder/1.0'}
DRY = '--dry-run' in sys.argv

LICENSES = {
    'CC-BY-4.0': {'name': 'Creative Commons Attribution 4.0', 'url': 'https://creativecommons.org/licenses/by/4.0/', 'attribution': True, 'commercial': True, 'derivatives': True},
    'CC-BY-3.0': {'name': 'Creative Commons Attribution 3.0', 'url': 'https://creativecommons.org/licenses/by/3.0/', 'attribution': True, 'commercial': True, 'derivatives': True},
    'CC0-1.0': {'name': 'Creative Commons Zero 1.0 (Public Domain Dedication)', 'url': 'https://creativecommons.org/publicdomain/zero/1.0/', 'attribution': False, 'commercial': True, 'derivatives': True},
}


def get(url, binary=False, tries=3, referer=None):
    """curl, not urllib: ccMixter answers with header lines longer than http.client accepts, and serves files only
    with a Referer from its own pages. Incompetech throttles each connection (~10 kB/s): no overall time limit,
    only a stall check, and many downloads in parallel."""
    cmd = ['curl', '-sSL', '--fail', '--speed-limit', '1000', '--speed-time', '90', '-A', UA['User-Agent']] + (['-e', referer] if referer else []) + [url]
    for k in range(tries):
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0: return r.stdout if binary else r.stdout.decode('utf-8', 'replace')
        print('  retry', url, r.stderr.decode()[:120], flush=True); time.sleep(2 + k * 3)
    raise SystemExit(f'download failed: {url}')


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:70] or 'track'


def secs(hms):
    parts = [int(p) for p in (hms or '0').split(':') if p.strip().isdigit()]
    t = 0
    for p in parts: t = t * 60 + p
    return t


def probe(path):
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', path], capture_output=True, text=True, check=True).stdout
        return round(float(out.strip()), 1)
    except Exception:  # noqa: BLE001
        return None


# ───────────────────────────────────────────── moods / uses (English tags, Vietnamese labels in README)
MOOD_OF_FEEL = {
    'Calming': 'calm', 'Relaxed': 'relaxed', 'Bright': 'bright', 'Uplifting': 'uplifting', 'Bouncy': 'playful', 'Humorous': 'funny',
    'Mysterious': 'mysterious', 'Mystical': 'mystical', 'Somber': 'sad', 'Dark': 'dark', 'Eerie': 'eerie', 'Unnerving': 'tense',
    'Suspenseful': 'suspense', 'Intense': 'intense', 'Epic': 'epic', 'Action': 'action', 'Driving': 'driving', 'Grooving': 'groovy', 'Aggressive': 'aggressive',
}
USE_RULES = [  # (use tag, moods/genres any-of)
    ('podcast', {'calm', 'relaxed', 'groovy', 'bright', 'lofi', 'jazz', 'chill'}),
    ('study', {'calm', 'relaxed', 'lofi', 'piano', 'ambient', 'chill'}),
    ('story', {'mysterious', 'mystical', 'suspense', 'sad', 'calm', 'soundtrack', 'film'}),
    ('kids', {'playful', 'funny', 'bright'}),
    ('meditation', {'calm', 'ambient', 'mystical'}),
    ('motivation', {'uplifting', 'epic', 'driving', 'bright'}),
    ('horror', {'eerie', 'tense', 'dark', 'horror'}),
    ('holiday', {'holiday', 'christmas'}),
]
CHRISTMAS = re.compile(r'christmas|xmas|noel|jingle|sleigh|carol|adeste|deck the|silent night|holly|santa|krampus|nutcracker|sugar plum|wenceslas|we three kings|o holy|joy to the world|hark|angels we have|midnight clear|first noel|o come|good king|we wish you', re.I)


def uses_for(tags):
    s = set(tags)
    return [u for u, need in USE_RULES if s & need]


# ───────────────────────────────────────────── Incompetech
GENRES = {2: 'african', 3: 'blues', 4: 'classical', 5: 'contemporary', 6: 'disco', 7: 'electronica', 8: 'funk', 9: 'holiday', 10: 'horror', 11: 'jazz', 12: 'latin',
          13: 'modern', 14: 'musical', 15: 'polka', 16: 'pop', 18: 'reggae', 19: 'rock', 20: 'silent-film', 21: 'ska', 22: 'soundtrack', 23: 'stings', 24: 'unclassifiable', 25: 'world', 26: 'urban'}
# buckets: (name, how many, predicate)
BUCKETS = [
    ('calm-piano', 14, lambda m, g, ins, x: {'calm', 'relaxed'} & m and not {'dark', 'eerie', 'tense', 'aggressive'} & m and ('piano' in ins or g in ('classical', 'contemporary', 'modern'))),
    ('uplifting', 12, lambda m, g, ins, x: {'uplifting', 'bright'} & m and not {'dark', 'eerie', 'aggressive'} & m and g not in ('rock', 'stings', 'holiday')),
    ('kids-fun', 8, lambda m, g, ins, x: {'playful', 'funny'} & m and not {'dark', 'eerie'} & m and g not in ('stings', 'holiday')),
    ('christmas', 10, lambda m, g, ins, x: bool(CHRISTMAS.search(x['title'])) and 'rap' not in x['title'].lower()),
    ('story-mystery', 10, lambda m, g, ins, x: {'mysterious', 'mystical', 'suspense'} & m and not {'aggressive', 'action'} & m and g in ('soundtrack', 'horror', 'contemporary', 'unclassifiable', 'modern')),
    ('jazz-lounge', 8, lambda m, g, ins, x: g == 'jazz' and {'relaxed', 'calm', 'groovy'} & m),
    ('epic-cinematic', 6, lambda m, g, ins, x: 'epic' in m and g == 'soundtrack' and 'aggressive' not in m),
    ('sad-emotional', 6, lambda m, g, ins, x: 'sad' in m and not {'eerie', 'aggressive', 'tense'} & m),
    ('world-calm', 5, lambda m, g, ins, x: g == 'world' and {'calm', 'relaxed', 'mystical'} & m),
    ('horror', 4, lambda m, g, ins, x: g == 'horror' and {'eerie', 'tense'} & m),
]


def base_title(t):
    """'Dance of the Sugar Plum Fairies' ≈ 'Dance of the Sugar Plum Fairy'; 'too quiet (piano)' ≈ 'too quiet (instr.)'."""
    w = re.sub(r'\s*[-(].*$', '', t).strip().lower().split()
    return ' '.join(x.rstrip('s') for x in w[:4])


def incompetech():
    pieces = json.loads(get('https://incompetech.com/music/royalty-free/pieces.json'))
    used, seen_base, out = set(), set(), []
    for name, n, pred in BUCKETS:
        cands = []
        for x in pieces:
            fn, title = x.get('filename') or '', x.get('title') or ''
            if not fn.lower().endswith('.mp3') or fn in used: continue
            d = secs(x.get('length'))
            if not 75 <= d <= 330: continue                                          # 1:15 – 5:30
            if re.search(r'vocal|feat\.?|\bsing|choir|lyrics|stinger|sting\b|\brap\b', title + ' ' + (x.get('description') or ''), re.I) and 'instrumental' not in title.lower(): continue
            m = {MOOD_OF_FEEL[f.strip()] for f in (x.get('feel') or '').split(',') if f.strip() in MOOD_OF_FEEL}
            g = GENRES.get(int(x['genre'] or 0), 'other')
            ins = {i.strip().lower() for i in (x.get('instruments') or '').split(',') if i.strip()}
            if pred(m, g, ins, x): cands.append((x, m, g, ins, d))
        cands.sort(key=lambda c: hashlib.sha1(c[0]['title'].encode()).hexdigest())          # stable but spread over the alphabet
        picked = 0
        for x, m, g, ins, d in cands:
            if picked >= n: break
            b = base_title(x['title'])
            if b in seen_base: continue
            seen_base.add(b); used.add(x['filename']); picked += 1
            title = x['title'].strip()
            moods = sorted(m) + (['christmas'] if name == 'christmas' else [])
            tags = sorted(set(moods) | {g} | ins)
            out.append({
                'id': f'incompetech-{slug(title)}', 'title': title, 'artist': 'Kevin MacLeod', 'source': 'incompetech',
                'sourcePage': 'https://incompetech.com/music/royalty-free/music.html',
                'originalUrl': 'https://incompetech.com/music/royalty-free/mp3-royaltyfree/' + urllib.parse.quote(x['filename']),
                'file': f'music/incompetech/{slug(title)}.mp3', 'license': 'CC-BY-4.0',
                'attribution': f'"{title}" Kevin MacLeod (incompetech.com) — Licensed under Creative Commons: By Attribution 4.0 — https://creativecommons.org/licenses/by/4.0/',
                'collection': name, 'moods': moods, 'genres': [g], 'instruments': sorted(ins), 'uses': uses_for(tags + [name]),
                'bpm': int(x['bpm']) if str(x.get('bpm') or '').isdigit() else None, 'durationHint': d,
                'description': (x.get('description') or '').strip()[:300], 'isrc': x.get('isrc'), 'tags': tags,
            })
        print(f'incompetech {name}: {picked}/{n} (of {len(cands)})')
    return out


# ───────────────────────────────────────────── ccMixter
CC_QUERIES = [  # (licence filter, tag query, how many)
    ('zero', 'instrumental', 14),
    ('by', 'instrumental,piano', 6),
    ('by', 'instrumental,chill', 6),
    ('by', 'instrumental,ambient', 5),
    ('by', 'instrumental,acoustic', 5),
]
CC_LIC = {'creativecommons.org/publicdomain/zero/1.0': 'CC0-1.0', 'creativecommons.org/licenses/by/3.0': 'CC-BY-3.0', 'creativecommons.org/licenses/by/4.0': 'CC-BY-4.0'}
CC_SKIP = {'remix', 'acappella', 'a_cappella', 'vocals', 'singing', 'female_vocals', 'male_vocals', 'spoken_word', 'rap', 'lyrics'}
CC_MOOD = {'chill': 'chill', 'mellow': 'calm', 'relaxing': 'calm', 'ambient': 'ambient', 'happy': 'bright', 'upbeat': 'uplifting', 'dark': 'dark', 'sad': 'sad', 'melancholy': 'sad',
           'cinematic': 'epic', 'film': 'film', 'music_for_film': 'film', 'lofi': 'lofi', 'downtempo': 'chill', 'jazz': 'jazz', 'piano': 'piano', 'guitar': 'guitar', 'acoustic': 'acoustic',
           'classical': 'classical', 'electronic': 'electronica', 'hip_hop': 'hip-hop', 'orchestral': 'orchestral', 'folk': 'folk', 'experimental': 'experimental', 'christmas': 'christmas'}


def ccmixter(seen_titles):
    out, used, per_artist = [], set(), Counter()
    for lic, tags, n in CC_QUERIES:
        rows = []                                  # 10 per page: the server copies the body into a header, big pages break clients
        for off in range(0, 120, 10):
            q = urllib.parse.urlencode({'f': 'json', 'lic': lic, 'tags': tags, 'type': 'all', 'sort': 'rank', 'limit': 10, 'offset': off})
            page = json.loads(get('http://ccmixter.org/api/query?' + q))
            rows += page
            if len(page) < 10: break
        picked = 0
        for x in rows:
            if picked >= n: break
            t = {s for s in (x.get('upload_tags') or '').split(',') if s}
            if t & CC_SKIP or 'instrumental' not in t or re.search(r'stems|loop|sample pack|acapella|subtrack|\btest\b', x.get('upload_name') or '', re.I): continue
            if per_artist[x.get('user_name')] >= 2: continue
            url = (x.get('license_url') or '').replace('http://', '').replace('https://', '').rstrip('/')
            licence = CC_LIC.get(url)
            if not licence: continue
            mp3 = next((f for f in x.get('files', []) if (f.get('file_name') or '').lower().endswith('.mp3') and f.get('download_url')), None)
            if not mp3: continue
            d = secs((mp3.get('file_format_info') or {}).get('ps'))
            if not 60 <= d <= 360: continue
            key = (x.get('user_name'), base_title(x.get('upload_name') or ''))
            if key in used or (x.get('upload_name') or '').lower() in seen_titles: continue
            used.add(key); picked += 1; per_artist[x.get('user_name')] += 1
            title, artist = x['upload_name'].strip(), (x.get('user_real_name') or x.get('user_name') or '').strip()
            moods = sorted({CC_MOOD[s] for s in t if s in CC_MOOD})
            bpm = next((int(s[4:7]) for s in t if re.fullmatch(r'bpm_\d{3}_\d{3}', s)), None)
            tg = sorted(set(moods) | {'instrumental'})
            out.append({
                'id': f'ccmixter-{slug(artist)}-{slug(title)}'[:90], 'title': title, 'artist': artist, 'source': 'ccmixter',
                'sourcePage': x.get('file_page_url'), 'originalUrl': mp3['download_url'],
                'file': f'music/ccmixter/{slug(artist)}-{slug(title)}'[:110] + '.mp3', 'license': licence,
                'attribution': (f'"{title}" by {artist} (ccmixter.org) — {LICENSES[licence]["name"]} — {LICENSES[licence]["url"]} — {x.get("file_page_url")}'
                                if licence != 'CC0-1.0' else f'"{title}" by {artist} (ccmixter.org) — CC0, no attribution required (credit appreciated)'),
                'collection': f'ccmixter-{lic}', 'moods': moods, 'genres': [m for m in moods if m in ('jazz', 'classical', 'electronica', 'hip-hop', 'folk', 'orchestral', 'experimental')],
                'instruments': [m for m in moods if m in ('piano', 'guitar')], 'uses': uses_for(tg + ['podcast']), 'bpm': bpm, 'durationHint': d,
                'description': '', 'isrc': None, 'tags': tg,
            })
        print(f'ccmixter {lic} {tags}: {picked}/{n}')
    return out


# ───────────────────────────────────────────── main
def main():
    tracks = incompetech()
    tracks += ccmixter({t['title'].lower() for t in tracks})
    if DRY:
        for t in tracks: print(f"{t['license']:10} {t['collection']:16} {t['title']} — {t['artist']}")
        print(len(tracks), 'tracks'); return
    def fetch(t):                                                  # Incompetech is slow per connection: 24 in parallel
        path = os.path.join(ROOT, t['file'])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 10_000: return
        data = get(t['originalUrl'], binary=True, referer=t['sourcePage'] if t['source'] == 'ccmixter' else None)
        if len(data) > 95 * 1024 * 1024: raise SystemExit(f'too big for GitHub: {t["file"]}')
        with open(path + '.part', 'wb') as f: f.write(data)
        os.replace(path + '.part', path); print('↓', t['file'], flush=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(24) as ex: list(ex.map(fetch, tracks))
    for t in tracks:
        path = os.path.join(ROOT, t['file'])
        data = open(path, 'rb').read()
        t['bytes'] = len(data); t['sha256'] = hashlib.sha256(data).hexdigest()
        t['duration'] = probe(path) or float(t['durationHint']); del t['durationHint']
        t['url'] = RAW + urllib.parse.quote(t['file']); t['cdnUrl'] = CDN + urllib.parse.quote(t['file'])
        t['vocals'] = False; t['modified'] = False
    keep = {t['file'] for t in tracks}                                  # drop files no longer selected
    for sub in ('music/incompetech', 'music/ccmixter'):
        d = os.path.join(ROOT, sub)
        for fn in os.listdir(d) if os.path.isdir(d) else []:
            if f'{sub}/{fn}' not in keep: os.remove(os.path.join(d, fn)); print('✗', sub, fn)
    tracks.sort(key=lambda t: (t['source'], t['collection'], t['title'].lower()))
    count = lambda k: dict(sorted(Counter(v for t in tracks for v in (t[k] if isinstance(t[k], list) else [t[k]])).items()))
    lib = {'name': 'gbm — free background music', 'version': 1, 'generated': time.strftime('%Y-%m-%d'),
           'baseUrl': RAW, 'cdnBaseUrl': CDN, 'count': len(tracks), 'totalBytes': sum(t['bytes'] for t in tracks),
           'licenses': LICENSES, 'facets': {'license': count('license'), 'source': count('source'), 'collection': count('collection'), 'moods': count('moods'), 'uses': count('uses'), 'genres': count('genres')},
           'tracks': tracks}
    with open(os.path.join(ROOT, 'tracks.json'), 'w', encoding='utf-8') as f: json.dump(lib, f, ensure_ascii=False, indent=1); f.write('\n')
    lines = ['# Credits', '', 'Every audio file keeps its own licence (see `tracks.json` → `license`). Files are unmodified copies of the originals.', '',
             'Copy the line of each track you use into your video / podcast description.', '']
    for src, head in (('incompetech', 'Incompetech — Kevin MacLeod (CC BY 4.0)'), ('ccmixter', 'ccMixter (CC0 / CC BY)')):
        lines += [f'## {head}', '']
        for t in tracks:
            if t['source'] == src: lines.append(f"- `{t['file']}` — {t['attribution']} — source: {t['sourcePage']}")
        lines.append('')
    with open(os.path.join(ROOT, 'CREDITS.md'), 'w', encoding='utf-8') as f: f.write('\n'.join(lines))
    print(len(tracks), 'tracks,', round(lib['totalBytes'] / 1e6, 1), 'MB')


if __name__ == '__main__':
    main()
