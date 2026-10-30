"""Thin wrapper around the Blotato REST API (v2).

Docs: https://help.blotato.com/api/start
Auth: header `blotato-api-key`. Base URL: https://backend.blotato.com
Rate limits: posts 30/min, media uploads 10/min.
"""

import requests

BLOTATO_BASE = "https://backend.blotato.com"


class BlotatoClient:
    def __init__(self, api_key, base_url=BLOTATO_BASE):
        if not api_key:
            raise ValueError(
                "Missing Blotato API key. Put BLOTATO_API_KEY in your .env file."
            )
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"blotato-api-key": api_key, "Content-Type": "application/json"}
        )

    def _get(self, path):
        r = self.session.get(self.base + path, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text}")
        return r.json()

    def _post(self, path, payload):
        r = self.session.post(self.base + path, json=payload, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text}")
        return r.json()

    def _delete(self, path):
        # Blotato rejects a DELETE that carries Content-Type: application/json
        # with no body ("Body cannot be empty..."). Send it without that header.
        r = self.session.delete(
            self.base + path, headers={"Content-Type": None}, timeout=30
        )
        if r.status_code >= 400:
            raise RuntimeError(f"DELETE {path} -> {r.status_code}: {r.text}")
        return True

    # --- discovery -------------------------------------------------------
    def list_accounts(self):
        """All connected social accounts. Each item carries the accountId
        you need for posting."""
        return self._get("/v2/users/me/accounts")

    def list_subaccounts(self, account_id):
        """Per-account details: pageId (Facebook/LinkedIn),
        playlistIds (YouTube), boardId (Pinterest), etc."""
        return self._get(f"/v2/users/me/accounts/{account_id}/subaccounts")

    # --- media -----------------------------------------------------------
    def upload_media(self, url):
        """Hand Blotato a public image/video URL; it re-hosts it and returns
        a mediaUrl you can attach to a post."""
        return self._post("/v2/media", {"url": url})

    def create_presigned_upload(self, filename):
        """Step 1 of local-file upload: returns {presignedUrl, publicUrl}."""
        return self._post("/v2/media/uploads", {"filename": filename})

    def upload_local_image(self, file_path):
        """Upload a local image OR video straight to Blotato (no external
        hosting): get a presigned URL, PUT the raw bytes, return the public URL."""
        import os
        fn = os.path.basename(file_path)
        ext = fn.rsplit(".", 1)[-1].lower()
        ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "mp4": "video/mp4", "mov": "video/quicktime"}.get(
            ext, "application/octet-stream"
        )
        res = self.create_presigned_upload(fn)
        with open(file_path, "rb") as f:
            data = f.read()
        # PUT raw bytes to the presigned URL (no api-key header, not multipart)
        put = requests.put(
            res["presignedUrl"], data=data,
            headers={"Content-Type": ctype}, timeout=300,
        )
        if put.status_code >= 400:
            raise RuntimeError(f"PUT presigned -> {put.status_code}: {put.text[:200]}")
        return res["publicUrl"]

    def upload_local_video(self, file_path):
        """Upload a local mp4/mov to Blotato and return its public URL."""
        return self.upload_local_image(file_path)

    # --- posting ---------------------------------------------------------
    def create_post(
        self,
        account_id,
        platform,
        text,
        media_urls=None,
        target=None,
        scheduled_time=None,
        use_next_free_slot=False,
        additional_posts=None,
    ):
        """Create (and optionally schedule) one post on one platform.

        platform / targetType use the SAME value, e.g. 'twitter' for X.
        Pass scheduled_time as ISO 8601 with offset (e.g. 2026-06-23T09:00:00-07:00)
        OR use_next_free_slot=True to drop it in Blotato's next open calendar slot.
        """
        content = {"text": text, "mediaUrls": media_urls or [], "platform": platform}
        if additional_posts:
            content["additionalPosts"] = additional_posts

        tgt = {"targetType": platform}
        if target:
            # Strip only None/empty-string so we never send blank pageId/title,
            # but KEEP boolean False (e.g. TikTok disabledDuet:false) and 0.
            tgt.update({k: v for k, v in target.items() if v not in (None, "")})

        body = {"post": {"accountId": account_id, "content": content, "target": tgt}}
        if scheduled_time:
            body["scheduledTime"] = scheduled_time
        elif use_next_free_slot:
            body["useNextFreeSlot"] = True
        return self._post("/v2/posts", body)

    # --- AI visuals (Blotato-generated images & videos) ------------------
    def list_templates(self, fields="id,name,description"):
        """List the visual templates available in this account."""
        return self._get("/v2/videos/templates?fields=" + fields)

    @staticmethod
    def _bare_template_id(template_id):
        """Blotato wants the bare UUID, not the full '/base/v2/.../v1' path."""
        import re
        m = re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            str(template_id),
        )
        return m.group(0) if m else str(template_id)

    @staticmethod
    def _media_url(item):
        """Pull the finished media URL from a creation item, whatever it's called."""
        for k in ("mediaUrl", "url", "outputUrl", "videoUrl", "imageUrl", "output"):
            v = item.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for k in ("mediaUrls", "outputUrls", "images"):
            v = item.get(k)
            if isinstance(v, list) and v:
                first = v[0]
                if isinstance(first, str) and first.startswith("http"):
                    return first
                if isinstance(first, dict):
                    for kk in ("url", "mediaUrl", "imageUrl"):
                        if isinstance(first.get(kk), str):
                            return first[kk]
        return None

    def _template_id_candidates(self, template_id):
        """Try the id exactly as given first, then the bare UUID — Blotato
        accepts different forms for different templates."""
        tid = str(template_id)
        cands = [tid]
        bare = self._bare_template_id(tid)
        if bare != tid:
            cands.append(bare)
        return cands

    def create_visual(self, template_id, prompt, inputs=None, render=True, title=None):
        """Start a visual (image or video) from a template. AI fills the
        template inputs from `prompt`. Returns {item:{id,status}}."""
        last = None
        for tid in self._template_id_candidates(template_id):
            body = {"templateId": tid, "inputs": inputs or {}, "prompt": prompt, "render": render}
            if title:
                body["title"] = title
            try:
                return self._post("/v2/videos/from-templates", body)
            except RuntimeError as e:
                last = e
                if "404" in str(e) or "Unknown template" in str(e):
                    continue   # wrong id form — try the next candidate
                raise
        raise last or RuntimeError("template not accepted: " + str(template_id))

    def get_visual(self, visual_id):
        """Poll a visual's status. Returns {item:{id,status,mediaUrl}}."""
        return self._get("/v2/videos/creations/" + str(visual_id))

    def generate_visual(self, template_id, prompt, poll=8, timeout=720, title=None):
        """Create a visual and wait until it's rendered; return its media URL.
        Terminal states: done/completed (ok) or creation-from-template-failed."""
        import time as _t
        r = self.create_visual(template_id, prompt, title=title)
        vid = (r.get("item") or {}).get("id")
        if not vid:
            raise RuntimeError("Blotato visual: no id returned (%s)" % str(r)[:120])
        waited = 0
        done_polls = 0
        while waited < timeout:
            item = (self.get_visual(vid).get("item") or {})
            st = item.get("status", "")
            if st in ("done", "completed", "media-ready", "exporting"):
                url = self._media_url(item)
                if url:
                    return url
                done_polls += 1            # finished but URL may lag a beat
                if done_polls > 5:
                    raise RuntimeError("finished but no media url; fields=%s" % list(item.keys()))
            elif st in ("creation-from-template-failed", "failed"):
                raise RuntimeError("visual failed: " + st)
            _t.sleep(poll)
            waited += poll
        raise RuntimeError("visual timed out after %ss" % timeout)

    # --- scheduled posts (calendar) -------------------------------------
    def list_schedules(self, cursor=None, limit=50):
        """One page of upcoming (future) scheduled posts.
        Returns {items:[{id, scheduledAt, account, draft}], count, cursor}."""
        path = f"/v2/schedules?limit={limit}"
        if cursor:
            import urllib.parse
            path += "&cursor=" + urllib.parse.quote(cursor)
        return self._get(path)

    def delete_schedule(self, schedule_id):
        """Cancel one scheduled post (removes it from the calendar)."""
        return self._delete("/v2/schedules/" + str(schedule_id))

    def all_schedule_ids(self):
        """Every upcoming scheduled post id, across all pages."""
        ids, cursor = [], None
        for _ in range(200):  # safety cap
            data = self.list_schedules(cursor=cursor)
            items = data.get("items") or []
            ids += [it.get("id") for it in items if it.get("id")]
            cursor = data.get("cursor")
            if not cursor or not items:
                break
        return ids
