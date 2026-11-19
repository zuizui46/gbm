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
