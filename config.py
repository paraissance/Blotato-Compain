"""Agent Broker Coach — 1-week social campaign configuration.

Schedule: 4 time blocks/day (11 PM, 4 AM, 8 AM, 7 PM) on Pakistan time.
Each block = 4 image posts + 2 videos = 16 image posts + 8 videos per brand/day.
Designs rotate automatically across the day (see images.NUM_TEMPLATES) and the
small set of rendered videos is reused across all video slots (see run.py).
Content recycles, so the calendar never runs empty (see run.py --days).

All posting times below are in YOUR local timezone (Pakistan / Asia/Karachi).
There is deliberately NO US timezone logic in the posting path.
"""

TIMEZONE = "Asia/Karachi"   # your local time (Pakistan, UTC+5)
GEN_MODEL = "claude-sonnet-4-6"

# "photo"   = real Pexels stock photo + bold headline (needs PEXELS_API_KEY)  <-- current
# "blotato" = Blotato AI visuals (templates; can glitch/double text)
# "card"    = plain branded text card (no key)
IMAGE_MODE = "photo"

# Blotato visual template UUIDs — run `python run.py templates` to list yours,
# then paste the bare UUIDs here.
BLOTATO_IMAGE_TEMPLATE = ""   # not used in photo mode
# AI Video with AI Voice — makes the 1 video per session:
BLOTATO_VIDEO_TEMPLATE = ""   # AI-voice DISABLED — both video slots are unique slides videos
VISUAL_CREATE_SLEEP = 12      # seconds between visual jobs (raise if rate-limited)

MEDIA_REQUIRED = {"instagram", "youtube"}

# 4 time blocks a day (11 PM, 4 AM, 8 AM, 7 PM) in YOUR local time (Pakistan).
# Each block = 4 image posts (:00, :03, :06, :09) + 2 UNIQUE slides videos (:12, :15)
#            = 16 image posts + 8 videos per brand per day.
# (AutismWorks posts 2 min later via slot_offset_min, so the two brands never collide.)
_BLOCKS = ["23", "04", "08", "19"]
_IMG_MIN = ["00", "03", "06", "09"]   # 4 image slots per block
_VID_MIN = ["12", "15"]               # 2 video slots per block
SESSIONS = [f"{h}:{m}" for h in _BLOCKS for m in _IMG_MIN + _VID_MIN]
VIDEO_SESSIONS = [f"{h}:{m}" for h in _BLOCKS for m in _VID_MIN]   # the 2 videos in each block
VOICE_SESSIONS = []                              # AI-voice disabled
SLIDES_SESSIONS = list(VIDEO_SESSIONS)           # BOTH video slots (:12 and :15) = slides videos

# --- Platform-specific Blotato target fields (verified against Blotato API docs) ---
# TikTok requires the full flag set; AI-generated video must be disclosed (isAiGenerated).
TIKTOK_TARGET = {
    "privacyLevel": "PUBLIC_TO_EVERYONE",
    "disabledComments": False, "disabledDuet": False, "disabledStitch": False,
    "isBrandedContent": False, "isYourBrand": False, "isAiGenerated": True,
}
# YouTube posts as a public Short. A per-post title is set at publish time from the
# post headline (see run.py); these are just the defaults.
YOUTUBE_TARGET = {
    "privacyStatus": "public", "shouldNotifySubscribers": False, "isMadeForKids": False,
}

BRANDS = {
    "agent_broker_coach": {
        "name": "Agent Broker Coach",
        "phone": "",   # optional: shows on ABC designs, e.g. "(360) 555-0142"
        "slot_offset_min": 0,
        "profile": "brands/agent_broker_coach.md",
        "website": "https://agentbrokercoach.com",
        "platforms": {
            # platform     account id          page / target id                 posts? videos?
            "facebook":  {"account_id": "25990", "target": {"pageId": "108505075402700"}, "posts": True,  "videos": True,  "slots": SESSIONS},
            "instagram": {"account_id": "53897", "target": {},                            "posts": True,  "videos": True,  "slots": SESSIONS},
            "linkedin":  {"account_id": "17253", "target": {"pageId": "28835376"},         "posts": True,  "videos": False, "slots": SESSIONS},
            "youtube":   {"account_id": "32756", "target": dict(YOUTUBE_TARGET),         "posts": False, "videos": True,  "slots": SESSIONS},
            "tiktok":    {"account_id": "47152", "target": dict(TIKTOK_TARGET),          "posts": False, "videos": True,  "slots": SESSIONS},
        },
    },
}


# ---------------------------------------------------------------------------
# AutismWorks is currently DISABLED (running Agent Broker Coach only).
# To turn it back on, paste this entry back inside BRANDS above:
#   "autismworks": {
#       "name": "AutismWorks",
#       "slot_offset_min": 2,
#       "profile": "brands/autismworks.md",
#       "website": "https://autismworks.com",
#       "platforms": {
#           "facebook": {"account_id": "25990", "target": {"pageId": "675145015966083"}, "posts": True, "videos": True, "slots": SESSIONS},
#           "youtube":  {"account_id": "28081", "target": dict(YOUTUBE_TARGET),          "posts": False, "videos": True, "slots": SESSIONS},
#       },
#   },


# ---------------------------------------------------------------------------
# Saved for the next business pair (Phase 2) — same Facebook account 25990:
#   Tyler McNamer (FB page):      567546559923089
#   Population One (FB page):     447186555354031
#   X / @jmcnamer (account):      15780
# Add these as their own BRANDS entries when we expand past Phase 1.
# ---------------------------------------------------------------------------
