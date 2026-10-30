# SESSION CHANGELOG — 4-block schedule + LinkedIn/YouTube/TikTok

## v2.1.2 — `go` no longer auto-clears the calendar — 2026-08-25

Per client: scheduling a run should NOT delete already-scheduled posts. Deletion should only happen
when the client explicitly runs the clear command.

- cmd_go no longer calls cmd_clear automatically. By default it leaves the existing Blotato calendar
  untouched and just adds the new week's posts/videos.
- Deleting is now manual-only:  python run.py clear   (add --yes to skip the confirm prompt).
- Optional: `python run.py go --clear` will still wipe first, for anyone who wants the old behavior.
- go is now a 4-step flow (write posts -> schedule images -> render videos -> schedule videos).
- README + START-HERE updated to say go does not clear, and how to clear manually.

## v2.1.1 — Photo posts: real-estate only (fixed off-topic stock image) — 2026-08-25

Client flagged an inappropriate stock photo (a romantic Christmas couple) on the 4th image style.
Cause: that style ("other" recipes) searches Pexels live, and the query "happy couple holding keys
new home" matched "happy couple" and returned a romance stock shot instead of a real-estate scene.

- Rewrote the 4 ABC photo queries to strict real-estate subjects:
    other_hero     -> "real estate agent shaking hands with client"
    other_property -> "modern luxury house exterior"
    other_split    -> "real estate agent showing home to buyers"
    other_frame    -> "bright modern living room interior"
- Added a safety filter in photos.fetch_photo (_safe_query): strips romance/holiday/lifestyle words
  (couple, kiss, wedding, christmas, santa, beach, model, etc.) and guarantees a real-estate anchor
  (agent, house, home, property, interior, key, office...). Anything off-topic falls back to a safe
  "real estate house exterior" search. Verified with unit tests.
- Net: the 3 Jody cut-out styles are unchanged; the 1 photo style now only ever pulls real-estate imagery.

## v2.1.0 — Every video unique; AI-voice removed — 2026-08-25

Per client: both video slots should be slides-style (no AI-voice), and every video must be
different in BOTH design and content — no two the same across a week or a month.

- AI-VOICE OFF: config.BLOTATO_VIDEO_TEMPLATE = "" and VOICE_SESSIONS = []. SLIDES_SESSIONS now
  covers BOTH video slots (:12 and :15). cmd_go no longer renders/schedules any Blotato AI-voice video.
- UNIQUE VIDEO PER SLOT: _render_slides now renders N = days x 8 UNIQUE videos (a 7-day week = 56).
  Each video is built from a DIFFERENT content post (unique script via slides_video.script_from_post)
  rendered in a ROTATING design look. cmd_publish assigns each video slot its own URL in time order
  (slides_urls[k]) with NO reuse — verified: 56 slots -> 56 distinct videos, zero repeats.
- 9 DESIGN LOOKS: slides_video.LOOKS defines 9 visually distinct templates — different backgrounds
  (cream / dark / navy / gradient / glow / gold-hero), left vs center alignment, and different scene
  sequences (hook / quote / proof-line / feature-card / outro). Statement and card scenes are now
  background- and alignment-parameterized. Feature cards rotate independently (CARD_BANK) so the card
  scene varies too. Rendered 6 looks x 6 posts and eyeballed them: clearly different designs, unique copy.
- Content each video reads from the 144-post pool, so a full week's 56 videos never repeat content.
  A 30-day run (240 slots) reuses posts but always paired with a rotating look + rotating card, so no two
  rendered videos are identical; regenerate posts (Anthropic key) for fully-fresh month-over-month copy.
- RENDER COST: unique-per-slot means real render time. ~24s render + ~7s upload per video =>
  ~25-30 min for a 7-day run (56 videos). go prints an estimate; --max-videos N caps it for testing.
- Quality unchanged from v2.0.0 (1080x1920, 30fps, CRF 18).

## v2.0.0 — Agent Broker Coach 1-week campaign (renamed from phase1-social) — 2026-08-10

Scope: Agent Broker Coach ONLY (AutismWorks stays disabled; config kept as comment).

Fixed / added this build:
- CONTENT POOL: expanded to 144 unique posts (headline + FB + IG variants, IG hashtags capped at 5).
  A full 7-day run schedules 112 image slots with ZERO repeated headlines. Video captions draw from
  a separate 24-post reserve. Verified by simulation (0 repeats) and a live dry-run.
- NO REPEAT WEEK-OVER-WEEK: added a persistent used-headline ledger in state.py (get_used/add_used).
  generator.py seeds its avoid-list from the ledger and records new headlines after every run, so a
  fresh weekly `go` (with ANTHROPIC_API_KEY) never re-words a previous week's posts. A no-fresh run
  also records what shipped, so a later AI run still skips it.
- IMAGE TEXT OVERLAP: hardened designs._fitw to guarantee the headline block fits its zone (finer
  step, lower floor, tightened leading as a last resort). Added _img_head() at the single build()
  choke point to keep image headlines short/punchy (first sentence, word/char cap, no trailing
  filler words). Tightened other_hero so the headline can never collide with the website line.
  Re-rendered all 12 layouts with long headlines — clean.
- VIDEO VARIETY ("videos use same content"): slides script bank grown to 12 hooks / 12 lines /
  6 feature cards (from 5/5/3); cards rotate independently. `go` now renders 6 AI-voice + 7 slides
  videos by default (was 4/4) — roughly one distinct slides video per day.
- SLIDES QUALITY: encoder bumped to CRF 18 / preset medium / high profile, keyint pinned; still
  1080x1920 @ 30fps. Verified a real render (16.8s, valid mp4).
- PACKAGE: renamed to agent-broker-coach-week; README, START.bat, and config header updated to the
  ABC-only 1-week campaign. Removed stray state.json / card cache from the package.

Note on AI-voice video quality: the :12 AI-voice clips are rendered by Blotato's AI-story-video
template (BLOTATO_VIDEO_TEMPLATE). Their fidelity is a Blotato-side setting, not something this
toolkit renders. The real quality upgrade for a Jody talking-head is the HeyGen avatar path wired
into a new :18 slot (needs a Creator web plan to build the avatar + a separate HeyGen API wallet
for the daily renders; avatar_id + voice_id + HEYGEN_API_KEY).


This build wired in the new schedule and the three new platforms. The operator
workflow is unchanged: copy `.env` out → delete old folder → unzip this →
paste `.env` back → `python run.py go --days 1`.

## What changed in this build ✅

1. **New 4-block schedule (Pakistan time)** — `config.py`
   - Blocks at **11:00 PM, 4:00 AM, 8:00 AM, 7:00 PM**.
   - Each block = **4 image posts** (:00, :03, :06, :09) + **2 videos** (:12, :15).
   - = **16 image posts + 8 videos per brand per day**.
   - `SESSIONS` (24 times) and `VIDEO_SESSIONS` (8 times) are now generated from
     `_BLOCKS`/`_IMG_MIN`/`_VID_MIN` — change those lists to retune spacing.
   - AutismWorks still posts 2 min after ABC (`slot_offset_min`), so no collisions.

2. **Per-platform routing now honored** — `run.py`
   - Image posts go ONLY to platforms with `posts: true` → ABC: Facebook,
     Instagram, **LinkedIn**; AW: Facebook.
   - Videos go ONLY to platforms with `videos: true` → ABC: Facebook, Instagram,
     **YouTube**, **TikTok**; AW: Facebook, YouTube.
   - Replaced the old crude `MEDIA_REQUIRED` skip (which silently dropped YouTube
     entirely). `MEDIA_REQUIRED` is now unused but left in config harmlessly.

3. **New platforms enabled by default** — `run.py`
   - `go --platform` default is now
     `facebook,instagram,linkedin,youtube,tiktok`.
   - LinkedIn added to `IMAGE_PLATFORMS`, so it gets a real branded image card.

4. **Verified Blotato target fields for the new platforms** — `config.py`
   - **TikTok** (`TIKTOK_TARGET`): privacyLevel + disabledComments/Duet/Stitch +
     isBrandedContent/isYourBrand + **isAiGenerated:true** (AI video disclosed).
   - **YouTube** (`YOUTUBE_TARGET`): privacyStatus=public, shouldNotifySubscribers,
     isMadeForKids=false. A **per-post `title`** is set at publish time from the
     post headline, and **`#Shorts`** is appended to the caption.
   - **LinkedIn**: company-page `pageId` 28835376 (already correct).

5. **Bugfix: target booleans were being dropped** — `blotato_client.py`
   - `create_post` previously stripped any falsy target value (`if v`), which
     would have deleted TikTok's `false` flags. Now strips only `None`/`""`,
     keeping `False`/`0`.

6. **Video rotation (volume control)** — `run.py`
   - Only a small set of videos is rendered (`go --videos`, default **4**) and
     **reused across all 8 daily video slots**, so a daily run doesn't take hours.
   - Captions stay varied: each video slot pulls a different caption from a
     reserved caption pool but reuses one of the few rendered MP4 URLs.

7. **Fresh-content volume scaled up** — `run.py`
   - `go` now writes `days*16 + 8` posts/brand (cap raised to 120) so image
     captions rarely repeat across a 7-day run. Lower with `--fresh-cap N` to
     save time/tokens (at the cost of more repetition).

8. Images are still scheduled **before** videos (steps 3 then 5 in `go`), Jody
   design rotation still starts at index 0, IG hashtags still capped at 5,
   timezone still strictly Asia/Karachi, roll-forward still on. None regressed.

## Still PENDING (not in this build) ⬅️ next session

1. **2nd "slides-style" video** — the operator will send an example. Right now
   BOTH video slots in each block use the AI-voice video pool (a working
   placeholder). When the slides generator exists, wire video slot #2
   (the `:15` time in each block) to it. The seam: in `run.py`'s evening loop,
   the two `VIDEO_SESSIONS` minutes per block (`:12`, `:15`) can be split by
   minute to choose which video pool to draw from.
2. **Post content changes** — operator mentioned changes TBD. `generator.py`
   was left essentially untouched so those changes don't collide.
3. **US reference column (cosmetic)** — confirm noon vs midnight. 11-hour offset
   → 11:00 PM PK = 12:00 PM (noon) US. Spreadsheet-only; posting is PK time.
4. **Live test of the new platforms** — the Blotato target fields match the
   current API docs, but the first real run to LinkedIn/YouTube/TikTok should be
   watched (1-day test) in case an account needs a field tweak (e.g. YouTube
   title length, TikTok privacy for unaudited apps may force SELF_ONLY).

## Quick test plan for the operator
```
python run.py go --days 1     # watch the 5 steps; confirm calendar fills
```
Then check the Blotato calendar: ABC should show image posts on Facebook +
Instagram + LinkedIn, and videos on Facebook + Instagram + YouTube + TikTok.
If a platform errors, the others still schedule (errors are printed per post).

---

## Update — face-safe photo treatment (people photos)

Photos of people had the brand color (navy/teal) duotone washing over faces.
Now the brand overlay is kept OFF faces:

- `designs.py` detects faces (OpenCV **YuNet** model bundled at
  `assets/face_detection_yunet.onnx`, ~230 KB; Haar cascades as a fallback) and
  restores the natural photo over each face, so faces stay clear and skin-toned.
- The bottom text scrim in `other_hero` is also lifted off faces.
- **Home/property photos are unchanged** — no faces detected means the full
  duotone treatment stays exactly as before.
- Jody cut-out designs and typographic cards are untouched (they don't use the
  photo duotone path).

**New dependency:** `opencv-python-headless` (added to `requirements.txt`).
After swapping in this folder, run **once**:
```
pip install -r requirements.txt
```
If OpenCV isn't installed the toolkit still runs — it just falls back to the old
full-duotone look until you install it (the `go` command prints a reminder).

---

## Update — 2nd video type: slides-style promo video

Each block has two video slots. They are now two different kinds of video:

- **Slot 1 (`:12`)** — the AI-voice Blotato video (unchanged).
- **Slot 2 (`:15`)** — a NEW **slides-style promo video**, brand-themed, built to
  match the kinetic-typography reference: bold statements with one handwritten
  script accent word, a glassy feature card that slides up over a brand
  gradient, and a logo outro — set to a soft music bed. 1080×1920, ~17s, 30fps.

New / changed:
- `slides_video.py` (new) — the promo-video engine. Renders Pillow frames piped
  to ffmpeg. Per-brand copy + colors (ABC navy/gold, AutismWorks teal/spectrum)
  in `default_script()`; `--slides N` renders N variants that rotate across the
  four `:15` slots each day.
- `assets/fonts/Caveat-Bold.ttf` (new, OFL) — the script accent font.
- `blotato_client.py` — `upload_local_video()` (uploads the rendered mp4 to
  Blotato and returns a public URL; mp4/mov content-types added).
- `config.py` — `VOICE_SESSIONS` (the `:12` times) and `SLIDES_SESSIONS`
  (the `:15` times).
- `run.py` — new Step 5 renders + uploads the slides pool (`slides_urls` saved
  per brand); the video scheduler now picks slot 1 from the AI-voice pool and
  slot 2 from the slides pool. `--slides` (default 2) and `--no-slides`.

**Requires ffmpeg on PATH.** Windows: download from ffmpeg.org and add it to
PATH. If ffmpeg is missing, the slides step is skipped and the `:15` slot simply
reuses the AI-voice video (nothing breaks).

**Music:** a soft ambient bed is generated automatically. To use your own track
instead, drop an mp3 in `assets/music/` and pass it through (or tell me and I'll
wire a per-brand track). Keep any music you add license-cleared.

First live run tip: watch the first slides post on each platform (YouTube title
length / TikTok privacy), same as the other video type.
---

## Update — Agent Broker Coach only

AutismWorks is now disabled. `config.BRANDS` contains only Agent Broker Coach,
and the AutismWorks drafts/profile files were removed. The AutismWorks platform
block is preserved as a comment in `config.py` if you ever want to switch it back
on. Everything (posts, AI-voice videos, slides videos) now runs for ABC only.

Run lengths — same command, just change `--days`:
```
python run.py go --days 1      # one day
python run.py go --days 7      # one week
python run.py go --days 30     # one month
```
All three are verified: a 30-day run fills 480 image slots + 240 video slots
(120 AI-voice on the :12 slots, 120 slides on the :15 slots) across the month,
recycling the written content. For more caption variety on the 30-day run, add
`--fresh-cap 200` (writes more unique posts; costs a bit more time/AI).
---

## Update — fresher content (fixed repeating videos & image styles)

Fixed the main cause of duplicate-looking posts:

- **Videos were repeating** because both video slots shared one counter — the math
  only ever used AI-voice videos #1 and #3 and a single slides video. Now each
  pool (voice / slides) has its own counter, so **every rendered video gets used**,
  and a per-day rotation means a given slot shows a different video each day.
- **Slides variety**: default is now **4** distinct slides videos per brand
  (`--slides 4`), with a bigger pool of hooks, one-liners, and feature cards so
  the four are visibly different.
- **Image styles**: each image now gets its style from a **per-day shuffled order**
  of the 12 designs, so within every 4-image block all four styles are different,
  and the daily order changes day to day. The photo keeps advancing independently,
  so photos never repeat.
- **Re-runs look different**: re-running `go` now jumps the style/photo rotation
  further, so a fresh run doesn't look like the last one. (Captions are already
  rewritten by AI on every run.)

Note: there are 12 base design styles, so a full 16-image day repeats a few styles
once — but shuffled, with different photos and captions each time. Want zero style
repeats in a day? I can add more design layouts — just ask.

For a 30-day run, the rendered videos (4 voice + 4 slides) rotate across the month;
raise `--videos`/`--slides` for more distinct videos, and `--fresh-cap` for more
distinct captions.
---

## Update — clear photos (removed the blue overlay)

The home/property and people photos no longer get the navy duotone wash. Photos
now render **clear and natural** (light polish only — mild contrast, a touch more
color, a soft vignette for depth). The brand look now comes from the card framing
— the navy panels, headline, gold accents, and website pill — not from tinting the
photo. Text-over-photo layouts still keep a small gradient behind the text so
captions stay readable.
---

## Update — FIX: the slides video (video slot 2) was not posting

Cause: the slides video is rendered with ffmpeg, and ffmpeg is almost never on
PATH on Windows. When it was missing, the slides step was skipped silently and
BOTH video slots fell back to the AI-voice video — so only one video type posted.

Fix: ffmpeg is now bundled via the pip package **imageio-ffmpeg** (added to
requirements). No manual ffmpeg install. `pip install -r requirements.txt` brings
everything (ffmpeg + OpenCV) in one go.

Also added a pre-flight test command so you can CONFIRM slot 2 before publishing:
```
python run.py slides            # renders + uploads the slides videos, prints their URLs
```
If that prints URLs, the 2nd video type is working and `go` will schedule it.

Recommended order before a 7-day publish:
```
pip install -r requirements.txt      # once
python run.py slides                 # confirm slides render + upload (prints URLs)
python run.py go --days 7            # publishes: slot 1 = AI-voice, slot 2 = slides
```
---

## Update — slides music is now clearly audible

The slides videos' sound was rendering ~13 dB too quiet (near-silent on speakers).
Fixed: the built-in bed is now a real chord progression with a soft pulse, and
ALL slides audio (built-in or your own track) is loudness-normalized to standard
social level (-16 LUFS). Verified: mean volume went from -31.5 dB to -18.4 dB.

Want your own music? Drop mp3/m4a/wav files into **assets/music/** — the slides
videos will use them automatically (rotating across variants). Use royalty-free
tracks only (Pixabay Music, Uppbeat, YouTube Audio Library).
---

## Update — slides music: upbeat produced-style track

Replaced the quiet ambient bed with a synthesized, produced-style promo track —
kick drum, hi-hats, bass pulses, plucked chord progression with a sidechain
"pump" (modern SaaS/Kajabi promo feel), loudness-normalized to a punchy social
level (mean ~ -16 dB, peaks ~ -3.5 dB). All 4 slides variants verified.
Your own tracks still override: drop mp3s in assets/music/.
