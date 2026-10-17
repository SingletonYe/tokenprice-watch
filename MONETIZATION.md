# TokenPrice Watch — Monetization Playbook

**Target:** $50/day = **$1,500/month** (30-day basis), for a solo owner with ~1 hour/day.

**Evidence standard.** Every volume, CPC, difficulty score, SERP composition and backlink count below was observed live on **2026-10-17** via `okou seo` (DataForSEO) and `okou web-search`. Program thresholds come from vendor primary sources where cited. Anything unverified is marked **[ESTIMATE]** or **[UNVALIDATED]**. Nothing here is a guarantee.

---

## 1. Unit economics: what $50/day actually requires

$1,500/month ÷ RPM × 1,000 = required monthly pageviews.

| Path | Mechanism | Rate used | Pageviews for $1,500/mo | Viable? |
|---|---|---|---|---|
| AdSense only | Display, no minimum | $6 RPM | **250,000** | Slow |
| AdSense only | Display, US-skew | $12 RPM | **125,000** | Slow |
| AdSense only | Display, ceiling | $15 RPM | **100,000** | Slow |
| Premium programmatic | Raptive / Mediavine | $18 RPM | **83,000** | Needs 25k pv/mo first |
| Premium programmatic | Managed header bidding | $30 RPM | **50,000** | Needs $5k/yr ad rev (circular) |
| EthicalAds | Dev-only, 1 unit, 70% share | **$2.50 CPM** (verified) | **600,000** | **No** |
| Carbon Ads | Invite-only, 60% share | **$1.75 CPM** (verified $1.20–$2.30) | **857,000** | **No** |
| Affiliate / referral | Provider + GPU-cloud bounties | ~$5/mo per active referred spender | **~45,000–60,000** | Yes, with approvals |
| Direct sponsor slot | One hand-sold placement | $25 CPM on 40k sellable pv, or $1,500 flat | **~40,000–60,000** | Yes — one conversation |

**RPM basis.** Published 2026 ranges: developer/coding blogs $8–$22, tech how-to and software reviews $12–$35, software/SaaS $30–$65, B2B SaaS $15–$45. I use the **low end** deliberately — developer audiences have high ad-block rates and these are comparison tables, not long reads. **[ESTIMATE]**

**Affiliate math.** A referred developer spending $60/month on inference or GPU capacity (range $20–$300) yields **$3.00–$6.00/month** under RunPod's verified terms (3% Pod / 5% Serverless, 6 months; 10% cash after 25 paying referrals). Blended: **$5/month per active referred spender [ESTIMATE]** → **300 active paying referred developers** → ~50,000 pageviews/month at 12% pageview→click and 5% click→spender.

**The decisive economic fact.** Advertisers pay **$5.81, $6.04, $7.93, $8.42, $8.91, $9.85, $10.29, $12.80, $13.33, $14.08, $15.15, $17.73 and $28.34 per search click** on the exact queries this site targets (DataForSEO CPC, US, 2026-10-17). At $25 CPM a sponsor buys **1,000 impressions for the price of one search click**. That asymmetry — not traffic volume — is the site's monetization edge, and it justifies $30–60 CPM on high-intent pages.

**Fastest path to $50/day: direct sponsor + affiliate/referral, not display.** Both clear $1,500/month at ~45,000–60,000 pageviews; AdSense alone needs 100,000–250,000. The sponsor path wins on *calendar* time — one sales conversation instead of 75,000 more pageviews. EthicalAds would need 600,000 pageviews/month on its own. **[ESTIMATE]** for the ranking; CPMs and CPCs are measured.

---

## 2. Highest-intent keyword targets

All rows **validated** (DataForSEO, US, desktop, 2026-10-17) unless marked. Tier **A** = KD 0–20, **B** = 21–35, **C** = 36+.

**`/model/<vendor>/<slug>/` — per-model pages (highest commercial intent)**

| Query | Volume | CPC | KD | Tier |
|---|---|---|---|---|
| claude api pricing | 8,100 | $5.57 | 15 | A |
| claude model pricing | 1,600 | $5.33 | 23 | B |
| claude api token price | 590 | $5.30 | 36 | C |
| claude ai api pricing | 260 | $8.91 | 22 | B |
| gemini api pricing | 4,400 | $4.24 | 21 | B |
| gemini token price | 260 | — | 17 | A |
| grok api pricing | 1,000 | $6.04 | 19 | A |
| openai model pricing | 1,600 | $17.73 | 37 | C |
| open ai api pricing | 1,000 | $12.94 | 19 | A |
| openai token price | 320 | $12.80 | 33 | B |
| deepseek v4 pro api pricing | 320 | $13.33 | 16 | A |
| nano banana api pricing | 260 | $9.89 | 21 | B |
| vertex ai pricing | 390 | $5.69 | 22 | B |
| perplexity ai pricing | 1,300 | $15.18 | 40 | C |
| gemini ai pricing | 1,000 | $5.21 | 59 | C |

**`/provider/<vendor>/` — vendor pages**

| Query | Volume | CPC | KD | Tier |
|---|---|---|---|---|
| **openrouter alternatives** | **880** | **$17.90** | **1** | **A** |
| openrouter proxy | 110 | $5.31 | 9 | A |
| openrouter docs | 210 | $2.27 | 32 | B |

`openrouter alternatives` is the single best target found: 880 searches, **$17.90 CPC**, **KD 1**. The live SERP is Reddit plus vendor marketing blogs (DigitalOcean, Braintrust, Portkey, TrueFoundry) — no neutral data site owns it.

**`/models/` — the full pricing table**

| Query | Volume | CPC | KD | Tier |
|---|---|---|---|---|
| llm price | 210 | $6.83 | 31 | B |
| llm cost | 170 | $7.39 | 26 | B |
| ai model pricing | 170 | $10.29 | 32 | B |
| llm api pricing comparison | 140 | $8.42 | 31 | B |
| ai model pricing comparison | 110 | $9.85 | 21 | B |
| cost per million tokens | 110 | $28.34 | 24 | B |

**`/cheapest/<use-case>/` + homepage**

| Query | Volume | CPC | KD | Tier |
|---|---|---|---|---|
| ai token cost | 1,000 | $14.08 | 0 | A |
| cheapest llm | 140 | $9.08 | 22 | B |
| ai token price | 210 | $14.59 | 11 | A |
| ai token pricing | 210 | $14.59 | 5 | A |
| free llm api | not returned | — | — | **[UNVALIDATED]** |
| cheapest llm api, cheapest api for batch processing, cheapest vision api, cheapest reasoning api, best value llm api, llm cost calculator | not returned | — | — | **[UNVALIDATED]** |

The last group matches pages that **already exist** in the build (`cheapest-batch-api`, `cheapest-vision`, `cheapest-reasoning`, `cheapest-prompt-caching`, `cheapest-long-context`, `cheapest-million-context`, `cheapest-output-tokens`, `cheapest-for-agents`, `cheapest-for-coding`, `best-value-llm-api`, `free-llm-apis`). DataForSEO returned no volume for them — genuine zero-volume long tails. **Keep them (they convert, they cost nothing to host) but do not plan traffic from them.** Validate via Search Console impressions at day 60.

**Competitive evidence that matters more than KD:**

- `cheapest llm api` is held by **paritylayer.com at #4 and #9** — **30 referring domains** (verified). botgenuity.com ranks #2 with 1,758. Near-zero-authority domains already rank top-5.
- `llm cost calculator` is the softest SERP found: **all ten results are no-name tool sites**; agentcosts.xyz (31 referring domains) holds **#3**.
- Harder: `openai model pricing` and `claude api pricing` are owned by official docs plus benchlm.ai (1,263 referring domains).
- Avoid head brand terms: `openrouter` (135,000 vol, KD 44), `claude pricing` (40,500, KD 34), `openai pricing` (5,400, KD 39).

---

## 3. Monetization programs: real requirements and payouts

| Program | Exact requirement | Payout | At 0 traffic? | Source |
|---|---|---|---|---|
| **Google AdSense** | No traffic minimum; must pass policy review | Dev/tech $8–$22 RPM; tech how-to $12–$35 | **Yes** | published 2026 ranges |
| **Mediavine Journey** | 1,000 Tier-1 sessions/30 days | Not published | **Yes, ~1k sessions** | Publift; toolincomelab |
| **Mediavine (official)** | **$5,000/yr ad revenue** + original content, clean traffic, good AdSense standing | 75% share, net-65 | No — circular | Publift; monetific |
| **Raptive** | **25,000 monthly pageviews**; 25k–99k needs ≥50% Tier-1 traffic; domain 6+ months old; GA configured | **Flat 75%**, net-45 | No — 25k gate | Publift; monetizepros |
| **Ezoic** | **250,000 monthly active users** (raised 19 Feb 2026 from effectively none) | $3–$25 RPM, net-30 | **No — hard gate** | Publift; calmmonetization |
| **Monumetric** | 10,000 pageviews/mo **+ $99 setup fee** | $6–$30 RPM, net-60 | No | monetific |
| **EthicalAds** | **50,000 pageviews/mo**, developer-focused, sole ad, above the fold | **~$2.50 CPM**, 70% share, $50 payout min | No | ethicalads.io/publishers/faq |
| **Carbon Ads** | **Invite-only**; English-speaking devs/designers, US/CA/EU; exclusive | **$1.20–$2.30 CPM**, 60% share | Apply yes, selective | carbonads.net/faq |
| **Freestar** | ~1M pageviews/mo, 12 months history | Managed | No | Publift |
| **RunPod** | Self-serve | 3% Pod / 5% Serverless, 6 months; **10% cash after 25 paying referrals** | **Yes** | runpod.io (primary) |
| **Together AI** | Application; approval slow | 15% recurring 12mo **[UNVALIDATED — conflicting sources]** | Apply yes | directories only |
| **Fireworks AI** | Application | 10–15% first order, no recurring **[UNVALIDATED]** | Apply yes | directories only |
| **OpenRouter** | **No public affiliate or referral program.** Two independent sweepers found no affiliate/referral page and no mention of "referral", "affiliate" or "commission" in its docs or 5,999-entry sitemap. The widely circulated "$5 for you, $5 for them" claim traces to coupon sites citing no source | **$0** | N/A | openaffiliate.dev; referral.wiki |
| **Anthropic / OpenAI** | **No public affiliate or referral program**; enterprise partnerships only | $0 | No | dev.to comparison |
| **Novita AI** | Self-serve | Referral program active | Yes | aiapicost.com disclosure |
| **DeepInfra** | Application | Listed **"pending"** on a live competitor in this niche | Apply yes | aiapicost.com |
| **Newsletter sponsorship** | Need a list | **$30–$80 CPM** dev/tech; marketplaces take 20–30% | No | onetwothreesend; earninglivingonline |

**Reachable at zero traffic:** AdSense, RunPod's referral program, and direct sponsor outreach. Ezoic is now closed to new small sites. Raptive at 25k pv/mo is the realistic premium target — it now sits *below* Mediavine Official's revenue gate, an inversion that happened in 2026.

⚠️ **Immediate fix:** `config/site.json`'s affiliate map example uses `"openrouter"` as the key slug. **OpenRouter pays $0 in referral commission.** Repoint that example to `runpod` or `novita`, or delete it — otherwise the site will render outbound links that earn nothing while looking monetized.

---

## 4. 90-day operating plan

~1 hour/day. Revenue figures are **honest estimates**, not targets.

**Phase 0 — Foundations (Days 0–14)**

| Weekly action | Metric that must move |
|---|---|
| Submit sitemap to Search Console + Bing IndexNow; verify canonicals | Pages **indexed** > 0 by day 14 |
| Hand-write 3 editorial pages: methodology, "how we compute cost per 1M tokens", one real-number teardown | 3 human-written pages live |
| Apply to **AdSense**; configure sponsor label + newsletter capture | Application submitted |

**Revenue: $0.**

**Phase 1 — Indexation and first rankings (Days 15–45)**

| Weekly action | Metric that must move |
|---|---|
| Publish the daily `/changes/<date>/` page every single day — the compounding asset | Impressions +50%/week |
| Hand-add unique analysis to 3 `/model/` pages per week | Pages ranking top-100 |
| Build Reddit karma: **9 genuine, link-free comments** in r/LocalLLaMA before any self-post | 9:1 ratio held |
| First newsletter send | Open-rate baseline |

**Cumulative revenue by day 45: $0–$30 [ESTIMATE].** AdSense approval alone takes 1–4 weeks.

**Phase 2 — Compounding and first revenue (Days 46–90)**

| Weekly action | Metric that must move |
|---|---|
| One hand-reviewed use-case page | ≥10 use-case pages indexed |
| One data-led X thread per price drop ≥10% | Referral traffic ≥15% of sessions |
| Apply to **RunPod** + **Novita**; apply to 3 GPU clouds | ≥2 referral programs approved |
| Email 10 hand-picked dev-tool sponsors with a one-page media kit | ≥1 reply |
| One **Show HN** attempt (Tue–Thu, 8–10am ET) | 1 shot fired |

**Cumulative revenue by day 90: $50–$300 [ESTIMATE]** — about $1–$3/day, not $50.

---

## 5. Traffic distribution: turning each daily price change into reach

Each daily run emits a delta table (model, old→new price, % change, new category rank). Then:

**Framing rule — what makes price-drop data shareable.** Lead with the number and the consequence, never the site name.

> ❌ "TokenPrice Watch now tracks 470 models!"
> ✅ "GPT-5 mini output dropped 40% today: $0.60 → $0.36 per 1M tokens. At 500M tokens/month that's $120/month back — roughly the price of moving your classification traffic to a smaller model."

**Only post changes with |Δ| ≥ 10%**, a new category #1, or a new model launch. Sub-1% tweaks get the account muted.

| Channel | Cadence | Rules you must respect | Realistic reach |
|---|---|---|---|
| X/Twitter | 5–10/week | None restrictive; thread with table image | 200–2,000 impressions/post early |
| r/LocalLLaMA | **≤1 post / 2 weeks** | 1/10th self-promo rule; **no affiliate links — link to GitHub/HuggingFace**; disclose affiliation; own project under *Resources*, never *News*; no LLM-generated copy; ~5 in-sub karma needed | 5k–60k views per surviving post |
| Hacker News (Show HN) | **Once** | "Show HN: TokenPrice Watch – daily LLM API price changes across 470 models"; Tue–Thu 8–10am ET; must be ad-light | 5k–20k visits if it lands |
| dev.to | Weekly | Canonical link back | 500–3,000 reads |
| LinkedIn | Weekly | Repackage for eng leaders: "your inference bill moved X% this month" — the highest-value sponsor audience | Small, high-value |
| Newsletter | Weekly | Owned channel, algorithm-proof, the asset sponsors actually buy | Compounds; 30–45% opens |
| Google Discover | Passive | Needs entity signals + large images; **upside, not a plan** | Unpredictable |

---

## 6. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| **OpenRouter API schema change** breaks the generator | High | Snapshot tests on required fields; fail loudly rather than publish zeros; keep last-good snapshot; alert on zero-row output |
| **OpenRouter rate limits / ToS change** on commercial reuse | Medium | Read the ToS now; visible attribution; aggressive caching; add provider-direct sources as a second feed |
| **Google "scaled content abuse"** on ~470 programmatic pages | **High — existential** | Hand-write the top 20 pages; inject first-party change history into every page; cap page count; monitor Search Console weekly |
| Ad network rejection (thin content / traffic quality) | Medium | Don't apply to Raptive/EthicalAds before threshold **and** editorial depth exist |
| Price data accuracy claims | Medium | "As of `<timestamp>`, source: OpenRouter, verify with provider" disclaimer; diff alerts; published correction process |
| Traffic concentrated in Reddit/HN spikes | High | Diversify to search + newsletter; never treat a spike as baseline |
| Affiliate programs never approve a new domain | Medium-high | Lean on AdSense + direct sponsors; treat provider affiliate as upside |
| Owner stops publishing 2+ weeks | Medium | Batch-generate ahead; the daily habit *is* the product |

**The 3 most likely failure causes:** (1) Google never meaningfully indexes the programmatic pages, so traffic stays near zero and nothing downstream matters; (2) the owner's daily publishing/outreach habit lapses — this is a compounding-asset business that punishes gaps; (3) traffic arrives but no monetization program is ever approved.

---

## 7. Honest assessment

**Probability of a sustained $50/day within 12 months: 20–35%, most likely ~25% [ESTIMATE].** Median expected outcome is **$300–$800/month by month 12**, not $1,500.

Assumptions: the site ranks for a meaningful share of the Tier-A keywords (plausible — a 30-referring-domain competitor already ranks top-5 on `cheapest llm api`); a newsletter reaches ~2,000 engaged subscribers; at least one sponsor deal closes; the daily change data stays differentiated. Break any one and the probability falls to **8–12%**.

**What the owner must do that cannot be automated:**

1. **Sell the first sponsor slot** — outbound email, negotiation, invoicing. The highest-leverage hour in the plan.
2. **Get approved for monetization programs** — AdSense, Raptive, EthicalAds and RunPod all involve human review, and several reject new domains on the first attempt.
3. **Be a real participant on Reddit and X** — the 9:1 ratio, the karma gate, and the "no LLM-generated copy" rule require weeks of link-free human commenting. Automated posting gets shadowbanned.
4. **Write the editorial layer by hand** — the ~20 pages that prevent a "scaled content abuse" classification are the difference between a site that ranks and one that is deindexed.
5. **Verify data accuracy and answer provider corrections** — when a vendor says a price is wrong, a human must investigate and publish the fix. In a niche built on numeric trust, one bad number costs more than a week of traffic.
6. **Handle ad-policy reviews and appeals** — Search Console manual actions, AdSense rejections and traffic-quality questions all need a human-written appeal and a real site change.

---

*All volumes, CPCs, difficulty scores, SERP compositions, backlink counts and program thresholds were observed live on 2026-10-17 via `okou seo` (DataForSEO), `okou web-search`, and primary program documentation. Items marked [ESTIMATE] or [UNVALIDATED] are not measured and must be re-validated before being relied upon.*
