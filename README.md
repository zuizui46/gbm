# gbm — free background music

A small, curated set of **instrumental background music** under **CC0** or **CC BY** only, for podcasts, video
narration and storytelling. Every file is an unmodified copy of the original, keeps its own licence, and has a
ready-made credit line.

> Licences differ per file — read [LICENSE](LICENSE) and [CREDITS.md](CREDITS.md). CC BY tracks **require credit**
> (copy the `attribution` text into your video / podcast description).

## Use the list from code

```
https://raw.githubusercontent.com/zuizui46/gbm/main/tracks.json
https://cdn.jsdelivr.net/gh/zuizui46/gbm@main/tracks.json      (CDN)
```

```jsonc
{
  "count": 114,
  "baseUrl": "https://raw.githubusercontent.com/zuizui46/gbm/main/",
  "licenses": { "CC-BY-4.0": { "name": "…", "url": "…", "attribution": true, "commercial": true, "derivatives": true }, … },
  "facets": { "license": {…}, "source": {…}, "collection": {…}, "moods": {…}, "uses": {…}, "genres": {…} },
  "tracks": [
    {
      "id": "incompetech-at-rest",
      "title": "At Rest",
      "artist": "Kevin MacLeod",
      "source": "incompetech",                 // incompetech | ccmixter
      "sourcePage": "https://…",
      "originalUrl": "https://…/At Rest.mp3",  // where the file was downloaded from
      "file": "music/incompetech/at-rest.mp3",
      "url": "https://raw.githubusercontent.com/zuizui46/gbm/main/music/incompetech/at-rest.mp3",
      "cdnUrl": "https://cdn.jsdelivr.net/gh/zuizui46/gbm@main/music/incompetech/at-rest.mp3",
      "license": "CC-BY-4.0",                  // key into "licenses": CC0-1.0 | CC-BY-3.0 | CC-BY-4.0
      "attribution": "\"At Rest\" Kevin MacLeod (incompetech.com) — Licensed under …",
      "collection": "calm-piano",
      "moods": ["calm", "relaxed"],
      "genres": ["contemporary"],
      "instruments": ["piano"],
      "uses": ["podcast", "study", "story", "meditation"],
      "tags": ["calm", "contemporary", "piano", "relaxed"],
      "bpm": 72, "duration": 183.4, "bytes": 4412345, "sha256": "…",
      "vocals": false, "modified": false
    }
  ]
}
```

Filter examples (JavaScript):

```js
const lib = await (await fetch('https://cdn.jsdelivr.net/gh/zuizui46/gbm@main/tracks.json')).json();
const calm = lib.tracks.filter((t) => t.uses.includes('podcast') && t.moods.includes('calm'));
const noCredit = lib.tracks.filter((t) => !lib.licenses[t.license].attribution);   // CC0 only
const xmas = lib.tracks.filter((t) => t.collection === 'christmas');
```

### Tags

| field | values |
|---|---|
| `uses` | `podcast` (podcast), `study` (học tập), `story` (kể chuyện), `kids` (thiếu nhi), `meditation` (thiền / tĩnh tâm), `motivation` (truyền cảm hứng), `horror` (rùng rợn), `holiday` (lễ hội) |
| `moods` | `calm`, `relaxed`, `bright`, `uplifting`, `playful`, `funny`, `mysterious`, `mystical`, `suspense`, `sad`, `dark`, `eerie`, `tense`, `epic`, `action`, `driving`, `groovy`, `chill`, `christmas`, … |
| `collection` | `calm-piano`, `uplifting`, `kids-fun`, `christmas`, `story-mystery`, `jazz-lounge`, `epic-cinematic`, `sad-emotional`, `world-calm`, `horror`, `ccmixter-zero`, `ccmixter-by` |

## Sources

| source | licence | notes |
|---|---|---|
| [Incompetech](https://incompetech.com) — Kevin MacLeod | CC BY 4.0 | Credit: `"Title" Kevin MacLeod (incompetech.com) — Licensed under Creative Commons: By Attribution 4.0 — https://creativecommons.org/licenses/by/4.0/` |
| [ccMixter](https://ccmixter.org) | CC0 / CC BY 3.0 | Only original instrumental uploads — remixes are excluded (they owe credit to their sources too) |

## Rebuild

```
python3 scripts/build.py            # downloads missing files, rewrites tracks.json + CREDITS.md
python3 scripts/build.py --dry-run  # prints the selection only
```

Needs `curl` and `ffprobe` (for durations). The selection is deterministic; edit `BUCKETS` / `CC_QUERIES` in the
script to change it.

## Photos (backgrounds and covers)

Real photographs for video backgrounds (`kind: "background"`, long edge ≤ 2400 px) and podcast covers
(`kind: "cover"`, 1400 × 1400 centre square), **CC0 or Public Domain Mark only** — no credit needed (author and page
are still listed in `images.json` and [CREDITS-IMAGES.md](CREDITS-IMAGES.md)). Taken from StockSnap, Flickr and
Wikimedia Commons through the [Openverse](https://openverse.org) API; resized and re-encoded (EXIF dropped), which
CC0 / PDM allow. Every photo has a 480 px WebP thumbnail next to it (`*.thumb.webp`) for pickers.

```
https://cdn.jsdelivr.net/gh/zuizui46/gbm@main/images.json
```

```jsonc
{
  "count": 209,
  "licenses": { "CC0-1.0": {…}, "PDM-1.0": {…} },
  "sources": [ { "id": "stocksnap", "name": "StockSnap.io", "search": "https://stocksnap.io/search/{q}", "inLibrary": true }, … ],
  "collections": [ { "id": "nature", "kind": "background", "label": "Nature", "count": 16 }, … ],
  "images": [
    {
      "id": "nature-misty-forest-0a1b2c", "kind": "background", "collection": "nature", "title": "Misty Forest",
      "author": "…", "source": "stocksnap", "sourcePage": "https://stocksnap.io/photo/…", "license": "CC0-1.0",
      "file": "images/nature/nature-misty-forest-0a1b2c.jpg", "cdnUrl": "https://cdn.jsdelivr.net/gh/zuizui46/gbm@main/images/…",
      "thumb": "images/nature/nature-misty-forest-0a1b2c.thumb.webp", "thumbCdnUrl": "…",
      "width": 2400, "height": 1600, "bytes": 512345, "sha256": "…", "tags": ["fog", "trees"]
    }
  ]
}
```

`sources` also lists Unsplash, Pexels and Pixabay (`inLibrary: false`): their licences let people use a photo in their
own videos but forbid copying their photos into a library like this one, so they are only links.

Rebuild: `python3 scripts/build-images.py [--dry-run] [--sheets DIR]` (needs Pillow). Collections and search words are
in `COLLECTIONS`; photos taken out after review are in `EXCLUDE`. `--sheets` writes one contact sheet per collection.
