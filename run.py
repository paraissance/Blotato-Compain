#!/usr/bin/env python3
"""Phase 1 social automation CLI for McNamer Real Estate + Tyler McNamer (Author).

Usage:
  python run.py accounts                         # list connected Blotato accounts + IDs
  python run.py subaccounts <accountId>          # show pageId / boardId / playlistId
  python run.py generate --brand all --count 7   # write draft content via Claude
  python run.py publish  --brand all --dry-run   # preview the exact Blotato payloads
  python run.py publish  --brand all             # schedule everything into Blotato
"""

import argparse
import itertools
import json
import os
import random
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import config
from blotato_client import BlotatoClient
import generator


def _client():
    return BlotatoClient(os.environ.get("BLOTATO_API_KEY"))


def _brands(arg):
    if arg == "all":
        return list(config.BRANDS.items())
    if arg not in config.BRANDS:
        sys.exit(f"Unknown brand '{arg}'. Choices: all, {', '.join(config.BRANDS)}")
    return [(arg, config.BRANDS[arg])]


# ---------------------------------------------------------------- discovery
def cmd_accounts(_):
    data = _client().list_accounts()
    print(json.dumps(data, indent=2))
    print("\n# Paste the relevant accountId into config.py for each platform.")


def cmd_subaccounts(args):
    data = _client().list_subaccounts(args.account_id)
    print(json.dumps(data, indent=2))
    print("\n# Use pageId (Facebook), boardId (Pinterest), playlistId (YouTube) in config.py.")


# ---------------------------------------------------------------- generate
def cmd_generate(args):
    for key, cfg in _brands(args.brand):
        print(f"Generating {args.count} ideas for {cfg['name']} ...")
        path, n = generator.generate(key, cfg, args.count, config.GEN_MODEL)
        print(f"  -> {n} posts written to {path}")
    print("\nReview the drafts, then run a --dry-run publish.")


# ---------------------------------------------------------------- publish
def _slot_stream(slots, start_day):
    """Yield (date, 'HH:MM') forever, advancing day after each day's slots."""
    day = start_day
    while True:
        for s in sorted(slots):
            yield day, s
        day += timedelta(days=1)


def _iso(day, hhmm, tz, offset_min=0):
    h, m = map(int, hhmm.split(":"))
    dt = datetime.combine(day, dtime(h, m), tzinfo=ZoneInfo(tz))
    if offset_min:
        dt += timedelta(minutes=offset_min)
    return dt.isoformat()


def _dt(day, hhmm, tz, offset_min=0):
    h, m = map(int, hhmm.split(":"))
    dt = datetime.combine(day, dtime(h, m), tzinfo=ZoneInfo(tz))
    if offset_min:
        dt += timedelta(minutes=offset_min)
    return dt


def _cap_hashtags(text, limit):
    """Keep only the first `limit` hashtags anywhere in the text; drop the rest."""
    import re
    count = [0]

    def repl(m):
        count[0] += 1
        return m.group(0) if count[0] <= limit else ""
    out = re.sub(r"#\w+", repl, text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


# platform hashtag ceilings (Blotato enforces some of these)
TAG_LIMIT = {"instagram": 5, "twitter": 2, "pinterest": 5, "facebook": 10}


def _compose(variant, platform):
    limit = TAG_LIMIT.get(platform)
    if platform == "pinterest":
        title = variant.get("title", "")
        body = variant.get("text", "")
        tags_list = variant.get("hashtags", [])
        if limit:
            tags_list = tags_list[:limit]
        tags = " ".join(tags_list)
        text = "\n\n".join(x for x in [title, body, tags] if x)
    else:
        body = variant.get("text", "")
        tags_list = variant.get("hashtags", [])
        if limit:
            tags_list = tags_list[:limit]
        tags = " ".join(tags_list)
        text = (body + ("\n\n" + tags if tags else "")).strip()
    if limit:
        text = _cap_hashtags(text, limit)   # also catches hashtags inside the body
    return text


IMAGE_PLATFORMS = {"facebook", "instagram", "linkedin"}  # a still card satisfies these


def _recipe_count(brand_key):
    """How many distinct design styles exist for a brand."""
    try:
        import designs
        return max(1, len(designs.RECIPES.get(brand_key, designs.RECIPES["agent_broker_coach"])))
    except Exception:
        return 12


def _recipe_perm(day_index, run_offset, n):
    """A deterministic shuffled order of style indices for a given day. Different
    day -> different order; different run (offset) -> different order again."""
    order = list(range(n))
    random.Random((day_index + 1) * 1009 + run_offset * 31 + 7).shuffle(order)
    return order


def cmd_publish(args):
    import images, media
    now_local = datetime.now(ZoneInfo(config.TIMEZONE))
    start_day = (
        datetime.strptime(args.start, "%Y-%m-%d").date()
        if getattr(args, "start", None) else now_local.date()
    )
    client = None if args.dry_run else _client()
    cards_dir = os.path.join("content", "cards")
    os.makedirs(cards_dir, exist_ok=True)
    only = args.platform
    days = max(1, args.days)
    totals = {"scheduled": 0, "skipped": 0, "errors": 0}
    upload_cache = {}  # card path -> Blotato URL, so identical cards upload once

    run_offset = getattr(args, "offset", 0)
    for key, cfg in _brands(args.brand):
        photo_seq = run_offset  # shifts design + photo each run so content stays fresh
        path = os.path.join("content", f"{key}_drafts.json")
        if not os.path.exists(path):
            print(f"[skip] no drafts for {key} (run generate first)")
            continue
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        all_posts = doc.get("posts", [])
        slides_urls = doc.get("slides_urls", [])   # brand-level slides-video pool

        print(f"\n=== {cfg['name']} ===")
        for plat, pcfg in cfg["platforms"].items():
            if only and plat != only:
                continue
            if not pcfg.get("account_id"):
                continue
            # posts usable on this platform (reuse the facebook caption if no
            # platform-specific one exists, so Instagram/X work from one source)
            plist = [p for p in all_posts
                     if plat in p.get("variants", {}) or "facebook" in p.get("variants", {})]
            if not plist:
                continue
            only_video = getattr(args, "only_video", False)
            skip_video = getattr(args, "skip_video", False)
            wants_posts = pcfg.get("posts", True)
            wants_videos = pcfg.get("videos", True)
            # Per-platform routing (honors the posts/videos flags in config):
            #   image pass (skip_video) -> only platforms that take image posts
            #   video pass (only_video) -> only platforms that take videos
            if skip_video and not wants_posts:
                continue   # e.g. YouTube / TikTok during the image-post pass
            if only_video and not wants_videos:
                continue   # e.g. LinkedIn during the video pass

            slots = sorted(pcfg.get("slots", ["09:00"]))
            video_times = set(getattr(config, "VIDEO_SESSIONS", []))
            # A SMALL pool of rendered videos is reused across every video slot
            # (8 video slots/day would be far too many to render fresh each run).
            # Captions stay varied: each video slot draws a different caption from
            # the evening pool but reuses one of the few rendered MP4 URLs.
            video_urls = [p["video_url"] for p in plist if p.get("video_url")]
            # Reserve a chunk of posts as the video-caption pool, kept separate from
            # the image-post captions so a video never duplicates that day's images.
            n_reserve = max(len(video_urls), 24)   # bigger video-caption pool so videos vary too
            if len(plist) > n_reserve + 4:
                evening_pool = plist[-n_reserve:]   # distinct captions for videos
                ilist = plist[:-n_reserve]          # captions for image posts
            else:
                evening_pool = plist
                ilist = plist

            # How many of each per day, and how many total we want for `days`.
            day_times = [h for h in slots if h not in video_times]
            eve_times = [h for h in slots if h in video_times]
            img_cap = days * max(1, len(day_times))
            eve_cap = days * max(1, len(eve_times))

            # Build every FUTURE slot over a generous window, sorted by time, so
            # posts roll forward past any times that already passed today. This
            # guarantees a full `days` worth of image posts no matter when you run.
            future = []
            for d in range(days + 4):
                day = start_day + timedelta(days=d)
                for hhmm in slots:
                    dt = _dt(day, hhmm, config.TIMEZONE, cfg.get("slot_offset_min", 0))
                    if dt > now_local + timedelta(minutes=2):
                        future.append((dt, day, hhmm, hhmm in video_times))
            future.sort(key=lambda x: x[0])
            img_slots = [(dy, hh) for (_, dy, hh, ev) in future if not ev][:img_cap]
            eve_slots = [(dy, hh) for (_, dy, hh, ev) in future if ev][:eve_cap]

            if only_video:
                todo = [(dy, hh, True) for (dy, hh) in eve_slots]
            elif skip_video:
                todo = [(dy, hh, False) for (dy, hh) in img_slots]
            else:
                merged = ([(dy, hh, True) for (dy, hh) in eve_slots]
                          + [(dy, hh, False) for (dy, hh) in img_slots])
                todo = [(dy, hh, ev) for (dy, hh, ev) in merged]

            idx = 0
            eve_i = 0            # caption rotation for video slots
            voice_i = 0          # AI-voice pool rotation (uses ALL rendered voice videos)
            slides_i = 0         # slides pool rotation (uses ALL rendered slides videos)
            nrec = _recipe_count(key)
            day_img_k = {}       # per-day image counter -> shuffled style order
            for day, hhmm, is_evening in todo:
                # belt-and-suspenders routing for the merged (plain publish) path
                if is_evening and not wants_videos:
                    continue
                if not is_evening and not wants_posts:
                    continue
                if True:
                    vid_url = None
                    vsrc = ""
                    rec_idx = None
                    day_shift = (day - start_day).days
                    if is_evening:
                        post = evening_pool[eve_i % len(evening_pool)]   # caption for the video
                        eve_i += 1
                        # BOTH video slots (:12 and :15) are UNIQUE slides videos.
                        # slides_i counts video slots in time order, so each slot gets
                        # its OWN video (slides_urls[k]) — no video is ever reused.
                        if slides_urls:
                            vsrc = "slides"
                            vid_url = slides_urls[slides_i % len(slides_urls)]
                            slides_i += 1
                        is_video = bool(vid_url)
                    else:
                        post = ilist[(idx + run_offset) % len(ilist)]  # daytime image content
                        idx += 1
                        is_video = False
                        # style: walk a per-day SHUFFLED order of the design recipes so
                        # each day's images use a different spread of styles (and a
                        # different order day-to-day). Photos still vary by photo_seq.
                        k = day_img_k.get(day_shift, 0)
                        day_img_k[day_shift] = k + 1
                        rec_idx = _recipe_perm(day_shift, run_offset, nrec)[k % nrec]
                    variant = post["variants"].get(plat) or post["variants"]["facebook"]
                    when = _iso(day, hhmm, config.TIMEZONE, cfg.get("slot_offset_min", 0))
                    text = _compose(variant, plat)
                    style = rec_idx if rec_idx is not None else idx   # design style for this image
                    has_url = bool(post.get("image_url"))
                    wants_card = (not is_video and not has_url
                                  and plat in IMAGE_PLATFORMS and not args.no_cards)

                    # In Blotato mode the visual must be generated first (run
                    # `python run.py visuals`). Don't silently fall back to cards.
                    if config.IMAGE_MODE == "blotato" and not is_video and not has_url:
                        print(f"  [skip] {post['id']}: no Blotato visual yet — run: python run.py visuals")
                        totals["skipped"] += 1
                        continue

                    if args.dry_run:
                        if is_video:
                            note = f"VIDEO:{vsrc}" if vsrc else "VIDEO"
                        elif has_url:
                            note = "img(url)"
                        elif wants_card:
                            headline = post.get("headline") or text[:80]
                            card = os.path.join(cards_dir, f"{key}_{post['id']}_t{style}.png")
                            if not os.path.exists(card):
                                media.build_image(config.IMAGE_MODE, key, cfg["name"], headline,
                                                  cfg["website"], post.get("keywords"), card, photo_seq,
                                                  recipe_idx=style)
                            note = f"{config.IMAGE_MODE}{style}"
                        elif is_evening:
                            note = "VIDEO(pending render)"
                        else:
                            note = "text"
                        print(f"  [{plat}] {when}  {post['id']}  ({note})")
                        continue

                    try:
                        media_urls = []
                        did_upload = False
                        if is_video:
                            media_urls = [vid_url]
                        elif has_url:
                            media_urls = [post["image_url"]]
                        elif wants_card:
                            headline = post.get("headline") or text[:80]
                            # photo_seq keeps advancing so the PHOTO is always different;
                            # rec_idx gives this image its (per-day shuffled) STYLE.
                            gidx = photo_seq
                            photo_seq += 1
                            card = os.path.join(cards_dir, f"{key}_{post['id']}_n{gidx}.png")
                            if not os.path.exists(card):
                                media.build_image(config.IMAGE_MODE, key, cfg["name"], headline,
                                                  cfg["website"], post.get("keywords"), card, gidx,
                                                  recipe_idx=style)
                            url = client.upload_local_image(card)
                            media_urls = [url]
                            did_upload = True
                        # Per-post target tweaks for the new platforms (copy so the
                        # shared config target dict is never mutated).
                        target = dict(pcfg.get("target") or {})
                        send_text = text
                        if plat == "youtube":
                            if not target.get("title"):
                                yt = (post.get("headline") or text or cfg["name"]).strip()
                                target["title"] = (yt[:95] or cfg["name"])
                            if "#shorts" not in send_text.lower():
                                send_text = (send_text + "\n\n#Shorts").strip()
                        client.create_post(
                            account_id=pcfg["account_id"], platform=plat, text=send_text,
                            media_urls=media_urls, target=target,
                            scheduled_time=when,
                        )
                        totals["scheduled"] += 1
                        kind = "video" if is_video else f"design{style}"
                        print(f"  [ok] {plat} {when} {post['id']} {kind}")
                        # pace fresh uploads under Blotato's 10 media/min limit
                        time.sleep(7 if did_upload else 2)
                    except Exception as e:
                        totals["errors"] += 1
                        print(f"  [ERR] {plat} {post['id']}: {str(e)[:160]}")
                        time.sleep(3)

    if args.dry_run:
        print("\nDry run only — nothing sent. Card previews are in content/cards/.")
    else:
        print(f"\nDone. Scheduled {totals['scheduled']}, "
              f"skipped {totals['skipped']}, errors {totals['errors']}.")


def cmd_templates(args):
    data = _client().list_templates()
    items = data.get("items") or data.get("data") or []
    if not items:
        print(json.dumps(data, indent=2)); return
    print("Blotato visual templates in your account:\n")
    for t in items:
        name = t.get("name") or t.get("title") or ""
        desc = (t.get("description") or "")[:60]
        print(f"  {t.get('id')}\n    {name} — {desc}\n")
    print("Paste an image template UUID into BLOTATO_IMAGE_TEMPLATE and a video one\n"
          "into BLOTATO_VIDEO_TEMPLATE in config.py.")


def _auto_pick_templates(client):
    """Pick an image + video template from the account when config is blank.
    Prefer a single quote-card for images (not a slideshow), a simple clip for video."""
    data = client.list_templates()
    items = data.get("items") or data.get("data") or []

    def text_of(t):
        return (str(t.get("id") or "") + " " + (t.get("name") or t.get("title") or "")
                + " " + (t.get("description") or "")).lower()

    img = vid = None
    # image: best = quote/tweet card; avoid slideshow/video
    for t in items:
        tid, s = t.get("id"), text_of(t)
        if tid and img is None and ("quote" in s or "card" in s) and "video" not in s:
            img = tid
    if img is None:  # next best: a still image template that isn't a slideshow/video
        for t in items:
            tid, s = t.get("id"), text_of(t)
            if tid and ("image" in s) and "slideshow" not in s and "video" not in s:
                img = tid; break
    if img is None and items:        # fallback: first template
        img = items[0].get("id")

    # video: a video/reel/story/slideshow template
    for t in items:
        tid, s = t.get("id"), text_of(t)
        if tid and any(k in s for k in ("video", "reel", "short", "story", "slideshow", "faceless")):
            vid = tid; break
    return img, vid


def cmd_visuals(args):
    client = _client()
    img_t = config.BLOTATO_IMAGE_TEMPLATE.strip()
    vid_t = config.BLOTATO_VIDEO_TEMPLATE.strip()
    do_images = (config.IMAGE_MODE == "blotato")   # photo/card make images elsewhere

    if do_images and not img_t:
        print("No image template set in config.py — auto-picking from your account...")
        try:
            auto_img, auto_vid = _auto_pick_templates(client)
        except Exception as e:
            sys.exit(f"Could not read your Blotato templates: {str(e)[:150]}")
        img_t = auto_img or ""
        if not vid_t:
            vid_t = auto_vid or ""
        print(f"  image template: {img_t}")
        print(f"  video template: {vid_t or '(none)'}\n")

    if not do_images and not vid_t:
        print("Nothing to generate (photo mode, no video template set). Skipping.")
        return

    for key, cfg in _brands(args.brand):
        path = os.path.join("content", f"{key}_drafts.json")
        if not os.path.exists(path):
            print(f"[skip] no drafts for {key}"); continue
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        posts = doc.get("posts", [])
        print(f"\n=== {cfg['name']}: generating videos ===" if not do_images
              else f"\n=== {cfg['name']}: generating Blotato visuals ===")
        vmade = 0
        # make videos from the END of the list so they are DIFFERENT posts than
        # the ones used as image content (which are taken from the front)
        ordered = posts if do_images else list(reversed(posts))
        for post in ordered:
            headline = post.get("headline") or ""
            caption = (post.get("variants", {}).get("facebook", {}) or {}).get("text", "")

            if do_images and img_t and not post.get("image_url"):
                prompt = (f"A polished, modern square social media quote card for {cfg['name']}. "
                          f"Headline text: \"{headline}\". Clean, professional, on-brand. "
                          f"Show {cfg['website']} small at the bottom.")
                try:
                    print(f"  image {post['id']} ...", flush=True)
                    post["image_url"] = client.generate_visual(img_t, prompt, title=f"{key}-{post['id']}-img")
                    print(f"    -> {post['image_url']}")
                except Exception as e:
                    print(f"    [ERR] {str(e)[:130]}")
                time.sleep(config.VISUAL_CREATE_SLEEP)

            if vid_t and vmade < args.videos and not post.get("video_url"):
                prompt = f"A short, engaging social video for {cfg['name']} about: {caption}"
                try:
                    print(f"  video {post['id']} ... (a few minutes)", flush=True)
                    post["video_url"] = client.generate_visual(vid_t, prompt, poll=10, timeout=900,
                                                               title=f"{key}-{post['id']}-vid")
                    print(f"    -> {post['video_url']}")
                    vmade += 1
                except Exception as e:
                    print(f"    [ERR] {str(e)[:130]}")
                time.sleep(config.VISUAL_CREATE_SLEEP)

            with open(path, "w", encoding="utf-8") as f:  # save after each (resumable)
                json.dump(doc, f, indent=2, ensure_ascii=False)
        print(f"  done ({vmade} videos)")


def _render_slides(brand_keys, n, client):
    """Render n UNIQUE slides videos per brand and upload each to Blotato, saving
    the public URLs into the brand's drafts file as `slides_urls`.

    Every video is built from a DIFFERENT content post (unique script) rendered in
    a ROTATING design look, so no two videos share the same content OR the same
    design across the whole run (see slides_video.LOOKS / script_from_post)."""
    import slides_video
    if not slides_video.ffmpeg_ok():
        print("  [!] ffmpeg not available, so the slides videos could not be made.\n"
              "      Fix once with:  pip install imageio-ffmpeg")
        return
    th_of = {}
    os.makedirs(os.path.join("content", "slides"), exist_ok=True)
    looks = slides_video.LOOKS
    for key, cfg in brand_keys:
        path = os.path.join("content", f"{key}_drafts.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        else:
            doc = {"posts": []}
        posts = doc.get("posts", [])
        if not posts:
            print(f"  [skip] no posts for {cfg['name']} — run generate first."); continue
        th = slides_video.vtheme(key)
        urls = []
        print(f"  Rendering {n} UNIQUE videos for {cfg['name']} "
              f"(distinct content + rotating design each)...", flush=True)
        for v in range(n):
            post = posts[v % len(posts)]           # unique content, walks the pool
            look = looks[v % len(looks)]           # rotating design look
            out = os.path.join("content", "slides", f"{key}_v{v:03d}.mp4")
            try:
                script = slides_video.script_from_post(key, th, post, look, idx=v)
                slides_video.render(key, out, script=script, variant=v)
                url = client.upload_local_video(out)
                urls.append(url)
                if (v + 1) % 8 == 0 or v == n - 1:
                    print(f"    {v + 1}/{n} done", flush=True)
                time.sleep(7)                      # pace under Blotato's upload limit
            except Exception as e:
                print(f"    [ERR] video {v}: {str(e)[:140]}")
        doc["slides_urls"] = urls
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        if urls:
            print(f"  OK — {len(urls)} unique videos ready for {cfg['name']}.")
        else:
            print(f"  [!] No videos produced for {cfg['name']} — check errors above.")


def cmd_slides(args):
    """Render + upload ONLY the slides-style videos (video slot 2), so you can
    confirm they work before a full run. Usage: python run.py slides"""
    _render_slides(_brands(args.brand), args.slides, _client())


def cmd_schedules(args):
    """Debug: show the raw shape of scheduled posts so we can map the id field."""
    client = _client()
    data = client.list_schedules(limit=5)
    items = data.get("items") or []
    print(f"count: {data.get('count')}   items on this page: {len(items)}")
    print("cursor:", data.get("cursor"))
    print("\n--- first item(s), raw ---")
    print(json.dumps(items[:2], indent=2)[:2500])


def cmd_clear(args):
    client = _client()
    print("Finding scheduled posts in your Blotato calendar...")
    ids = client.all_schedule_ids()
    if not ids:
        print("Calendar is already empty — nothing to delete.")
        return
    print(f"Found {len(ids)} scheduled posts.")
    if not args.yes:
        ans = input(f"Delete ALL {len(ids)} scheduled posts? This cannot be undone. (yes/no): ").strip().lower()
        if ans not in ("y", "yes"):
            print("Cancelled — nothing deleted.")
            return
    deleted, errors = 0, 0
    for sid in ids:
        try:
            client.delete_schedule(sid)
            deleted += 1
            if deleted % 10 == 0:
                print(f"  deleted {deleted}/{len(ids)}...")
            time.sleep(0.3)
        except Exception as e:
            errors += 1
            print(f"  [ERR] {sid}: {str(e)[:300]}")
            time.sleep(1)
    print(f"\nDone. Deleted {deleted}, errors {errors}. Calendar cleared.")


def cmd_go(args):
    """One shot: write fresh posts -> clear -> schedule photos -> make videos
    -> add videos. With an Anthropic key, every run writes brand-new posts so
    the content is genuinely fresh (different wording, not just reordered)."""
    import argparse as _ap
    import shutil
    import state
    platforms = [p.strip() for p in args.platform.split(",") if p.strip()]
    plist_label = " + ".join(platforms)
    off = state.get_offset()

    missing = []
    try:
        import cv2  # noqa: F401
    except Exception:
        missing.append("clear/face-safe photos")
    try:
        import slides_video
        if not slides_video.ffmpeg_ok():
            missing.append("the slides video (video slot 2)")
    except Exception:
        missing.append("the slides video (video slot 2)")
    if missing:
        print("Note: to enable " + " and ".join(missing) + ", run this ONCE:\n"
              "      pip install -r requirements.txt\n")

    # fresh image cache each run
    try:
        shutil.rmtree(os.path.join("content", "cards"))
    except OSError:
        pass

    fresh = bool(os.environ.get("ANTHROPIC_API_KEY")) and not getattr(args, "no_fresh", False)
    if fresh:
        cap = getattr(args, "fresh_cap", 120)
        # New volume = 16 image posts/brand/day + a separate pool of video captions.
        # Generate enough that image captions rarely repeat across the week.
        count = min(args.days * 16 + 8, cap)
        print(f"Step 1 of 5 — writing {count} brand-new posts per brand with AI "
              f"(this takes a minute)...\n")
        ok = False
        for key, cfg in _brands("all"):
            try:
                print(f"  {cfg['name']}:")
                path, n = generator.generate(key, cfg, count, config.GEN_MODEL)
                print(f"  -> {n} fresh posts\n")
                ok = ok or n > 0
            except Exception as e:
                print(f"  (couldn't write fresh posts: {str(e)[:90]})")
                print("   -> using existing posts instead. Check your ANTHROPIC_API_KEY.\n")
        if ok:
            off = 0  # brand-new content, start at the top
    else:
        print("Step 1 of 5 — using existing posts (no Anthropic key set, or --no-fresh).\n")

    if getattr(args, "clear", False):
        print("Step 2 of 4 — clearing the Blotato calendar (--clear was passed)...\n")
        cmd_clear(_ap.Namespace(yes=True))
    else:
        print("Keeping your existing scheduled posts (not clearing). "
              "Run 'python run.py clear' yourself if you want to wipe them.\n")

    print(f"\nStep 2 of 4 — scheduling the image posts "
          f"(16/day across 4 blocks: 11 PM, 4 AM, 8 AM, 7 PM PK) ({plist_label})...\n")
    for plat in platforms:
        cmd_publish(_ap.Namespace(brand="all", platform=plat, dry_run=False, no_cards=False,
                                  start=getattr(args, "start", None), days=args.days,
                                  skip_video=True, only_video=False, offset=off))

    # BOTH video slots are unique slides videos now (AI-voice disabled).
    # One distinct video per video slot = days * (video slots/day).
    per_day_videos = len(getattr(config, "VIDEO_SESSIONS", [])) or 8
    n_needed = args.days * per_day_videos
    if getattr(args, "max_videos", 0):
        n_needed = min(n_needed, args.max_videos)
    est_min = round(n_needed * 0.55)   # ~24s render + ~7s upload per video
    print(f"\nStep 3 of 4 — rendering {n_needed} UNIQUE videos per brand "
          f"(distinct content + rotating design; ~{est_min} min)...\n")
    try:
        _render_slides(_brands("all"), n_needed, _client())
    except Exception as e:
        print(f"  (couldn't render videos: {str(e)[:120]})")

    print(f"\nStep 4 of 4 — scheduling the video slots (2 unique videos per block) "
          f"({plist_label})...\n")
    for plat in platforms:
        cmd_publish(_ap.Namespace(brand="all", platform=plat, dry_run=False, no_cards=False,
                                  start=getattr(args, "start", None), days=args.days,
                                  skip_video=False, only_video=True, offset=off))

    if not fresh:
        state.bump_offset(5)   # jump styles+photos so a re-run looks clearly different
        # even without AI generation, remember what went out so a later AI run
        # (with an Anthropic key) won't reword this week's headlines next week.
        try:
            for _key, _cfg in _brands("all"):
                _p = os.path.join("content", f"{_key}_drafts.json")
                if os.path.exists(_p):
                    with open(_p, encoding="utf-8") as _f:
                        _doc = json.load(_f)
                    state.add_used([q.get("headline", "") for q in _doc.get("posts", [])])
        except Exception:
            pass
    print("\nAll done. Open Blotato -> Calendar and refresh.")


def main():
    p = argparse.ArgumentParser(description="Phase 1 social automation")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("accounts").set_defaults(func=cmd_accounts)

    sub.add_parser("templates").set_defaults(func=cmd_templates)

    sub.add_parser("schedules").set_defaults(func=cmd_schedules)

    go = sub.add_parser("go")
    go.add_argument("--days", type=int, default=7)
    go.add_argument("--platform", default="facebook,instagram,linkedin,youtube,tiktok")
    go.add_argument("--videos", type=int, default=0, help="(unused — AI-voice is disabled; every video slot now gets its own unique slides video)")
    go.add_argument("--slides", type=int, default=0, help="(unused — video count is auto = days x 8, one unique video per slot)")
    go.add_argument("--max-videos", type=int, default=0, help="optional cap on how many unique videos to render (0 = no cap = days x 8)")
    go.add_argument("--no-slides", dest="slides", action="store_const", const=0, help="skip the slides-style videos")
    go.add_argument("--no-fresh", action="store_true", help="reuse existing posts (don't write new ones)")
    go.add_argument("--clear", action="store_true", help="ALSO wipe the Blotato calendar first (off by default — otherwise existing posts are left alone)")
    go.add_argument("--fresh-cap", type=int, default=120, help="max new posts to write per brand per run (lower this to save time/tokens)")
    go.add_argument("--start", default=None, help="force a start date YYYY-MM-DD (Pakistan time). Default: today.")
    go.set_defaults(func=cmd_go)

    clr = sub.add_parser("clear")
    clr.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    clr.set_defaults(func=cmd_clear)

    vis = sub.add_parser("visuals")
    vis.add_argument("--brand", default="all")
    vis.add_argument("--videos", type=int, default=3, help="how many video clips per brand")
    vis.set_defaults(func=cmd_visuals)

    sl = sub.add_parser("slides", help="render + upload ONLY the slides videos (video slot 2) to test them")
    sl.add_argument("--brand", default="all")
    sl.add_argument("--slides", type=int, default=4, help="how many distinct slides videos per brand")
    sl.set_defaults(func=cmd_slides)

    sp = sub.add_parser("subaccounts")
    sp.add_argument("account_id")
    sp.set_defaults(func=cmd_subaccounts)

    g = sub.add_parser("generate")
    g.add_argument("--brand", default="all")
    g.add_argument("--count", type=int, default=7)
    g.set_defaults(func=cmd_generate)

    pub = sub.add_parser("publish")
    pub.add_argument("--brand", default="all")
    pub.add_argument("--dry-run", action="store_true")
    pub.add_argument("--platform", help="only this platform, e.g. facebook")
    pub.add_argument("--days", type=int, default=3, help="how many days of slots to fill (content recycles)")
    pub.add_argument("--no-cards", action="store_true", help="don't auto-generate image cards")
    pub.add_argument("--start", help="YYYY-MM-DD (default: tomorrow)")
    pub.set_defaults(func=cmd_publish)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
