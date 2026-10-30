"""Generate bulk, per-platform content for one brand using Claude.

Reads the brand voice profile (brands/*.md), asks Claude for N distinct post
ideas, each rendered for every enabled text platform, and writes a draft JSON
into content/ for review before publishing.
"""

import json
import os
import re
import requests

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
TEXT_PLATFORMS = ["facebook", "instagram", "twitter", "pinterest"]  # youtube = video, handled separately


def _call_claude(system, user, model, max_tokens=4000):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("Missing ANTHROPIC_API_KEY in your .env file.")
    r = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=120,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Anthropic API {r.status_code}: {r.text}")
    data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    # keep only the JSON object (model sometimes adds stray text around it)
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b != -1 and b > a:
        text = text[a:b + 1]
    # strict=False allows literal line breaks inside strings (captions have them)
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", text)        # drop trailing commas
        return json.loads(cleaned, strict=False)


def _batch(brand_key, profile, platforms, n, avoid, model):
    avoid_txt = ""
    if avoid:
        joined = "; ".join(avoid[-120:])
        avoid_txt = ("\n\nALREADY USED — do NOT repeat or lightly reword any of these "
                     "ideas or headlines:\n" + joined)
    system = (
        "You are a world-class direct-response copywriter (think Halbert, Ogilvy, "
        "Schwartz, Sugarman) writing scroll-stopping social posts. Rules you live by: "
        "the FIRST line is a hook that earns the second; write to ONE person like a text "
        "from a friend; specifics beat generalities; clarity beats cleverness; one idea + "
        "one clear next step per post; benefits the reader feels, not features. Plain words, "
        "short sentences, ~7th-grade reading level. Follow the brand profile and its hard "
        "rules exactly. Every post must be genuinely DIFFERENT from the others and from the "
        "already-used list — different hook type, angle, and wording. Output ONLY valid JSON."
    )
    user = f'''BRAND PROFILE
=============
{profile}

TASK
====
Write {n} DISTINCT, ready-to-publish posts, each rendered for: {", ".join(platforms)}.

MAKE EACH ONE EXCELLENT:
- Start with a real hook (bold claim, sharp question, myth-bust, mistake, or
  mini-story). No warm-up. The opening line must stop the scroll.
- Mirror the audience's own words/pains from the profile.
- Be specific and concrete (a number, a step, a vivid detail) — never fabricate
  stats, names, or testimonials.
- End with ONE clear, low-friction next step (vary the CTA).
- Rotate hook types and angles across the batch so nothing feels samey.

PER-PLATFORM:
- facebook: 2-4 short conversational sentences. Hook line, value, soft CTA + website. 2-4 hashtags max.
- instagram: punchy hook line, then 2-4 short lines with line breaks, then CTA. EXACTLY 3-5 hashtags (Instagram hard max is 5 — never more).
- twitter: <=270 chars, one sharp idea, 1-2 hashtags.
- pinterest: keyword-rich title (<=95 chars) + helpful body + 3-5 hashtags.

HASHTAGS: pull a smart MIX from the brand pool — a couple big-reach, a couple
niche, plus the branded one. Instagram MUST have 5 or fewer. Match
the per-platform counts above. Lowercase, no spaces.{avoid_txt}

Return ONLY this JSON:
{{
  "posts": [
    {{
      "id": "{brand_key[:2]}-0001",
      "theme": "short label",
      "headline": "<=8 words, punchy bold image-card line (this goes ON the image)",
      "image_prompt": "one-line ideal image description",
      "image_url": "",
      "variants": {{
        "facebook":  {{"text": "...", "hashtags": ["#..."]}},
        "instagram": {{"text": "...", "hashtags": ["#..."]}},
        "twitter":   {{"text": "...", "hashtags": ["#..."]}},
        "pinterest": {{"title": "...", "text": "...", "hashtags": ["#..."]}}
      }},
      "status": "draft"
    }}
  ]
}}
Only include platform keys from: {", ".join(platforms)}.'''
    raw = _call_claude(system, user, model, max_tokens=8000)
    return _parse_json(raw).get("posts", [])


def generate(brand_key, brand_cfg, count, model):
    with open(brand_cfg["profile"], "r", encoding="utf-8") as f:
        profile = f.read()
    platforms = [p for p in TEXT_PLATFORMS if p in brand_cfg["platforms"]]

    # Seed the avoid-list from the persistent cross-run ledger so a NEW week's
    # posts never repeat (or lightly reword) headlines already published before.
    try:
        import state
        prior_used = state.get_used()
    except Exception:
        state, prior_used = None, []

    posts, avoid, attempts = [], list(prior_used), 0
    while len(posts) < count and attempts < count // 6 + 8:
        attempts += 1
        need = min(12, count - len(posts))
        try:
            batch = _batch(brand_key, profile, platforms, need, avoid, model)
        except Exception as e:
            print(f"    (one batch failed, retrying: {str(e)[:60]})")
            continue   # try another batch instead of giving up
        if not batch:
            continue
        for p in batch:
            posts.append(p)
            avoid.append(p.get("headline", ""))
        print(f"    ...{len(posts)}/{count} fresh posts")

    if not posts:
        raise RuntimeError("AI returned no usable posts after several tries.")

    # renumber ids sequentially
    for i, p in enumerate(posts, 1):
        p["id"] = f"{brand_key[:2]}-{i:04d}"
    parsed = {"brand": brand_key, "posts": posts}

    # remember these headlines so next week's run avoids repeating them
    if state is not None:
        try:
            state.add_used([p.get("headline", "") for p in posts])
        except Exception:
            pass

    os.makedirs("content", exist_ok=True)
    out_path = os.path.join("content", f"{brand_key}_drafts.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    return out_path, len(posts)
