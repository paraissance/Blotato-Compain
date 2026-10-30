"""Picks how each post's image is made:

  IMAGE_MODE = "photo" -> real Pexels photo + modern headline overlay
  IMAGE_MODE = "card"  -> branded text card (no API key needed)

Photo mode needs PEXELS_API_KEY. If it's missing or a fetch fails, this falls
back to a branded card so a post is never blocked.

Agent Broker Coach uses three rotating agent-style designs:
  0 Spotlight (Jody photo)   1 Coach card (Jody photo)   2 Property card (home)
Drop Jody's headshot in  assets/jody.jpg  and designs 0 & 1 use it; otherwise a
professional stock portrait stands in.
"""

import os
import images


def _abc_image(brand_key, brand_name, headline, website, keywords, out_path, idx, pexels, recipe_idx=None):
    import designs
    phone = ""
    try:
        import config
        phone = config.BRANDS.get(brand_key, {}).get("phone", "")
    except Exception:
        pass
    designs.build(idx, brand_key, headline, website, out_path, phone=phone, pexels=pexels, recipe_idx=recipe_idx)
    return out_path


def build_image(mode, brand_key, brand_name, headline, website, keywords, out_path, idx, recipe_idx=None):
    pexels = os.environ.get("PEXELS_API_KEY")
    if mode == "photo":
        try:
            if brand_key in ("agent_broker_coach", "autismworks"):
                return _abc_image(brand_key, brand_name, headline, website,
                                  keywords, out_path, idx, pexels, recipe_idx=recipe_idx)
            if pexels and keywords:
                import photos
                raw = out_path.replace(".png", "_raw.jpg")
                photos.fetch_photo(keywords, pexels, raw, variant=idx)
                photos.compose(raw, brand_key, brand_name, headline, website, out_path, style=idx)
                try:
                    os.remove(raw)
                except OSError:
                    pass
                return out_path
        except Exception as e:
            print(f"      (photo->card fallback: {str(e)[:80]})")
    images.make_card(brand_key, brand_name, headline, website, out_path, template=idx)
    return out_path
