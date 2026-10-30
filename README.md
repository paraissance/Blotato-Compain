# Agent Broker Coach — 1-Week Social Campaign

Automated, on-brand posts and videos for **Agent Broker Coach**, scheduled to
Blotato on YOUR (Pakistan) clock. A real photo background with your bold
headline on it, plus two video types per block. One week, no repeats.

- **4 blocks/day** — 11 PM, 4 AM, 8 AM, 7 PM (Pakistan time)
- **Each block** — 4 image posts (:00 :03 :06 :09) + 2 UNIQUE slides videos (:12, :15)
- **Per day** — 16 images + 8 videos
- **Per week** — 112 images + 56 videos
- **Images →** Facebook, Instagram, LinkedIn   •   **Videos →** Facebook, Instagram, YouTube, TikTok

## What's new in this build (v2.1.2)
- **144 unique posts** in the pool → a full 7-day week runs with **zero repeated
  headlines** (112 image slots, all distinct). Video captions draw from a
  separate 24-post pool.
- **No repeats week-over-week.** With an `ANTHROPIC_API_KEY` set, each `go` run
  writes brand-new posts and a persistent ledger stops it re-using any headline
  from a previous week. (Ledger lives in `state.json`.)
- **Image text overlap fixed.** Headlines now always fit their zone and never
  collide with the name / button / website line — verified across every layout,
  even with long lines.
- **Every video is unique.** AI-voice is off — BOTH video slots (:12 and :15)
  are now slides videos, and each slot gets its OWN freshly-rendered video:
  a different content post (unique script) rendered in a rotating design look.
  No two videos share the same content OR the same design across the week/month.
- **9 distinct design looks** (different backgrounds, left/center layouts, and
  scene structures) rotate across the run.
- **Higher video quality** (CRF 18, 1080×1920, 30 fps).

## Setup (once)
```
pip install -r requirements.txt
copy .env.example .env
```
In `.env` add:
- `BLOTATO_API_KEY`   (required)
- `PEXELS_API_KEY`    (required for photos — free, instant at pexels.com/api)
- `ANTHROPIC_API_KEY` (recommended — writes fresh posts each week + powers no-repeat)

## Pre-flight (test the video render + Blotato key)
```
python run.py slides
```
4 URLs printed = Blotato key + ffmpeg/slides render all working.
401 = bad/expired `BLOTATO_API_KEY`.

## Run the full week
```
python run.py go --days 7
```
This runs 4 steps: write fresh posts → schedule all images → render every video
(one unique video per slot) → schedule all video slots.

> **`go` does NOT clear your calendar.** Your already-scheduled posts are left
> alone. To wipe them, run `python run.py clear` yourself (or add `--clear` to
> `go` if you want it to wipe first).
>
> Video count = days × 8. A 7-day run renders **56 unique videos** (~25-30 min,
> render + upload). A 30-day run is ~240 videos — expect it to run a while; leave
> it going or cap it with `--max-videos N`.

> Heads-up: step 2 **clears the Blotato calendar first** — back up anything you
> want to keep. Uploads pace ~7s apart, so leave the terminal open until it's done.

## Running from JodyOS (Claude Code routine)
JodyOS (Social Media → Agent Broker Coach → "Run a campaign week") starts a
Claude Code routine on this repository. The routine runs
`python run.py go --days N` in the cloud, then commits `state.json` and
`content/agent_broker_coach_drafts.json` back to `main` so next week never
repeats a headline. The keys (`BLOTATO_API_KEY`, `PEXELS_API_KEY`,
`ANTHROPIC_API_KEY`) live in the routine's cloud environment, never in this
repository. Rendered images and videos are not committed.

## Notes
- **AI-voice is disabled** (`BLOTATO_VIDEO_TEMPLATE = ""`). If you ever want a
  talking-head video slot, the HeyGen avatar path is the upgrade (see the notes
  from our earlier session).
- **Custom music:** drop royalty-free mp3/m4a/wav into `assets/music/` (never
  copyrighted songs); they're used automatically, rotating across the videos.
