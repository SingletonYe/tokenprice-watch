#!/usr/bin/env python3
"""TokenPrice Watch - static site builder.

Reads the daily snapshots/change logs produced by fetch_data.py and renders a
complete static site: home, full pricing table, one page per model, one per
vendor, high-intent "cheapest API for X" pages, a daily price-change archive,
an interactive cost calculator, plus feeds, sitemap and monetization slots.

Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import shutil
import sys

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

VENDOR_NAMES = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "meta": "Meta",
    "meta-llama": "Meta Llama", "mistralai": "Mistral AI", "qwen": "Alibaba Qwen", "deepseek": "DeepSeek",
    "x-ai": "xAI", "cohere": "Cohere", "amazon": "Amazon", "microsoft": "Microsoft",
    "nvidia": "NVIDIA", "moonshotai": "Moonshot AI", "z-ai": "Z.ai", "minimax": "MiniMax",
    "ai21": "AI21 Labs", "perplexity": "Perplexity", "01-ai": "01.AI", "baidu": "Baidu",
    "tencent": "Tencent", "bytedance": "ByteDance", "ibm-granite": "IBM", "inclusionai": "InclusionAI",
    "liquid": "Liquid AI", "thudm": "THUDM", "aion-labs": "Aion Labs", "open-r1": "Open-R1",
    "nousresearch": "Nous Research", "sao10k": "Sao10K", "gryphe": "Gryphe", "undi95": "Undi95",
    "alfredpros": "AlfredPros", "anthracite-org": "Anthracite", "neversleep": "NeverSleep",
    "raifle": "Raifle", "agentica-org": "Agentica", "featherless": "Featherless",
    "switchpoint": "Switchpoint", "relace": "Relace", "arcee-ai": "Arcee AI", "infermatic": "Infermatic",
    "cognitivecomputations": "Cognitive Computations", "eva-unit-01": "EVA-Unit-01",
    "nothingiisreal": "NothingIsReal", "the-drummer": "TheDrummer", "tngtech": "TNG Technology",
    "upstage": "Upstage", "stepfun-ai": "StepFun", "kwaipilot": "Kwaipilot", "alibaba": "Alibaba",
    "sarvamai": "Sarvam AI", "opengvlab": "OpenGVLab", "eleutherai": "EleutherAI",
    "bytedance-seed": "ByteDance Seed", "rekaai": "Reka AI", "sakana": "Sakana AI",
    "thinkingmachines": "Thinking Machines", "xiaomi": "Xiaomi", "moonshot": "Moonshot AI",
    "writer": "Writer", "morph": "Morph", "poolside": "Poolside", "inception": "Inception",
    "meituan": "Meituan", "dots-studio": "Dots Studio", "elorian": "Elorian", "fireworks": "Fireworks AI",
    "inference-net": "Inference.net", "mancer": "Mancer", "moondream": "Moondream",
    "nex-agi": "Nex AGI", "openrouter": "OpenRouter", "perceptron": "Perceptron",
    "prism-ml": "Prism ML", "reflection": "Reflection", "scaledown": "ScaleDown",
    "stepfun": "StepFun", "thedrummer": "TheDrummer", "typesafe": "TypeSafe",
    "unbiased": "Unbiased", "xingchen-agi": "Xingchen AGI",
}


def vendor_key(vendor: str) -> str:
    """URL-safe provider key. `~vendor` ids are 'latest alias' routing groups."""
    if vendor.startswith("~"):
        return vendor.lstrip("~") + "-latest"
    return vendor


def esc(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def vendor_label(vendor: str) -> str:
    alias = vendor.startswith("~")
    key = vendor.lstrip("~")
    name = VENDOR_NAMES.get(key, key.replace("-", " ").title())
    return f"{name} (latest alias)" if alias else name


def money(value, per: str = "") -> str:
    """Format a USD amount compactly."""
    if value is None:
        return "—"
    if value == 0:
        return "Free"
    if value < 0.01:
        return f"${value:.4f}{per}"
    if value < 1:
        return f"${value:.3f}{per}"
    if value < 100:
        return f"${value:.2f}{per}"
    return f"${value:,.0f}{per}"


def per_m(token_price) -> float | None:
    if token_price is None:
        return None
    try:
        return float(token_price) * 1_000_000
    except (TypeError, ValueError):
        return None


def int_fmt(n) -> str:
    if n is None:
        return "—"
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "—"
    if n >= 1_000_000 and n % 1_000_000 == 0:
        return f"{n // 1_000_000}M"
    if n >= 1_000:
        return f"{n:,}"
    return str(n)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "x"


def display_name(name: str, vendor: str = "") -> str:
    """Strip the redundant "Vendor: " prefix the upstream catalogue prepends."""
    if not name:
        return name
    head, sep, tail = name.partition(": ")
    if not sep or not tail:
        return name
    candidates = {vendor.lower(), vendor.lstrip("~").lower()}
    for v in list(candidates):
        candidates.add(VENDOR_NAMES.get(v, v).lower())
    candidates.discard("")
    # "DeepSeek: DeepSeek V4 Flash" -> strip; "OpenAI: GPT-6 Astra" -> strip
    if head.lower() in candidates:
        return tail
    if head.lower().replace("-", " ") in {c.replace("-", " ") for c in candidates}:
        return tail
    return name


def page_url(path: str) -> str:
    """Flat, host-agnostic URL for a page: /models.html, /model/a/b.html.

    Directory-style URLs (/models/) only work on hosts that resolve a directory
    to its index.html. Several static hosts do not, so every deployment uses
    explicit .html paths, which work everywhere and keep canonicals unambiguous.
    """
    rel = (path or "/").strip("/")
    if rel in ("", "index.html", "index.htm"):
        return "/"
    if not rel.endswith(".html"):
        rel += ".html"
    return "/" + rel


def model_path(model_or_id) -> str:
    """Canonical URL for a model page, shared by every renderer."""
    if isinstance(model_or_id, dict):
        vendor, slug, variant = model_or_id["vendor"], model_or_id["slug"], model_or_id.get("variant", "")
    else:
        mid = str(model_or_id)
        base, _, variant = mid.partition(":")
        vendor, _, slug = base.partition("/")
    return page_url(f"/model/{vendor_key(vendor)}/{slugify(slug)}")


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def pct(part: float, whole: float) -> float:
    return 0.0 if not whole else part / whole * 100


def human_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
    except Exception:
        return iso
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def short_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
    except Exception:
        return iso
    return d.strftime("%b %-d, %Y") if hasattr(d, "strftime") else iso


# --------------------------------------------------------------------------- #
# data loading
# --------------------------------------------------------------------------- #

class Dataset:
    def __init__(self, root: pathlib.Path):
        self.root = root
        self.latest = json.loads((root / "data" / "latest.json").read_text())
        self.date: str = self.latest["date"]
        self.models: list[dict] = self.latest["models"]
        self.changes: dict = self.latest.get("changes") or {}
        self.fetched_at: str = self.latest.get("fetched_at") or ""
        self.collected: str = ""
        if self.fetched_at:
            try:
                parsed = dt.datetime.fromisoformat(self.fetched_at.replace("Z", "+00:00"))
                self.collected = parsed.astimezone(dt.timezone.utc).strftime("%H:%M UTC")
            except ValueError:
                self.collected = ""
        self.snapshots: dict[str, list[list]] = {}
        for p in sorted((root / "data" / "snapshots").glob("*.json")):
            snap = json.loads(p.read_text())
            self.snapshots[snap["date"]] = snap.get("models", [])
        self.change_days: dict[str, dict] = {}
        for p in sorted((root / "data" / "changes").glob("*.json"), reverse=True):
            day = json.loads(p.read_text())
            self.change_days[day["date"]] = day

        arch_path = root / "data" / "archive.json"
        self.archive = json.loads(arch_path.read_text()) if arch_path.exists() else []
        self.by_id = {m["id"]: m for m in self.models}
        self._prepare()

    def _prepare(self) -> None:
        for m in self.models:
            m["in1m"] = per_m(m.get("pin"))
            m["out1m"] = per_m(m.get("pout"))
            m["cache1m"] = per_m(m.get("pcr"))
            # blended cost: 3 input tokens per 1 output token (typical chat/RAG mix)
            if m["in1m"] is not None and m["out1m"] is not None:
                m["blend"] = m["in1m"] * 0.75 + m["out1m"] * 0.25
            else:
                m["blend"] = None
            m["is_free"] = bool(m["in1m"] == 0 and m["out1m"] == 0)
            m["path"] = model_path(m)
            m["dn"] = display_name(m.get("name") or m["id"], m["vendor"])
            m["iq"] = m.get("iq")
            m["ci"] = m.get("ci")
            m["value"] = (
                round(m["iq"] / m["blend"], 1)
                if m.get("iq") and m.get("blend") and m["blend"] > 0
                else None
            )

        # group variants under their base model
        self.bases: dict[str, list[dict]] = {}
        for m in self.models:
            self.bases.setdefault(m["base"], []).append(m)
        for base, group in self.bases.items():
            group.sort(key=lambda m: (m["variant"] != "", m["variant"]))
            canon = group[0]
            canon_variants = group

        self.base_models = [g[0] for g in self.bases.values()]
        for m in self.models:
            m["vk"] = vendor_key(m["vendor"])
        self.vendors: dict[str, list[dict]] = {}
        for m in self.models:
            self.vendors.setdefault(m["vk"], []).append(m)

        paid = sorted([m for m in self.base_models if m["blend"] and m["blend"] > 0], key=lambda m: m["blend"])
        self.paid_sorted = paid
        self.blend_values = [m["blend"] for m in paid]
        iqs = [m["iq"] for m in self.base_models if m.get("iq")]
        self.iq_values = iqs

    def vendor_group(self, base: str) -> list[dict]:
        return self.bases.get(base, [])

    def history(self, base: str, field: str = "blend") -> list[tuple[str, float | None]]:
        out = []
        for date in sorted(self.snapshots):
            for row in self.snapshots[date]:
                if row and row[0] == base:
                    pin, pout = row[2], row[3]
                    try:
                        v = float(pin) * 0.75e6 + float(pout) * 0.25e6 if pin is not None and pout is not None else None
                    except (TypeError, ValueError):
                        v = None
                    out.append((date, v))
                    break
        return out

    def rank_of(self, model: dict) -> dict:
        """Ranking context for a model page."""
        info: dict = {}
        paid = self.paid_sorted
        if model.get("blend") and model["blend"] > 0:
            cheaper = sum(1 for m in paid if m["blend"] < model["blend"])
            info["cost_rank"] = cheaper + 1
            info["cost_total"] = len(paid)
            info["cheaper_pct"] = round(pct(cheaper, len(paid)))
        if model.get("iq"):
            better = sum(1 for m in self.base_models if (m.get("iq") or 0) > model["iq"])
            info["iq_rank"] = better + 1
            info["iq_total"] = len(self.iq_values)
        if model.get("value"):
            higher = sum(1 for m in self.base_models if (m.get("value") or 0) > model["value"])
            info["value_rank"] = higher + 1
            info["value_total"] = sum(1 for m in self.base_models if m.get("value"))
        return info

    def alternatives(self, model: dict, limit: int = 6) -> list[dict]:
        """Similar capability, lower price."""
        pool = [m for m in self.paid_sorted if m["base"] != model["base"]]
        if model.get("iq"):
            near = [m for m in pool if m.get("iq") and abs(m["iq"] - model["iq"]) <= 4]
            cheaper = [m for m in near if model.get("blend") and m["blend"] < model["blend"]]
            if len(cheaper) >= 3:
                return cheaper[:limit]
            near.sort(key=lambda m: (-(m.get("iq") or 0), m["blend"]))
            return near[:limit]
        return pool[:limit]

    def improved(self, model: dict, limit: int = 5) -> list[dict]:
        """Slightly pricier but clearly more capable (for upgrade intent)."""
        if not model.get("iq") or not model.get("blend"):
            return []
        pool = [
            m for m in self.paid_sorted
            if m.get("iq") and m["iq"] > model["iq"] and m["blend"] <= model["blend"] * 12
        ]
        pool.sort(key=lambda m: (m["blend"] / max(m["iq"] / model["iq"], 0.01)))
        return pool[:limit]


# --------------------------------------------------------------------------- #
# page shell
# --------------------------------------------------------------------------- #

class Builder:
    def __init__(self, data: Dataset, cfg: dict, out: pathlib.Path, base_url: str,
                 rss_href: str = "/rss.xml"):
        self.d = data
        self.rss_href = rss_href
        self.cfg = cfg
        self.out = out
        self.base_url = base_url.rstrip("/")
        self.assets = pathlib.Path(__file__).resolve().parent.parent / "assets"
        # content-hashed asset names (cache-busting, and required by the host)
        self.hashed: dict[str, str] = {}
        for f in sorted(self.assets.glob("*")):
            if f.is_file() and f.suffix in (".css", ".js", ".png", ".jpg", ".svg", ".webp"):
                digest = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
                self.hashed[f.name] = f"{f.stem}-{digest}{f.suffix}"
        self.pages: list[tuple[str, str, str]] = []  # (url_path, title, priority)
        self.site = cfg.get("site_name", "TokenPrice Watch")

    # ---------- url helpers ----------
    def url(self, path: str = "/") -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}" if self.base_url else path

    def rel(self, path: str = "/") -> str:
        """Root-relative link that works on any host."""
        return path if path.startswith("/") else "/" + path

    # ---------- monetization ----------
    def ad_slot(self, kind: str = "inline", label: str = "Advertisement") -> str:
        ads = self.cfg.get("adsense") or {}
        client = ads.get("client") or ""
        slot = ads.get(f"slot_{kind}") or ads.get("slot_inline") or ""
        sponsor = self.cfg.get("sponsor") or {}
        if client and slot:
            return (
                f'<aside class="ad" aria-label="{esc(label)}">'
                f'<span class="ad-tag">{esc(label)}</span>'
                f'<ins class="adsbygoogle" style="display:block" data-ad-client="{esc(client)}" '
                f'data-ad-slot="{esc(slot)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
                f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script>'
                f"</aside>"
            )
        if sponsor.get("label") and sponsor.get("url"):
            return (
                f'<aside class="ad ad-sponsor" aria-label="Sponsor">'
                f'<span class="ad-tag">Sponsored</span>'
                f'<a rel="sponsored nofollow" href="{esc(sponsor["url"])}">{esc(sponsor["label"])}</a>'
                f"</aside>"
            )
        return (
            '<aside class="ad ad-empty" aria-label="Sponsor slot available">'
            f'<span class="ad-tag">{esc(label)}</span>'
            '<span>This slot is available. Reach '
            f'<a href="mailto:{esc(self.cfg.get("contact_email", ""))}">{esc(self.cfg.get("contact_email", ""))}</a>'
            ' — <a href="/advertise.html">sponsor rates</a>.</span>'
            "</aside>"
        )

    def affiliate(self, vendor: str, fallback: str, text: str = "Try it") -> str:
        amap = (self.cfg.get("affiliates") or {}).get("map") or {}
        href = amap.get(vendor) or fallback
        sponsored = ' rel="sponsored nofollow noopener"' if amap.get(vendor) else ' rel="noopener"'
        return f'<a href="{esc(href)}"{sponsored}>{esc(text)}</a>'

    def newsletter_form(self) -> str:
        nl = self.cfg.get("newsletter") or {}
        if nl.get("action"):
            return (
                '<form class="nl" method="post" action="' + esc(nl["action"]) + '">'
                f'<p><strong>{esc(nl.get("headline"))}</strong> Daily price drops, one email. No spam.</p>'
                '<input type="email" name="email" required placeholder="you@company.com" aria-label="Email address">'
                '<button type="submit">Subscribe</button></form>'
            )
        return (
            '<div class="nl"><p><strong>' + esc(nl.get("headline") or "Get the daily price-drop email") + "</strong> "
            "Connect a newsletter provider in <code>config/site.json</code> to switch this on. "
            f'<a href="mailto:{esc(self.cfg.get("contact_email",""))}?subject=Subscribe">Subscribe by email</a> in the meantime.</p></div>'
        )

    # ---------- shell ----------
    def shell(self, *, path: str, title: str, description: str, body: str,
              canonical_path: str | None = None, jsonld: list | None = None,
              breadcrumbs: list[tuple[str, str]] | None = None, body_class: str = "") -> str:
        cfg = self.cfg
        canonical = self.url(page_url(canonical_path or path))
        ld = ""
        crumbs_ld = None
        if breadcrumbs:
            crumbs_ld = {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": name, "item": self.url(href)}
                    for i, (name, href) in enumerate(breadcrumbs)
                ],
            }
        blocks = list(jsonld or [])
        if crumbs_ld:
            blocks.append(crumbs_ld)
        blocks.append({
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": self.site,
            "url": self.url("/"),
        })
        for block in blocks:
            ld += f'<script type="application/ld+json">{json.dumps(block, separators=(",", ":"))}</script>'
        if crumbs_ld:
            ld += f'<script type="application/ld+json">{json.dumps(crumbs_ld, separators=(",", ":"))}</script>'

        ads = cfg.get("adsense") or {}
        head_ads = ""
        if ads.get("client"):
            head_ads = (
                '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                f'?client={esc(ads["client"])}" crossorigin="anonymous"></script>'
            )
        og_meta = ""
        og_src = next((n for n in self.hashed if n.startswith("og.")), None)
        if og_src:
            og_meta = (f'<meta property="og:image" content="{esc(self.url("/assets/" + self.hashed[og_src]))}">'
                       f'<meta property="og:image:width" content="1200">'
                       f'<meta property="og:image:height" content="630">'
                       f'<meta name="twitter:image" content="{esc(self.url("/assets/" + self.hashed[og_src]))}">')
        analytics = cfg.get("analytics") or {}
        head_analytics = ""
        if analytics.get("plausible_domain"):
            head_analytics += (
                '<script defer data-domain="' + esc(analytics["plausible_domain"])
                + '" src="https://plausible.io/js/script.js"></script>'
            )
        if analytics.get("cloudflare_beacon"):
            head_analytics += (
                '<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                f'data-cf-beacon=\'{{"token":"{esc(analytics["cloudflare_beacon"])}"}}\'></script>'
            )

        crumb_html = ""
        if breadcrumbs and len(breadcrumbs) > 1:
            items = "".join(
                f'<li><a href="{self.rel(href)}">{esc(name)}</a></li>' for name, href in breadcrumbs[:-1]
            )
            items += f"<li aria-current=\"page\">{esc(breadcrumbs[-1][0])}</li>"
            crumb_html = f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>'

        nav = (
            '<nav class="mainnav" aria-label="Main">'
            '<a href="/models.html">All prices</a>'
            '<a href="/cheapest.html">Cheapest</a>'
            '<a href="/changes.html">Price changes</a>'
            '<a href="/cost-calculator.html">Calculator</a>'
            "</nav>"
        )

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(self.site)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
{og_meta}
<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="alternate" type="application/rss+xml" title="{esc(self.site)} daily changes" href="{esc(self.rss_href)}">
<link rel="stylesheet" href="/assets/{self.hashed.get("style.css", "style.css")}">
<meta name="theme-color" content="#0d1117">
{head_ads}
{head_analytics}
{ld}
</head>
<body class="{esc(body_class)}">
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <div class="wrap header-inner">
    <a class="brand" href="/"><span class="brand-mark">TP</span> <span>{esc(self.site)}</span></a>
    {nav}
  </div>
  <div class="ticker"><div class="wrap"><span id="ticker">Data as of {esc(human_date(self.d.date))}{f" · collected {esc(self.d.collected)}" if self.d.collected else ""}{f" · compared with {esc(self.d.changes.get('baseline'))}" if self.d.changes.get('baseline') else ""}</span></div></div>
</header>
<main id="main" class="wrap">
{crumb_html}
{body}
</main>
<footer class="foot">
  <div class="wrap">
    <p class="foot-links">
      <a href="/models.html">All prices</a> · <a href="/cheapest.html">Cheapest APIs</a> ·
      <a href="/changes.html">Price changes</a> · <a href="/cost-calculator.html">Cost calculator</a> ·
      <a href="/methodology.html">Methodology</a> · <a href="/about.html">About</a> ·
      <a href="/advertise.html">Advertise</a> · <a href="/privacy.html">Privacy</a>
    </p>
    <p class="muted">Independent tracker. Prices are collected daily from public provider pricing
    endpoints and can change without notice — always confirm on the provider's own page before you
    make a purchasing decision. Not affiliated with any model provider.</p>
    <p class="muted">© {dt.date.today().year} {esc(self.cfg.get('owner',''))} · {esc(self.site)} ·
    <a href="{esc(self.rss_href)}">RSS</a> · <a href="/sitemap.xml">Sitemap</a></p>
  </div>
</footer>
<script src="/assets/{self.hashed.get("app.js", "app.js")}" defer></script>
</body>
</html>
"""

    def write(self, path: str, html_text: str, *, title: str = "", priority: str = "0.6") -> None:
        """Write one page. `path` may be given directory-style; output is always flat
        .html so it works on hosts that do not resolve directory indexes."""
        rel = path.strip("/")
        if rel.endswith(".html"):
            rel = rel[:-5]
        if not rel:
            target = self.out / "index.html"
        else:
            target = self.out / f"{rel}.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text)
        self.pages.append((self.url(page_url(path)), title, priority))


# --------------------------------------------------------------------------- #
# shared table renderers
# --------------------------------------------------------------------------- #

def price_cell(value, dynamic: bool = False) -> str:
    if value is None:
        return '<span class="muted">Varies</span>' if dynamic else '<span class="muted">—</span>'
    if value == 0:
        return '<span class="free">Free</span>'
    return money(value)


def model_table(models: list[dict], d: Dataset, *, limit: int | None = None,
                show_rank: bool = True, caption: str = "") -> str:
    rows = models[:limit] if limit else models
    head = (
        "<tr><th>#</th><th>Model</th><th>Provider</th><th class=\"num\">Input / 1M</th>"
        "<th class=\"num\">Output / 1M</th><th class=\"num\">Blended / 1M</th>"
        "<th class=\"num\">Context</th><th class=\"num\">Intelligence</th>"
        "<th class=\"num\">Value</th></tr>"
    )
    body_rows = []
    for i, m in enumerate(rows):
        flags = []
        if m["is_free"]:
            flags.append('<span class="badge free">free</span>')
        if m.get("reasoning"):
            flags.append('<span class="badge">reasoning</span>')
        if m.get("ctx") and m["ctx"] >= 1_000_000:
            flags.append('<span class="badge">1M ctx</span>')
        value = f"{m['value']:.1f}" if m.get("value") else '<span class="muted">—</span>'
        body_rows.append(
            "<tr>"
            f'<td class="num rank">{i + 1 if show_rank else ""}</td>'
            f'<td><a href="{esc(m["path"])}">{esc(m["name"])}</a>'
            + (" ".join(flags) if flags else "")
            + "</td>"
            f'<td>{esc(vendor_label(m["vendor"]))}</td>'
            f'<td class="num">{price_cell(m.get("in1m"))}</td>'
            f'<td class="num">{price_cell(m.get("out1m"))}</td>'
            f'<td class="num strong">{price_cell(m.get("blend"))}</td>'
            f'<td class="num">{esc(int_fmt(m.get("ctx")))}</td>'
            f'<td class="num">{m["iq"] if m.get("iq") else "—"}</td>'
            f'<td class="num">{value}</td>'
            "</tr>"
        )
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return (
        f'<div class="table-wrap"><table class="prices">{cap}<thead>{head}</thead><tbody>'
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def sparkline(points: list[tuple[str, float | None]]) -> str:
    vals = [(d, v) for d, v in points if v is not None]
    if len(vals) < 2:
        return (
            '<p class="muted">Price history starts today — the trend chart appears after the next '
            "daily update. Every snapshot is committed to the repository, so history is permanent.</p>"
        )
    w, h = 640, 120
    lo = min(v for _, v in vals)
    hi = max(v for _, v in vals)
    span = (hi - lo) or 1
    step = w / max(len(vals) - 1, 1)
    pts = " ".join(
        f"{i * step:.1f},{h - (v - lo) / span * (h - 20) - 10:.1f}" for i, (_, v) in enumerate(vals)
    )
    return (
        f'<div class="spark"><svg viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="Blended price per 1M tokens from {esc(vals[0][0])} to {esc(vals[-1][0])}" '
        f'preserveAspectRatio="none"><polyline points="{pts}" fill="none" stroke="var(--accent)" stroke-width="2"/></svg>'
        f'<div class="spark-legend"><span>{esc(vals[0][0])}: {money(vals[0][1])}</span>'
        f'<span>{esc(vals[-1][0])}: {money(vals[-1][1])}</span></div></div>'
    )


def change_rows(changes: list[dict], d: Dataset, limit: int | None = None) -> str:
    field_labels = {"pin": "Input", "pout": "Output", "pcr": "Cache read", "pcw": "Cache write"}
    if not changes:
        return '<p class="muted">No price moves recorded in this update.</p>'
    rows = []
    for c in changes[:limit] if limit else changes:
        base = c["id"].split(":")[0]
        vendor = base.partition("/")[0]
        arrow = "▼" if c["direction"] == "down" else "▲"
        cls = "down" if c["direction"] == "down" else "up"
        pct_txt = f' <span class="{cls}">{c["pct"]:+.1f}%</span>' if c.get("pct") is not None else ""

        def cell(value) -> str:
            if value is None:
                return '<span class="muted">Varies</span>'
            try:
                fv = float(value)
            except (TypeError, ValueError):
                return '<span class="muted">—</span>'
            if fv < 0:
                return '<span class="muted">Varies</span>'
            if fv == 0:
                return '<span class="free">Free</span>'
            return money(fv * 1_000_000)
        rows.append(
            "<tr>"
            f'<td><a href="{esc(model_path(c["id"])) if c["id"] in d.by_id else "/retired.html"}">'
            f'{esc(c.get("name") or c["id"])}</a></td>'
            f'<td>{esc(vendor_label(vendor))}</td>'
            f'<td>{esc(field_labels.get(c["field"], c["field"]))}</td>'
            f'<td class="num">{"Free" if c["from"] in ("0", 0) else money(float(c["from"]) * 1e6 if c["from"] is not None else None)}</td>'
            f'<td class="num strong">{"Free" if c["to"] in ("0", 0) else money(float(c["to"]) * 1e6 if c["to"] is not None else None)}</td>'
            f'<td class="num {cls}">{arrow}{pct_txt}</td>'
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="prices"><thead><tr>'
        "<th>Model</th><th>Provider</th><th>Price</th><th class=\"num\">Before /1M</th>"
        "<th class=\"num\">After /1M</th><th class=\"num\">Change</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


# --------------------------------------------------------------------------- #
# individual page builders
# --------------------------------------------------------------------------- #

def build_home(b: Builder) -> None:
    d = b.d
    ch = d.changes
    counts = ch.get("counts", {})
    paid = d.paid_sorted
    cheapest = paid[:12]
    value_leaders = sorted([m for m in d.base_models if m.get("value")], key=lambda m: -m["value"])[:12]
    smartest = sorted([m for m in d.base_models if m.get("iq")], key=lambda m: -m["iq"])[:10]
    free = sorted([m for m in d.base_models if m["is_free"]], key=lambda m: -(m.get("iq") or 0))[:8]
    newest = sorted(d.base_models, key=lambda m: m.get("created") or 0, reverse=True)[:8]

    drops = [c for c in ch.get("price_changes", []) if c["direction"] == "down"]
    hikes = [c for c in ch.get("price_changes", []) if c["direction"] == "up"]
    added = ch.get("added", [])
    removed = ch.get("removed", [])

    headline_bits = []
    if drops:
        headline_bits.append(f"{len(drops)} price cut{'s' if len(drops) != 1 else ''}")
    if hikes:
        headline_bits.append(f"{len(hikes)} increase{'s' if len(hikes) != 1 else ''}")
    if added:
        headline_bits.append(f"{len(added)} new model{'s' if len(added) != 1 else ''}")
    if removed:
        headline_bits.append(f"{len(removed)} retired")
    headline = ", ".join(headline_bits) if headline_bits else "baseline captured — no moves yet"

    body = [
        '<section class="hero">',
        f'<p class="kicker">Updated {esc(human_date(d.date))} · {d.latest["count"]} endpoints · '
        f'{len(d.bases)} models · {len(d.vendors)} providers</p>',
        "<h1>LLM API pricing, tracked daily</h1>",
        f'<p class="lede">Every model price on one page, refreshed every day at 06:17 UTC. '
        f'Today: <strong>{esc(headline)}</strong>'
        + (f", measured against the {esc(d.changes.get('baseline'))} snapshot" if d.changes.get("baseline") else "")
        + (f". This update was collected at {esc(d.collected)}; inference prices can move during the "
           "day, and each update is snapshotted so you can always check what a price was on a given date."
           if d.collected else ".")
        + "</p>",
        '<p class="hero-cta"><a class="btn" href="/models.html">See all prices</a> '
        '<a class="btn ghost" href="/cost-calculator.html">Calculate your bill</a></p>',
        "</section>",
        b.ad_slot("top", "Advertisement"),
    ]

    body.append('<section class="grid-2">')
    body.append(
        '<div class="card"><h2>Today’s price changes</h2>'
        + (change_rows(ch.get("price_changes", []), d, limit=15) if ch.get("price_changes") else
           '<p class="muted">No price moves in the last update. The tracker keeps a permanent daily '
           'snapshot of all '
           f'{d.latest["count"]} endpoints, so every future change is caught automatically.</p>')
        + '<p><a href="/changes.html">Full change log →</a></p></div>'
    )
    movers = []
    for c in (drops + hikes)[:6]:
        link = f'<a href="{esc(model_path(c["id"]))}">{esc(c.get("name") or c["id"])}</a>'
        movers.append(f'<li>{link} — {esc(c["field"])} {c["pct"]:+.1f}%</li>'
                      if c.get("pct") is not None else f"<li>{link}</li>")
    body.append(
        '<div class="card"><h2>Why track prices daily?</h2>'
        "<p>Inference prices move constantly: new snapshots launch, providers cut rates, cache tiers "
        "appear and retired models vanish. A price sheet you copied last quarter is usually wrong by "
        "10–40%. This tracker rebuilds the whole table every day and keeps the diff.</p>"
        + (f'<ul class="plain">{"".join(movers)}</ul>' if movers else "")
        + '<p><a href="/methodology.html">How the data is collected →</a></p></div>'
    )
    body.append("</section>")

    body.append(b.ad_slot("inline", "Advertisement"))
    body.append('<section class="card"><h2>Cheapest LLM APIs right now</h2>'
                '<p class="sub">Blended price assumes 3 input tokens per 1 output token — the mix most '
                'chat and RAG workloads actually run at.</p>'
                + model_table(cheapest, d) + '<p><a href="/cheapest/cheapest-llm-api.html">Full ranking →</a></p></section>')

    body.append('<section class="grid-2">')
    body.append('<div class="card"><h2>Best value: quality per dollar</h2>'
                '<p class="sub">Intelligence index ÷ blended price per 1M tokens. Higher is better.</p>'
                + model_table(value_leaders, d) + "</div>")
    body.append('<div class="card"><h2>Most capable models (any price)</h2>'
                + model_table(smartest, d) + "</div>")
    body.append("</section>")

    body.append('<section class="grid-2">')
    body.append('<div class="card"><h2>Free API models</h2>'
                + model_table(free, d) + '<p><a href="/cheapest/free-llm-apis.html">All free models →</a></p></div>')
    body.append('<div class="card"><h2>Newest models on the market</h2>'
                + model_table(newest, d) + '<p><a href="/changes.html">Release history →</a></p></div>')
    body.append("</section>")

    body.append('<section class="card"><h2>Pick by workload</h2><ul class="linkgrid">')
    for uc in USE_CASES:
        body.append(f'<li><a href="/cheapest/{uc["slug"]}.html">{esc(uc["title"])}</a>'
                    f'<span>{esc(uc["blurb"])}</span></li>')
    body.append('<li><a href="/models.html">All models</a><span>Complete pricing table, sortable in your browser.</span></li>')
    body.append("</ul></section>")

    body.append(b.newsletter_form())

    jsonld = [{
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"LLM API pricing snapshot {d.date}",
        "description": f"Daily snapshot of {d.latest['count']} LLM API endpoints with per-token pricing, context windows and benchmark indices.",
        "dateModified": d.date,
        "creator": {"@type": "Organization", "name": b.site},
        "license": b.url("/methodology.html"),
    }]
    html_text = b.shell(
        path="/", title=f"LLM API Pricing Tracker — updated daily ({short_date(d.date)})",
        description=f"Compare {len(d.bases)} LLM API models on price per 1M tokens. Updated daily; "
                    f"today: {headline}. Input, output, cache and blended costs plus a free cost calculator.",
        body="\n".join(body), jsonld=jsonld,
    )
    b.write("/", html_text, title="Home", priority="1.0")


def _paid(d): return d.paid_sorted
def _coding_pool(d):
    pool = [m for m in d.base_models if m.get("ci") and m.get("blend")]
    if not pool:
        return []
    pool.sort(key=lambda m: -m["ci"])
    return pool
def _agentic_pool(d):
    pool = [m for m in d.base_models if m.get("agi") and m.get("blend")]
    pool.sort(key=lambda m: -m["agi"])
    return pool
def _long_ctx_pool(d):
    return [m for m in d.paid_sorted if (m.get("ctx") or 0) >= 128_000]
def _mega_ctx_pool(d):
    return [m for m in d.paid_sorted if (m.get("ctx") or 0) >= 1_000_000]
def _vision_pool(d):
    return [m for m in d.paid_sorted if "image" in (m.get("in_mod") or [])]
def _reasoning_pool(d):
    return [m for m in d.paid_sorted if m.get("reasoning")]
def _free_pool(d):
    return [m for m in d.base_models if m["is_free"]]
def _value_pool(d):
    return [m for m in d.base_models if m.get("value")]
def _output_pool(d):
    return [m for m in d.paid_sorted if m.get("out1m")]
def _cache_pool(d):
    return [m for m in d.paid_sorted if m.get("cache1m") is not None]
def _batch_pool(d):
    return [m for m in d.base_models if m["variant"] == "batch" or any(
        g["variant"] == "batch" for g in d.vendor_group(m["base"]))]


USE_CASES = [
    {
        "slug": "cheapest-llm-api",
        "title": "Cheapest LLM API overall",
        "blurb": "Lowest blended cost per 1M tokens across every paid model.",
        "h1": "The cheapest LLM APIs available today",
        "intro": "Ranked by blended cost per 1M tokens (3 input tokens per output token). Free tiers are "
                 "listed separately because they usually carry rate limits and licence restrictions.",
        "filter": lambda d: d.paid_sorted,
        "key": lambda d: d.paid_sorted,
    },
    {
        "slug": "cheapest-for-coding",
        "title": "Cheapest API for coding",
        "blurb": "Best value among models with published coding benchmarks.",
        "h1": "Cheapest LLM APIs for coding",
        "intro": "Coding workloads are judged on the coding index, not on general intelligence. These are "
                 "the models that hold a coding index in the top half of the field while costing the least.",
        "filter": _coding_pool,
        "key": lambda d: sorted(_coding_pool(d), key=lambda m: m["blend"]),
    },
    {
        "slug": "cheapest-for-agents",
        "title": "Cheapest API for AI agents",
        "blurb": "Tool-calling quality per dollar for agentic loops.",
        "h1": "Cheapest LLM APIs for agents and tool calling",
        "intro": "Agents burn many small input tokens per task, so input price and cache price dominate the "
                 "bill. Ranked by blended cost among models with a published agentic index.",
        "filter": _agentic_pool,
        "key": lambda d: sorted(_agentic_pool(d), key=lambda m: m["blend"]),
    },
    {
        "slug": "cheapest-long-context",
        "title": "Cheapest long-context API",
        "blurb": "128K+ context windows at the lowest cost per token.",
        "h1": "Cheapest long-context LLM APIs (128K tokens and up)",
        "intro": "Long-context work fails on price long before it fails on capability: a single 500K-token "
                 "document can cost more than a full day of chat traffic. Cheapest first.",
        "filter": _long_ctx_pool,
        "key": lambda d: sorted(_long_ctx_pool(d), key=lambda m: m["blend"]),
    },
    {
        "slug": "cheapest-million-context",
        "title": "Cheapest 1M-token context API",
        "blurb": "Million-token context windows ranked by cost.",
        "h1": "Cheapest 1M-token context LLM APIs",
        "intro": "A million-token window lets you drop an entire repository or document set into one call. "
                 "Here is what that actually costs per 1M tokens of input.",
        "filter": _mega_ctx_pool,
        "key": lambda d: sorted(_mega_ctx_pool(d), key=lambda m: m["blend"]),
    },
    {
        "slug": "cheapest-vision",
        "title": "Cheapest vision API",
        "blurb": "Image and file understanding at the lowest price.",
        "h1": "Cheapest multimodal vision LLM APIs",
        "intro": "Models that accept images or documents as input, cheapest blended cost first.",
        "filter": _vision_pool,
        "key": lambda d: sorted(_vision_pool(d), key=lambda m: m["blend"]),
    },
    {
        "slug": "cheapest-reasoning",
        "title": "Cheapest reasoning API",
        "blurb": "Chain-of-thought models without the premium.",
        "h1": "Cheapest reasoning LLM APIs",
        "intro": "Reasoning models emit long internal token streams, so output price is what bites. These "
                 "support an explicit reasoning mode and sit at the bottom of the price range.",
        "filter": _reasoning_pool,
        "key": lambda d: sorted(_reasoning_pool(d), key=lambda m: m["blend"]),
    },
    {
        "slug": "free-llm-apis",
        "title": "Free LLM APIs",
        "blurb": "Zero-cost endpoints, ranked by capability.",
        "h1": "Free LLM APIs: zero-cost models you can use today",
        "intro": "No input or output charge. Free tiers normally carry rate limits, shared capacity and "
                 "sometimes non-commercial licence terms — check the provider's terms before shipping.",
        "filter": _free_pool,
        "key": lambda d: sorted(_free_pool(d), key=lambda m: -(m.get("iq") or 0)),
    },
    {
        "slug": "best-value-llm-api",
        "title": "Best value LLM API",
        "blurb": "Highest capability per dollar, not just the cheapest.",
        "h1": "Best value LLM APIs: capability per dollar",
        "intro": "Value = intelligence index ÷ blended price per 1M tokens. Cheap models with weak "
                 "benchmarks score badly here, which is exactly the point.",
        "filter": _value_pool,
        "key": lambda d: sorted(_value_pool(d), key=lambda m: -m["value"]),
    },
    {
        "slug": "cheapest-output-tokens",
        "title": "Cheapest output tokens",
        "blurb": "For generation-heavy workloads.",
        "h1": "Cheapest LLM APIs by output token price",
        "intro": "Summarisation, code generation and agent transcripts pay mostly for output tokens. "
                 "Ranked by output price per 1M tokens.",
        "filter": _output_pool,
        "key": lambda d: sorted(_output_pool(d), key=lambda m: m["out1m"]),
    },
    {
        "slug": "cheapest-prompt-caching",
        "title": "Cheapest prompt caching",
        "blurb": "Lowest cached-input price for repeated context.",
        "h1": "Cheapest prompt caching tiers for LLM APIs",
        "intro": "If you send the same system prompt or document on every call, cache reads are where your "
                 "bill is won. Ranked by cached input price per 1M tokens.",
        "filter": _cache_pool,
        "key": lambda d: sorted(_cache_pool(d), key=lambda m: m["cache1m"]),
    },
    {
        "slug": "cheapest-batch-api",
        "title": "Cheapest batch API",
        "blurb": "Off-peak batch pricing, roughly half the synchronous rate.",
        "h1": "Cheapest batch LLM APIs",
        "intro": "Batch endpoints trade latency for price and are the cheapest way to run overnight jobs.",
        "filter": _batch_pool,
        "key": lambda d: sorted(_batch_pool(d), key=lambda m: m["blend"]),
    },
]


def build_use_cases(b: Builder) -> None:
    d = b.d
    index_items = []
    for uc in USE_CASES:
        rows = uc["key"](d)
        pool = [m for m in rows if m.get("blend") or m["is_free"]]
        # coding: restrict to top-half coding index for a meaningful "cheapest *good*" answer
        if uc["slug"] == "cheapest-for-coding" and pool:
            cut = sorted(m["ci"] for m in pool if m.get("ci"))
            if cut:
                thresh = cut[len(cut) // 2]
                pool = [m for m in pool if (m.get("ci") or 0) >= thresh]
        if uc["slug"] == "cheapest-for-agents" and pool:
            cut = sorted(m["agi"] for m in pool if m.get("agi"))
            if cut:
                thresh = cut[len(cut) // 2]
                pool = [m for m in pool if (m.get("agi") or 0) >= thresh]

        body = [
            '<header class="page-head">',
            f"<h1>{esc(uc['h1'])}</h1>",
            f'<p class="lede">{esc(uc["intro"])}</p>',
            f'<p class="kicker">Updated {esc(human_date(d.date))} · {len(pool)} qualifying models</p>',
            "</header>",
            b.ad_slot("top", "Advertisement"),
            model_table(pool, d, limit=40),
        ]
        if len(pool) > 40:
            body.append(f'<p class="muted">Showing the 40 cheapest of {len(pool)} qualifying models. '
                        '<a href="/models.html">Open the full table</a>.</p>')
        # extra explainer content, unique per page
        best = pool[0] if pool else None
        if best:
            body.append('<section class="card prose">')
            body.append(f"<h2>What the winner costs</h2>")
            body.append(
                f"<p><strong>{esc(best['dn'])}</strong> currently leads this list. At "
                f"{money(best['in1m'])} per 1M input tokens and {money(best['out1m'])} per 1M output "
                f"tokens, a workload that processes 100M input and 25M output tokens per month bills "
                f"about <strong>{money((best['in1m'] or 0) * 100 + (best['out1m'] or 0) * 25)}</strong> "
                f"per month. The most expensive paid model in the catalogue is "
                f"{money(d.paid_sorted[-1]['blend'])} per 1M blended — "
                f"{round(d.paid_sorted[-1]['blend'] / best['blend']) if best.get('blend') else 'many'}× more.</p>"
            )
            body.append(
                "<h2>How to read this ranking</h2>"
                "<ol><li><strong>Blended price</strong> assumes three input tokens for every output token. "
                "If your mix is different, use the calculator and your own numbers.</li>"
                "<li><strong>Context window</strong> caps how much you can send per call, but long context "
                "usually costs a premium above roughly 128K tokens.</li>"
                "<li><strong>Benchmark indices</strong> come from the provider's published model metadata "
                "and are absolute published scores, not an endorsement.</li>"
                "<li><strong>Caching</strong> can cut repeat-context costs by 60–90% — see "
                '<a href="/cheapest/cheapest-prompt-caching.html">cache pricing</a>.</li></ol>'
            )
            body.append(
                '<p><a class="btn ghost" href="/cost-calculator.html">Run your own numbers →</a></p>'
            )
            body.append("</section>")
        body.append(b.ad_slot("inline", "Advertisement"))
        body.append('<section class="card"><h2>Other workload comparisons</h2><ul class="linkgrid">')
        for other in USE_CASES:
            if other["slug"] == uc["slug"]:
                continue
            body.append(f'<li><a href="/cheapest/{other["slug"]}.html">{esc(other["title"])}</a>'
                        f'<span>{esc(other["blurb"])}</span></li>')
        body.append("</ul></section>")
        body.append(b.newsletter_form())

        jsonld = [{
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": uc["h1"],
            "numberOfItems": len(pool),
            "dateModified": d.date,
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": m.get("dn") or m["name"]}
                for i, m in enumerate(pool[:40])
            ],
        }]
        title = f"{uc['title']} — ranked by price ({short_date(d.date)})"
        html_text = b.shell(
            path=f"/cheapest/{uc['slug']}.html", title=title,
            description=f"{uc['blurb']} {len(pool)} qualifying models, ranked, with cost per 1M tokens. "
                        f"Updated {d.date}.",
            body="\n".join(body),
            breadcrumbs=[("Home", "/"), ("Cheapest", "/cheapest.html"), (uc["title"], f"/cheapest/{uc['slug']}/")],
            jsonld=jsonld,
        )
        b.write(f"/cheapest/{uc['slug']}.html", html_text, title=uc["title"], priority="0.9")
        index_items.append((uc, pool))

    body = ["<h1>Cheapest LLM APIs by workload</h1>",
            '<p class="lede">The same catalogue, ranked for the job you actually have. Blended price '
            'assumes 3 input tokens per 1 output token; each page lists the full qualifying set.</p>',
            '<ul class="linkgrid">']
    for uc, pool in index_items:
        bestm = pool[0] if pool else None
        body.append(
            f'<li><a href="/cheapest/{uc["slug"]}.html">{esc(uc["title"])}</a>'
            f'<span>{esc(uc["blurb"])} · {len(pool)} models'
            + (f' — cheapest: {esc(bestm["dn"])} at {money(bestm["blend"])}/1M' if bestm and bestm.get("blend") else "")
            + "</span></li>"
        )
    body.append("</ul>")
    body.append(b.newsletter_form())
    html_text = b.shell(
        path="/cheapest.html", title="Cheapest LLM APIs by workload — daily rankings",
        description="Cheapest LLM API for coding, agents, long context, vision, reasoning, batch and "
                    "high-volume output. Ranked daily from live provider pricing.",
        body="\n".join(body), breadcrumbs=[("Home", "/"), ("Cheapest", "/cheapest.html")],
    )
    b.write("/cheapest.html", html_text, title="Cheapest APIs", priority="0.9")


def build_models_table(b: Builder) -> None:
    d = b.d
    rows = sorted(d.base_models, key=lambda m: (m.get("blend") is None, m.get("blend") or 0))
    payload = [
        {
            "i": m["id"], "n": m["name"], "v": m["vendor"], "u": m["path"],
            "a": m.get("in1m"), "o": m.get("out1m"), "b": round(m["blend"], 4) if m.get("blend") is not None else None,
            "c": m.get("ctx"), "q": m.get("iq"), "r": 1 if m.get("reasoning") else 0,
            "x": ",".join(m.get("in_mod") or []), "d": 1 if m.get("dynamic") else 0,
        }
        for m in rows
    ]
    body = [
        "<h1>All LLM API prices</h1>",
        f'<p class="lede">{len(d.models)} endpoints from {len(d.vendors)} providers, refreshed '
        f'{esc(human_date(d.date))}. Sort any column, or filter to what you need. Prices are USD per '
        f'1M tokens.</p>',
        b.ad_slot("top", "Advertisement"),
        '<div class="controls">'
        '<input id="q" type="search" placeholder="Filter by model, provider, e.g. claude" aria-label="Filter models">'
        '<label><input type="checkbox" id="f-free"> Free only</label>'
        '<label><input type="checkbox" id="f-vision"> Vision</label>'
        '<label><input type="checkbox" id="f-reason"> Reasoning</label>'
        '<label><input type="checkbox" id="f-long"> 128K+ context</label>'
        '<span class="muted" id="count"></span>'
        "</div>",
        '<div class="table-wrap"><table class="prices sortable" id="allmodels"><thead><tr>'
        '<th data-sort="n">Model</th><th data-sort="v">Provider</th>'
        '<th class="num" data-sort="a">Input /1M</th><th class="num" data-sort="o">Output /1M</th>'
        '<th class="num" data-sort="b">Blended /1M</th><th class="num" data-sort="c">Context</th>'
        '<th class="num" data-sort="q">Intelligence</th></tr></thead><tbody id="rows"></tbody></table></div>',
        '<p class="muted">Blended = 0.75 × input + 0.25 × output. Endpoint variants (batch, free, '
        'thinking) are shown on each model page. Data is collected automatically; always confirm '
        'current pricing with the provider before you commit to a contract.</p>',
        b.ad_slot("inline", "Advertisement"),
        b.newsletter_form(),
    ]
    html_text = b.shell(
        path="/models.html", title=f"All LLM API prices — {len(d.bases)} models compared ({short_date(d.date)})",
        description=f"Complete, sortable table of {len(d.models)} LLM API endpoints and their input, "
                    f"output and blended price per 1M tokens. Updated daily.",
        body="\n".join(body),
        breadcrumbs=[("Home", "/"), ("All prices", "/models.html")],
    )
    html_text = html_text.replace(
        "</body>",
        f'<script id="models-data" type="application/json">{json.dumps(payload, separators=(",", ":"))}</script>\n</body>',
    )
    b.write("/models.html", html_text, title="All prices", priority="1.0")


def build_model_pages(b: Builder) -> None:
    d = b.d
    for base, group in d.bases.items():
        canon = group[0]
        vendor = canon["vendor"]
        path = canon["path"]
        info = d.rank_of(canon)
        variants = [g for g in group if g["variant"]]
        hist = d.history(base)

        body = [
            '<header class="page-head">',
            f'<p class="kicker">{esc(vendor_label(vendor))}</p>',
            f'<h1>{esc(canon["dn"])} API pricing</h1>',
            f'<p class="lede">{money(canon["in1m"])} per 1M input tokens · '
            f'{money(canon["out1m"])} per 1M output tokens · '
            f'{esc(int_fmt(canon.get("ctx")))} context'
            + (f' · intelligence index {canon["iq"]}' if canon.get("iq") else "") + "</p>",
            "</header>",
        ]
        body.append('<section class="stats">')
        dyn = bool(canon.get("dynamic"))
        stats = [
            ("Input / 1M", price_cell(canon.get("in1m"), dyn)),
            ("Output / 1M", price_cell(canon.get("out1m"), dyn)),
            ("Blended / 1M", price_cell(canon.get("blend"), dyn)),
            ("Cache read / 1M", price_cell(canon.get("cache1m"), dyn)),
            ("Context", esc(int_fmt(canon.get("ctx")))),
            ("Max output", esc(int_fmt(canon.get("max_out")))),
            ("Intelligence", str(canon["iq"]) if canon.get("iq") else "—"),
            ("Coding index", str(canon["ci"]) if canon.get("ci") else "—"),
        ]
        for label, val in stats:
            body.append(f'<div class="stat"><span>{esc(label)}</span><strong>{val}</strong></div>')
        body.append("</section>")
        body.append(b.ad_slot("top", "Advertisement"))

        # cost table
        body.append('<section class="card"><h2>What it costs at your volume</h2>'
                    '<p class="sub">Monthly bill at a 3:1 input/output token mix. Cached input is not '
                    'assumed; if you cache a large system prompt the real bill drops sharply.</p>')
        if canon.get("in1m") is not None and canon.get("out1m") is not None:
            body.append('<div class="table-wrap"><table class="prices"><thead><tr><th>Monthly volume</th>'
                        '<th class="num">Input cost</th><th class="num">Output cost</th><th class="num">Total</th>'
                        "</tr></thead><tbody>")
            for label, tin, tout in (
                ("1M in / 0.33M out", 1, 1 / 3),
                ("10M in / 3.3M out", 10, 10 / 3),
                ("100M in / 33M out", 100, 100 / 3),
                ("1B in / 333M out", 1000, 1000 / 3),
            ):
                ic = (canon["in1m"] or 0) * tin
                oc = (canon["out1m"] or 0) * tout
                body.append(f"<tr><td>{esc(label)}</td><td class=\"num\">{money(ic)}</td>"
                            f"<td class=\"num\">{money(oc)}</td>"
                            f"<td class=\"num strong\">{money(ic + oc)}</td></tr>")
            body.append("</tbody></table></div>")
        elif dyn:
            body.append('<p class="muted">This endpoint is a <strong>router</strong>: the provider does not '
                        'publish a fixed per-token price because the cost depends on which underlying '
                        'model the request is routed to. Compare the candidate models below, or check the '
                        'provider page for routing rules.</p>')
        else:
            body.append('<p class="muted">Pricing is not published in a comparable unit for this model. '
                        'Check the provider page.</p>')
        body.append("</section>")

        # rankings
        bits = []
        if info.get("cost_rank"):
            bits.append(f'<li><strong>{ordinal(info["cost_rank"])} cheapest</strong> of {info["cost_total"]} '
                        f'paid models — cheaper than {info["cheaper_pct"]}% of the catalogue.</li>')
        if info.get("iq_rank"):
            bits.append(f'<li><strong>Intelligence rank {info["iq_rank"]} of {info["iq_total"]}</strong> '
                        f'published indices.</li>')
        if info.get("value_rank"):
            bits.append(f'<li><strong>{ordinal(info["value_rank"])} best value</strong> of '
                        f'{info["value_total"]} scoring models (capability per dollar).</li>')
        if canon.get("created"):
            created = dt.datetime.fromtimestamp(canon["created"], dt.timezone.utc).date().isoformat()
            bits.append(f"<li>First listed <strong>{esc(created)}</strong>.</li>")
        if bits:
            body.append('<section class="card"><h2>Where it stands</h2><ul class="plain">'
                        + "".join(bits) + "</ul></section>")

        if variants:
            body.append('<section class="card"><h2>Endpoint variants and their prices</h2>'
                        '<p class="sub">The same model routed differently: batch endpoints trade latency '
                        'for a discount, free endpoints carry rate limits.</p>'
                        '<div class="table-wrap"><table class="prices"><thead><tr><th>Endpoint</th>'
                        '<th class="num">Input /1M</th><th class="num">Output /1M</th>'
                        '<th class="num">Blended</th><th>Notes</th></tr></thead><tbody>')
            for g in group:
                note = ""
                if g["variant"] == "batch":
                    note = "Asynchronous batch processing"
                elif g["variant"] == "free":
                    note = "Free tier, rate limited"
                else:
                    note = "Standard synchronous endpoint"
                body.append(f'<tr><td><code>{esc(g["id"])}</code></td>'
                            f'<td class="num">{price_cell(g.get("in1m"))}</td>'
                            f'<td class="num">{price_cell(g.get("out1m"))}</td>'
                            f'<td class="num strong">{price_cell(g.get("blend"))}</td>'
                            f"<td>{esc(note)}</td></tr>")
            body.append("</tbody></table></div></section>")

        alts = d.alternatives(canon)
        if alts:
            body.append('<section class="card"><h2>Cheaper models with similar capability</h2>'
                        + model_table(alts, d) + "</section>")
        ups = d.improved(canon)
        if ups:
            body.append('<section class="card"><h2>Worth paying more for</h2>'
                        '<p class="sub">Higher benchmark scores for a proportionally smaller price jump.</p>'
                        + model_table(ups, d) + "</section>")

        body.append('<section class="card"><h2>Price history</h2>' + sparkline(hist) + "</section>")
        body.append(b.ad_slot("inline", "Advertisement"))

        # FAQ (unique, numbers-driven)
        faqs = []
        if canon.get("in1m") is not None:
            answer = (
                f"{money(canon['in1m'])} per 1M input tokens and {money(canon['out1m'])} per 1M output "
                f"tokens, which is {money(canon['blend'])} per 1M tokens at a 3:1 input-to-output mix."
            )
            if canon.get("cache1m") is not None:
                answer += (
                    f" Cached input reads cost {money(canon['cache1m'])} per 1M with this provider's "
                    "cache tier."
                )
            faqs.append((f"How much does {canon['dn']} cost per 1M tokens?", answer))
        if canon.get("ctx"):
            faqs.append((f"What is {canon['dn']}'s context window?",
                         f"{int_fmt(canon['ctx'])} tokens"
                         + (f", with up to {int_fmt(canon['max_out'])} output tokens per request."
                            if canon.get("max_out") else ".")))
        if alts:
            faqs.append((f"Is there a cheaper alternative to {canon['dn']}?",
                         "Yes — " + ", ".join(f"{m['name']} at {money(m['blend'])} per 1M blended"
                                              for m in alts[:3])
                         + ". The full ranking is on the cheapest API pages."))
        if info.get("cheaper_pct"):
            faqs.append((f"Is {canon['dn']} expensive?",
                         f"It is the {ordinal(info['cost_rank'])} cheapest of {info['cost_total']} paid "
                         f"models, so {info['cheaper_pct']}% of the catalogue is more expensive per token."))
        if canon.get("in_mod"):
            faqs.append(("What inputs does it accept?",
                         "Accepted input: " + ", ".join(canon["in_mod"]) + ". Output: "
                         + ", ".join(canon.get("out_mod") or ["text"]) + "."))
        if faqs:
            body.append('<section class="card"><h2>Frequently asked</h2><dl class="faq">')
            for q, a in faqs:
                body.append(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>")
            body.append("</dl></section>")

        if canon.get("desc"):
            body.append('<section class="card prose"><h2>About this model</h2>'
                        f'<p>{esc(canon["desc"])}</p></section>')

        body.append('<section class="card"><h2>Use it</h2>'
                    f'<p>{b.affiliate(vendor, "https://openrouter.ai/models", "Compare live endpoints for " + canon["name"])} '
                    '— the tracker reads the same public catalogue, so what you see here is what the '
                    'router charges.</p>'
                    f'<p class="muted">{esc(vendor_label(vendor))} provider page: '
                    f'<a rel="noopener" href="/provider/{esc(canon["vk"])}.html">{esc(vendor_label(vendor))} '
                    "models on TokenPrice Watch</a>.</p></section>")
        body.append(b.newsletter_form())

        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": f'{canon["dn"]} API',
                "category": "LLM inference API",
                "brand": {"@type": "Brand", "name": vendor_label(vendor)},
                "description": f'Pricing for the {canon["dn"]} API: {money(canon.get("in1m"))} per 1M '
                               f'input tokens, {money(canon.get("out1m"))} per 1M output tokens.',
                "offers": {
                    "@type": "Offer",
                    "priceCurrency": "USD",
                    "price": f'{canon.get("in1m") or 0:.4f}',
                    "priceSpecification": {
                        "@type": "UnitPriceSpecification",
                        "price": f'{canon.get("in1m") or 0:.6f}',
                        "priceCurrency": "USD",
                        "unitText": "per 1M input tokens",
                    },
                    "url": b.url(path),
                },
            }
        ]
        if faqs:
            jsonld.append({
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": q,
                     "acceptedAnswer": {"@type": "Answer", "text": a}}
                    for q, a in faqs
                ],
            })
        title = (f"{canon['dn']} pricing: {money(canon['in1m'])}/1M in, {money(canon['out1m'])}/1M out"
                 f" ({short_date(d.date)})")
        html_text = b.shell(
            path=path, title=title,
            description=f"{canon['dn']} API cost: {money(canon['in1m'])} per 1M input, "
                        f"{money(canon['out1m'])} per 1M output tokens, "
                        f"{int_fmt(canon.get('ctx'))} context. Rankings, variants, cheaper alternatives. "
                        f"Updated {d.date}.",
            body="\n".join(body),
            breadcrumbs=[("Home", "/"), ("All prices", "/models.html"),
                         (vendor_label(vendor), f'/provider/{canon["vk"]}.html'), (canon["dn"], path)],
            jsonld=jsonld,
        )
        b.write(path, html_text, title=f'{canon["name"]} pricing', priority="0.7")


def build_vendor_pages(b: Builder) -> None:
    d = b.d
    for vk, group in sorted(d.vendors.items()):
        label = vendor_label(group[0]["vendor"])
        bases = [m for m in d.base_models if m["vk"] == vk]
        paid = [m for m in bases if m.get("blend") and m["blend"] > 0]
        paid.sort(key=lambda m: m["blend"])
        free = [m for m in bases if m["is_free"]]
        cheapest = paid[0] if paid else None
        best = max(bases, key=lambda m: m.get("iq") or 0) if bases else None
        price_range = f"{money(paid[0]['blend'])} – {money(paid[-1]['blend'])}" if paid else "—"

        body = [
            '<header class="page-head">',
            '<p class="kicker">Provider</p>',
            f"<h1>{esc(label)} API pricing</h1>",
            f'<p class="lede">{len(bases)} models · blended range {price_range} per 1M tokens · '
            f'{len(free)} free endpoint{"s" if len(free) != 1 else ""}.</p>',
            "</header>",
            b.ad_slot("top", "Advertisement"),
            '<section class="stats">',
            f'<div class="stat"><span>Models tracked</span><strong>{len(bases)}</strong></div>',
            f'<div class="stat"><span>Endpoints</span><strong>{len(group)}</strong></div>',
            f'<div class="stat"><span>Cheapest</span><strong>{esc(cheapest["dn"]) if cheapest else "—"}</strong></div>',
            f'<div class="stat"><span>Lowest blended</span><strong>{price_cell(cheapest.get("blend")) if cheapest else "—"}</strong></div>',
            f'<div class="stat"><span>Most capable</span><strong>{esc(best["dn"]) if best else "—"}</strong></div>',
            "</section>",
            f'<section class="card"><h2>All {esc(label)} models by price</h2>'
            + model_table(paid + free, d) + "</section>",
        ]
        if free:
            body.append(f'<section class="card"><h2>Free {esc(label)} endpoints</h2>'
                        + model_table(free, d) + "</section>")
        body.append('<section class="card prose"><h2>What to know before you commit</h2>'
                    f"<p>{esc(label)} publishes {len(bases)} models in the tracked catalogue. Prices "
                    "below are per million tokens as published in the provider's own pricing metadata and "
                    "refreshed daily. Two practical traps: long-context requests are often billed at a "
                    "higher tier above 128K–200K tokens, and cached input is billed separately — a cheap "
                    "headline rate with no cache tier can end up costing more than a pricier model with "
                    "large cache discounts.</p>"
                    '<p><a href="/methodology.html">Read the methodology</a> or '
                    '<a href="/cost-calculator.html">model your own volume</a>.</p></section>')
        body.append('<section class="card"><h2>Other providers</h2><ul class="linkgrid">')
        for other, ogroup in sorted(d.vendors.items()):
            if other == vk:
                continue
            ob = [m for m in d.base_models if m["vk"] == other]
            op = min([m["blend"] for m in ob if m.get("blend") and m["blend"] > 0], default=None)
            body.append(f'<li><a href="/provider/{esc(other)}.html">{esc(vendor_label(ogroup[0]["vendor"]))}</a>'
                        f'<span>{len(ob)} models'
                        + (f' · from {money(op)}/1M' if op else "") + "</span></li>")
        body.append("</ul></section>")
        body.append(b.ad_slot("inline", "Advertisement"))
        body.append(b.newsletter_form())

        path = f"/provider/{vk}.html"
        jsonld = [{
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{label} API pricing",
            "dateModified": d.date,
        }]
        html_text = b.shell(
            path=path, title=f"{label} API pricing — {len(bases)} models ({short_date(d.date)})",
            description=f"Every {label} model with input, output and blended price per 1M tokens, "
                        f"cheapest first. Updated daily.",
            body="\n".join(body),
            breadcrumbs=[("Home", "/"), ("All prices", "/models.html"), (label, path)],
            jsonld=jsonld,
        )
        b.write(path, html_text, title=f"{label} pricing", priority="0.6")


def build_changes(b: Builder) -> None:
    d = b.d
    days = sorted(d.change_days.keys(), reverse=True)
    today = d.date
    ch = d.change_days.get(today) or {"counts": {}, "price_changes": [], "added": [], "removed": []}
    counts = ch.get("counts", {})

    def _entry(c: dict) -> str:
        """Link a change-log entry to its model page, or to the archive if retired."""
        href = model_path(c["id"]) if c["id"] in d.by_id else "/retired.html"
        return (f'<li><a href="{esc(href)}">{esc(c["name"])}</a>'
                f' <code>{esc(c["id"])}</code></li>')

    body = [
        "<h1>LLM API price changes</h1>",
        f'<p class="lede">A permanent daily diff of every price in the catalogue. Latest update '
        f'{esc(human_date(today))}: {counts.get("price_changes", 0)} price move'
        f'{"s" if counts.get("price_changes", 0) != 1 else ""}, {counts.get("added", 0)} new endpoint'
        f'{"s" if counts.get("added", 0) != 1 else ""}, {counts.get("removed", 0)} retired'
        + (f', measured against the {esc(ch.get("baseline"))} snapshot.' if ch.get("baseline") else ".")
        + "</p>",
        b.ad_slot("top", "Advertisement"),
    ]
    body.append('<section class="card"><h2>Price moves on ' + esc(today) + "</h2>"
                + change_rows(ch.get("price_changes", []), d) + "</section>")
    if ch.get("added") or ch.get("removed"):
        body.append('<section class="grid-2">')
        body.append('<div class="card"><h2>New endpoints</h2><ul class="plain">'
                    + ("".join(_entry(c) for c in ch.get("added", []))
                       or '<li class="muted">No new endpoints in this update.</li>')
                    + "</ul></div>")
        body.append('<div class="card"><h2>Retired endpoints</h2><ul class="plain">'
                    + ("".join(f'<li>{esc(display_name(c["name"], c["id"].split("/")[0]))}</li>'
                               for c in ch.get("removed", []))
                       or '<li class="muted">Nothing retired in this update.</li>')
                    + "</ul></div></section>")

    body.append('<section class="card"><h2>Change history</h2>'
                '<p class="sub">One page per day. Archives stay online, so you can always check what a '
                'price was on a given date.</p><ul class="daylist">')
    for date in days:
        c = d.change_days[date].get("counts", {})
        moves = c.get("price_changes", 0)
        body.append(f'<li><a href="/changes/{esc(date)}.html">{esc(date)}</a>'
                    f'<span>{moves} price move{"s" if moves != 1 else ""} · '
                    f'{c.get("added", 0)} added · {c.get("removed", 0)} retired</span></li>')
    body.append("</ul></section>")
    body.append(b.newsletter_form())

    html_text = b.shell(
        path="/changes.html", title="LLM API price changes — daily diff log",
        description="Every LLM API price move, addition and retirement, recorded daily. Includes "
                    "per-cent changes and the full archive.",
        body="\n".join(body), breadcrumbs=[("Home", "/"), ("Price changes", "/changes.html")],
    )
    b.write("/changes.html", html_text, title="Price changes", priority="0.9")

    for date in days:
        day = d.change_days[date]
        c = day.get("counts", {})
        hist_index = sorted(d.change_days).index(date)
        older = sorted(d.change_days)[hist_index - 1] if hist_index > 0 else None
        newer = sorted(d.change_days)[hist_index + 1] if hist_index + 1 < len(d.change_days) else None
        day_baseline = day.get("baseline")
        body = [
            "<h1>LLM API price changes — " + esc(human_date(date)) + "</h1>",
            f'<p class="lede">{c.get("price_changes", 0)} price move'
            f'{"s" if c.get("price_changes", 0) != 1 else ""} '
            f'({c.get("drops", 0)} down, {c.get("hikes", 0)} up) · {c.get("added", 0)} new · '
            f'{c.get("removed", 0)} retired · {c.get("models", 0)} endpoints tracked'
            + (f", measured against {esc(day_baseline)}." if day_baseline else ".") + "</p>",
            b.ad_slot("top", "Advertisement"),
            '<section class="card">' + change_rows(day.get("price_changes", []), d) + "</section>",
        ]
        if day.get("added"):
            body.append('<section class="card"><h2>Added this day</h2><ul class="plain">'
                        + "".join(_entry(x) for x in day["added"]) + "</ul></section>")
        if day.get("removed"):
            body.append('<section class="card"><h2>Retired this day</h2><ul class="plain">'
                        + "".join(f'<li>{esc(x["name"])}</li>' for x in day["removed"]) + "</ul></section>")
        nav = []
        if newer:
            nav.append(f'<a href="/changes/{esc(newer)}.html">← Newer ({esc(newer)})</a>')
        if older:
            nav.append(f'<a href="/changes/{esc(older)}.html">Older ({esc(older)}) →</a>')
        if nav:
            body.append('<p class="daynav">' + " · ".join(nav) + "</p>")
        body.append('<p><a href="/changes.html">All change logs →</a></p>')
        html_text = b.shell(
            path=f"/changes/{date}.html",
            title=f"LLM API price changes on {date} — {c.get('price_changes', 0)} moves",
            description=f"Price moves recorded on {date}: {c.get('drops', 0)} cuts, {c.get('hikes', 0)} "
                        f"increases, {c.get('added', 0)} new endpoints.",
            body="\n".join(body),
            breadcrumbs=[("Home", "/"), ("Price changes", "/changes.html"), (date, f"/changes/{date}.html")],
            canonical_path=f"/changes/{date}.html",
        )
        b.write(f"/changes/{date}.html", html_text, title=f"Changes {date}", priority="0.4")


def build_calculator(b: Builder) -> None:
    d = b.d
    payload = [
        {"i": m["id"], "n": m["name"], "v": m["vendor"], "a": m.get("in1m"), "o": m.get("out1m"),
         "c": m.get("cache1m"), "x": m.get("ctx"), "q": m.get("iq"),
         "d": 1 if m.get("dynamic") else 0}
        for m in sorted(d.base_models, key=lambda m: (m.get("blend") is None, m.get("blend") or 0))
    ]
    body = [
        "<h1>LLM API cost calculator</h1>",
        '<p class="lede">Estimate a monthly inference bill before you build on a model. Enter your '
        "traffic; the page ranks every tracked model by what it would cost you.</p>",
        b.ad_slot("top", "Advertisement"),
        """<section class="card calc">
  <div class="calc-inputs">
    <label>Calls per day <input type="number" id="calls" value="20000" min="0" step="100"></label>
    <label>Input tokens per call <input type="number" id="tin" value="1500" min="0" step="100"></label>
    <label>Output tokens per call <input type="number" id="tout" value="400" min="0" step="50"></label>
    <label>% of input served from cache <input type="number" id="cache" value="0" min="0" max="95" step="5"></label>
    <label>Days per month <input type="number" id="days" value="30" min="1" max="31"></label>
  </div>
  <p class="calc-out" id="calcout">—</p>
  <div class="table-wrap"><table class="prices"><thead><tr><th>#</th><th>Model</th><th>Provider</th>
  <th class="num">Input /1M</th><th class="num">Output /1M</th><th class="num">Your monthly cost</th>
  <th class="num">Intelligence</th></tr></thead><tbody id="calcrows"></tbody></table></div>
  <p class="muted">Estimates use published list prices and ignore free tiers, minimums, volume discounts
  and failed-request retries. Cache percentage applies to input tokens only and uses the cached-input
  rate where a provider publishes one; models without a cache tier are billed at full input price.</p>
</section>""",
        '<section class="card prose"><h2>How to cut the bill</h2><ol>'
        "<li><strong>Cache the system prompt.</strong> A 2,000-token instruction block sent on every "
        "request is the single largest avoidable cost at scale; cache reads are typically 10–25% of the "
        "input rate.</li>"
        "<li><strong>Route by task.</strong> Most production traffic does not need your most expensive "
        "model. Send classification and extraction to a small model and escalate only hard cases.</li>"
        "<li><strong>Cap output tokens.</strong> Output is usually 3–5× the input price per token, and "
        "verbose answers are pure cost.</li>"
        "<li><strong>Use batch endpoints</strong> for anything that is not interactive — see "
        '<a href="/cheapest/cheapest-batch-api.html">batch pricing</a>.</li>'
        "<li><strong>Re-check the table monthly.</strong> Prices fall; a model that was wrong for your "
        "budget last quarter is often the right answer now — that is why this tracker updates daily.</li>"
        "</ol></section>",
        b.newsletter_form(),
    ]
    html_text = b.shell(
        path="/cost-calculator.html", title="LLM API cost calculator — what your workload would cost today",
        description="Free LLM API cost calculator: enter calls per day and token sizes to see the monthly "
                    "bill for every tracked model, ranked cheapest first.",
        body="\n".join(body),
        breadcrumbs=[("Home", "/"), ("Cost calculator", "/cost-calculator.html")],
    )
    html_text = html_text.replace(
        "</body>",
        f'<script id="models-data" type="application/json">{json.dumps(payload, separators=(",", ":"))}</script>\n</body>',
    )
    b.write("/cost-calculator.html", html_text, title="Cost calculator", priority="0.9")


def build_static_pages(b: Builder) -> None:
    d = b.d
    pages = [
        ("/about.html", "About TokenPrice Watch", "Who runs this tracker, why it exists, and what it is not.", [
            f"<h1>About {esc(b.site)}</h1>",
            '<p class="lede">A one-page answer to a question every engineering team asks: what do LLM '
            "APIs actually cost today?</p>",
            '<section class="card prose"><h2>What this is</h2>'
            f'<p>{esc(b.site)} rebuilds the entire public LLM price catalogue every single day and keeps '
            "the diff. It exists because published price lists drift: providers add snapshots weekly, cut "
            "rates without announcement, introduce cache tiers, and retire models. A spreadsheet copied "
            "last quarter is reliably wrong.</p>"
            "<h2>What this is not</h2>"
            "<p>It is not a benchmark site, and it is not affiliated with, endorsed by, or sponsored by "
            "any model provider. Benchmark indices shown here are the values published alongside the "
            "models in the public catalogue; they are quoted, not measured by us. Prices are list prices "
            "in USD and exclude negotiated discounts, minimum commitments and failed-request retries.</p>"
            "<h2>How it makes money</h2>"
            "<p>Advertising and affiliate links to inference providers. When a provider link earns a "
            "referral, that is disclosed on the page with a <code>sponsored</code> link attribute, and it "
            "never changes a ranking: every table on this site is sorted by price or by a published "
            "benchmark index.</p>"
            "<h2>Corrections</h2>"
            f'<p>If a price here is wrong, it is almost always because the upstream catalogue changed and '
            f'the next daily run will fix it. To flag something urgent, email '
            f'<a href="mailto:{esc(b.cfg.get("contact_email",""))}">{esc(b.cfg.get("contact_email",""))}</a>.</p>'
            "</section>",
        ], "/about.html"),
        ("/methodology.html", "Methodology — how the price data is collected", "Data source, refresh schedule, pricing units, benchmark provenance and the limits of this dataset.", [
            "<h1>Methodology</h1>",
            '<p class="lede">Everything on this site is derived from one public data source, refreshed '
            "once a day, and committed to a public repository. Here is exactly how.</p>",
            '<section class="card prose"><h2>Source</h2>'
            '<p>Model metadata and prices are pulled from the public OpenRouter models catalogue '
            '(<code>openrouter.ai/api/v1/models</code>), a machine-readable list of endpoints, per-token '
            "prices, context windows, cache rates, modalities and published benchmark indices. No private "
            "API key is used and no scraping of HTML price pages happens.</p>"
            "<h2>Refresh schedule</h2>"
            "<p>Once per day, shortly after 06:17 UTC. Each run writes a dated snapshot to "
            "<code>data/snapshots/</code>, computes the diff against the previous snapshot into "
            "<code>data/changes/</code>, and rebuilds every page. If the collector receives fewer than 50 "
            "models it aborts without overwriting data, so a bad upstream response cannot wipe the site.</p>"
            "<h2>Units</h2>"
            "<p>All prices are USD per <strong>1,000,000 tokens</strong>. The upstream source publishes "
            "per-token prices; multiply by 1,000,000 and round for display. <strong>Blended</strong> price "
            "= 0.75 × input + 0.25 × output, a 3:1 input:output ratio that matches typical chat and RAG "
            "traffic. Ranked tables always state which column they are ordered by.</p>"
            "<h2>Benchmark indices</h2>"
            "<p>Intelligence, coding and agentic indices are quoted from the catalogue's published "
            "benchmark field. They are third-party absolute scores, not the site's own measurements, and "
            "they are only available for a subset of models — models without a published index are shown "
            "with a dash rather than an invented value.</p>"
            "<h2>Accuracy limits</h2>"
            "<ul><li>List prices change intraday; this site guarantees at most a 24-hour lag.</li>"
            "<li>Long-context tiers, batch discounts and minimum commitments are not always representable "
            "per token — verify before signing anything.</li>"
            "<li>Free endpoints carry undocumented rate limits and licence terms.</li>"
            "<li>Variants (<code>:batch</code>, <code>:free</code>) are shown on the model page rather "
            "than as separate models, to avoid duplicate pages.</li></ul>"
            "<h2>Reproducibility</h2>"
            "<p>The generator is a small Python program with no third-party dependencies. Anyone can "
            "clone the repository, run two commands, and rebuild this site from the committed snapshots.</p>"
            "</section>",
        ], "/methodology.html"),
        ("/advertise.html", "Advertise — reach developers choosing an inference provider", "Sponsorship placements, audience profile and how to get in front of engineers comparing LLM API costs.", [
            "<h1>Advertise on " + esc(b.site) + "</h1>",
            '<p class="lede">A small, high-intent audience: engineers and founders deciding which '
            "inference provider to build on.</p>",
            '<section class="card prose"><h2>Who reads this</h2>'
            "<p>Developers comparing per-token costs, teams migrating between providers, and buyers "
            "estimating an inference budget. The intent is unusually commercial: every visitor is looking "
            "at a price comparison table.</p>"
            "<h2>Placements</h2>"
            "<ul><li><strong>Sponsor bar</strong> — one line above the fold, site-wide.</li>"
            "<li><strong>Table sponsorship</strong> — labelled slot adjacent to the price tables on the "
            "highest-traffic pages.</li>"
            "<li><strong>Newsletter</strong> — included in the daily price-change email.</li>"
            "<li><strong>Provider profile</strong> — a factual, clearly-labelled note on a provider page; "
            "rankings are never for sale.</li></ul>"
            "<h2>Editorial rule</h2>"
            "<p>Paid placements are always labelled and never change a ranking. If a sponsored entry "
            "would alter a sorted table, the sponsorship is declined instead.</p>"
            f'<h2>Get in touch</h2><p>Email <a href="mailto:{esc(b.cfg.get("contact_email",""))}">'
            f'{esc(b.cfg.get("contact_email",""))}</a> with the provider or product you want to place, '
            "the pages you care about, and the period.</p></section>",
        ], "/advertise.html"),
        ("/privacy.html", "Privacy policy", "What this site collects, which third parties are involved, and how to opt out.", [
            "<h1>Privacy policy</h1>",
            '<section class="card prose">'
            "<p>This site is a static website. It has no accounts, no login, and no user-submitted "
            "content. The only personal data it can receive is what you type into the optional newsletter "
            "form, plus standard server logs and advertising or analytics cookies described below.</p>"
            "<h2>Newsletter</h2><p>If you subscribe, your email address is stored by the newsletter "
            "provider named on the form and used only to send daily price-change emails. Unsubscribe "
            "links appear in every email.</p>"
            "<h2>Advertising</h2><p>Third-party ad vendors (for example Google AdSense) may set cookies "
            "or use device identifiers to serve and measure ads. Where required by law, a consent message "
            "is shown before non-essential cookies are set. You can opt out of personalised advertising in "
            "your Google Ads settings.</p>"
            "<h2>Analytics</h2><p>If aggregate analytics are enabled they are configured without "
            "cross-site tracking or personal identifiers.</p>"
            "<h2>Affiliate links</h2><p>Outbound provider links may be affiliate links and are marked "
            "with <code>rel=\"sponsored\"</code>. Following one may set a cookie from the provider.</p>"
            "<h2>Data we publish</h2><p>The only dataset published here is model pricing metadata, which "
            "contains no personal data.</p>"
            f'<h2>Contact</h2><p>Requests about this policy: '
            f'<a href="mailto:{esc(b.cfg.get("contact_email",""))}">{esc(b.cfg.get("contact_email",""))}</a>.</p>'
            "</section>",
        ], "/privacy.html"),
        ("/terms.html", "Terms of use", "The basis on which this pricing data is provided.", [
            "<h1>Terms of use</h1>",
            '<section class="card prose">'
            "<p>The pricing data and rankings on this site are provided for information only, without "
            "warranty of any kind. Prices are collected from public provider metadata and may be stale, "
            "incomplete or superseded by a provider's own terms.</p>"
            "<h2>No advice</h2><p>Nothing here is procurement, legal or financial advice. Verify pricing "
            "with the provider before you commit to a contract or a production migration.</p>"
            "<h2>Reuse</h2><p>The daily snapshots are publicly available in the repository this site is "
            "built from; reuse them with attribution and a link to this site.</p>"
            "<h2>Trademarks</h2><p>Model and provider names are trademarks of their owners and are used "
            "here for identification only. This site is not affiliated with or endorsed by any of them.</p>"
            "</section>",
        ], "/terms.html"),
    ]
    for path, title, desc, chunks, canonical in pages:
        body = "\n".join(chunks) + "\n" + b.ad_slot("inline", "Advertisement") + "\n" + b.newsletter_form()
        html_text = b.shell(
            path=path, title=f"{title} — {b.site}", description=desc, body=body,
            breadcrumbs=[("Home", "/"), (title, path)], canonical_path=canonical,
        )
        b.write(path, html_text, title=title, priority="0.3")

    # 404
    notfound = b.shell(
        path="/404.html",
        title="Page not found — TokenPrice Watch",
        description="That page does not exist. Jump to the full LLM API price table, the cheapest API "
                    "rankings, or the cost calculator to find current model pricing.",
        body='<h1>Page not found</h1><p class="lede">Try the <a href="/models.html">full price table</a>, '
             'the <a href="/cheapest.html">cheapest API rankings</a>, or the '
             '<a href="/cost-calculator.html">cost calculator</a>.</p>',
    )
    (b.out / "404.html").write_text(notfound)
    b.pages.append((b.url("/404.html"), "404", "0.1"))


def build_retired(b: Builder) -> None:
    d = b.d
    arch = sorted(d.archive, key=lambda e: (e.get("last_seen") or "", e["id"]), reverse=True)
    body = [
        "<h1>Retired and delisted LLM API models</h1>",
        f'<p class="lede">Endpoints that disappeared from the tracked catalogue, with the last price we '
        f'observed. {len(arch)} models archived. Old links and delisted models still resolve here, so you '
        f'can see what a model cost before a provider pulled it.</p>',
        b.ad_slot("top", "Advertisement"),
    ]
    if arch:
        rows = []
        for e in arch:
            pin = per_m(e.get("pin"))
            pout = per_m(e.get("pout"))
            pcr = per_m(e.get("pcr"))
            blend = (pin * 0.75 + pout * 0.25) if (pin is not None and pout is not None) else None
            rows.append(
                "<tr>"
                f"<td>{esc(display_name(e['name'], e['id'].split('/')[0]))}"
                f"<br><code>{esc(e['id'])}</code></td>"
                f"<td>{esc(vendor_label(e['id'].split('/')[0]))}</td>"
                f'<td class="num">{price_cell(pin)}</td>'
                f'<td class="num">{price_cell(pout)}</td>'
                f'<td class="num strong">{price_cell(blend)}</td>'
                f'<td class="num">{price_cell(pcr)}</td>'
                f'<td class="num">{esc(int_fmt(e.get("ctx")))}</td>'
                f'<td class="num">{esc(e.get("last_seen"))}</td>'
                "</tr>"
            )
        body.append(
            '<div class="table-wrap"><table class="prices"><thead><tr><th>Model</th><th>Provider</th>'
            '<th class="num">Last input /1M</th><th class="num">Last output /1M</th>'
            '<th class="num">Last blended /1M</th><th class="num">Last cache /1M</th>'
            '<th class="num">Context</th><th class="num">Last seen</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>"
        )
    else:
        body.append('<p class="muted">Nothing has been delisted since tracking started on '
                    f'{esc(d.date)}. This page fills up automatically as providers retire endpoints.</p>')
    body.append('<section class="card prose"><h2>Why models disappear</h2>'
                "<p>Providers delist endpoints for three common reasons: a dated snapshot is superseded by "
                "a newer one, a preview model is withdrawn, or a free tier is closed after an abuse wave. "
                "If you depended on a retired model, the cheapest replacements are ranked on the "
                '<a href="/cheapest.html">cheapest API pages</a>, and every removal is dated in the '
                '<a href="/changes.html">daily change log</a>.</p></section>')
    body.append(b.newsletter_form())
    html_text = b.shell(
        path="/retired.html", title=f"Retired LLM API models ({len(arch)} archived) — last known prices",
        description="Delisted and retired LLM API endpoints with their last observed prices, context "
                    "windows and delisting dates. Archived automatically by the daily tracker.",
        body="\n".join(body), breadcrumbs=[("Home", "/"), ("Retired models", "/retired.html")],
    )
    b.write("/retired.html", html_text, title="Retired models", priority="0.5")


def build_feeds(b: Builder) -> None:
    d = b.d
    # sitemap
    items = []
    for url, _, priority in b.pages:
        if url.rstrip("/").endswith("404.html"):
            continue
        items.append(f"<url><loc>{esc(url)}</loc><lastmod>{d.date}</lastmod>"
                     f"<priority>{priority}</priority></url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               + "".join(items) + "</urlset>")
    (b.out / "sitemap.xml").write_text(sitemap)

    robots = ["User-agent: *", "Allow: /", "Disallow: /404.html", ""]
    if b.base_url:
        robots += [f"Sitemap: {b.base_url}/sitemap.xml", ""]
    (b.out / "robots.txt").write_text("\n".join(robots))

    # rss: daily change entries
    entries = []
    for date in sorted(d.change_days, reverse=True)[:60]:
        day = d.change_days[date]
        c = day.get("counts", {})
        moves = day.get("price_changes", [])
        lines = [f"{c.get('price_changes',0)} price moves, {c.get('added',0)} new, {c.get('removed',0)} retired"]
        for mv in moves[:25]:
            field = {"pin": "input", "pout": "output", "pcr": "cache read", "pcw": "cache write"}.get(mv["field"], mv["field"])
            direction = "cut" if mv["direction"] == "down" else "raised"
            pct = f" ({mv['pct']:+.1f}%)" if mv.get("pct") is not None else ""
            lines.append(f"{mv.get('name', mv['id'])} {field} {direction} to {mv['to']} USD/token{pct}")
        desc = "\n".join(lines)
        pubs = f"{date}T06:30:00Z"
        entries.append(
            "<item>"
            f"<title>LLM API price changes — {date}</title>"
            f"<link>{esc(b.url('/changes/' + date + '.html'))}</link>"
            f"<guid isPermaLink=\"true\">{esc(b.url('/changes/' + date + '.html'))}</guid>"
            f"<pubDate>{dt.datetime.strptime(date, '%Y-%m-%d').strftime('%a, %d %b %Y 06:30:00 +0000')}</pubDate>"
            f"<description>{esc(desc)}</description>"
            "</item>"
        )
    rss = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
           f"<title>{esc(b.site)} — daily LLM API price changes</title>"
           f"<link>{esc(b.url('/'))}</link>"
           f"<description>{esc(b.cfg.get('description',''))}</description>"
           f"<language>en</language><lastBuildDate>"
           f"{dt.datetime.strptime(d.date, '%Y-%m-%d').strftime('%a, %d %b %Y 06:30:00 +0000')}</lastBuildDate>"
           + "".join(entries) + "</channel></rss>")
    (b.out / "rss.xml").write_text(rss)
    # Some hosts only allow fixed-name or content-hashed non-HTML files. The
    # `.well-known/` namespace is the stable, conventional place for a feed that
    # has to keep one URL while its contents change daily.
    well_known = b.out / ".well-known"
    well_known.mkdir(parents=True, exist_ok=True)
    (well_known / "feed.xml").write_text(rss)


def rewrite_prefix(out: pathlib.Path, prefix: str) -> int:
    """Rewrite root-relative href/src attributes for subpath deployments.

    Canonical/meta/JSON-LD URLs are already absolute (built from --base-url) and
    are untouched, so the prefix is applied exactly once per link.
    """
    prefix = "/" + prefix.strip("/")
    if prefix == "/":
        return 0
    touched = 0
    for page in out.rglob("*.html"):
        text = page.read_text()
        new = text.replace('href="/', f'href="{prefix}/').replace('src="/', f'src="{prefix}/')
        # undo double-prefix on anything already pointing at the prefix
        new = new.replace(f'href="{prefix}{prefix}/', f'href="{prefix}/')
        new = new.replace(f'src="{prefix}{prefix}/', f'src="{prefix}/')
        if new != text:
            page.write_text(new)
            touched += 1
    print(f"[build] rewrote {touched} pages for path prefix {prefix}")
    return touched


def build_assets(b: Builder) -> None:
    (b.out / "assets").mkdir(parents=True, exist_ok=True)
    for name, hashed in b.hashed.items():
        shutil.copy2(b.assets / name, b.out / "assets" / hashed)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parent.parent))
    ap.add_argument("--out", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--rss-href", default="/rss.xml",
                    help="feed URL used in <link rel=alternate> and the footer")
    ap.add_argument("--path-prefix", default="",
                    help="deploy under a subpath (e.g. /my-repo for GitHub Pages project sites); "
                         "root-relative links get the prefix, canonical URLs come from --base-url")
    ap.add_argument("--no-rss", action="store_true",
                    help="omit top-level rss.xml (keep .well-known/feed.xml) for hosts that "
                         "require fixed names or content-hashed assets")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    cfg = json.loads((root / "config" / "site.json").read_text())
    out = pathlib.Path(args.out) if args.out else root / "site"
    base_url = args.base_url if args.base_url is not None else cfg.get("base_url", "")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    data = Dataset(root)
    b = Builder(data, cfg, out, base_url, rss_href=args.rss_href)

    build_home(b)
    build_models_table(b)
    build_use_cases(b)
    build_model_pages(b)
    build_vendor_pages(b)
    build_changes(b)
    build_retired(b)
    build_calculator(b)
    build_static_pages(b)
    build_assets(b)
    build_feeds(b)
    if args.no_rss and (out / "rss.xml").exists():
        (out / "rss.xml").unlink()
    if args.path_prefix:
        rewrite_prefix(out, args.path_prefix)

    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"[build] {len(b.pages)} pages, {size/1024/1024:.1f} MiB in {out}")
    print(f"[build] models={len(data.bases)} vendors={len(data.vendors)} changes_days={len(data.change_days)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
