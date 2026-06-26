---
name: product-ugc-seedance
description: "Create short product UGC video workflows."
version: 1.0.0
author: Alpha
license: MIT
metadata:
  hermes:
    tags: [creative, ugc, video, seedance, fal-ai, claude-code, product-marketing]
    related_skills: [creative-production-workflows, audio-music-and-shortform-media]
---

# Product UGC with Seedance

## Overview

Use this skill to turn a product concept into a short, native-feeling TikTok/Instagram-style UGC video workflow:

1. capture a one-line concept and production constraints;
2. write or adapt a short script;
3. generate a structured multi-shot Seedance prompt with timestamps;
4. optionally run the video generation via fal.ai/Seedance;
5. QA the output for drift, ad-read stiffness, product clarity, and platform fit.

Adapted from Joey Mulcahy's public Notion guide, with Alpha-specific safeguards for reusable execution and verification.

## When to use

Use when the user asks for:

- product UGC video concepts or prompts;
- TikTok/Reels-style AI product videos;
- Seedance 2.0 / fal.ai video generation;
- Claude Code skill/workflow for `/product-ugc`;
- UGC formats like selfie review, unboxing, try-on, lifestyle demo, ASMR, comparison, or product reaction.

Do **not** use for:

- long-form brand films or cinematic ads where UGC native cadence is not desired;
- videos requiring exact real-person face likeness without rights/compliance review;
- regulated product claims without source/legal review;
- cases where a static ad, product page, or real creator shoot would be simpler and better.

## Inputs to collect

Ask for or infer:

- Product name and category.
- One-line concept, e.g. `Sofia unboxes the magnesium on her desk`.
- Platform: TikTok, Reels, Shorts, paid social, organic.
- Duration target: commonly 8–20 seconds.
- Format: selfie review, unboxing, try-on, lifestyle demo, ASMR, comparison, before/after, problem-solution.
- Voice: dialogue, VO, captions-only, or no voice.
- Talent/look: age range, style, energy, accent/language, but avoid exact identity imitation.
- References available:
  - headshot / talent reference;
  - styled body shot;
  - product image;
  - optional brand/product notes.
- Mandatory claims, forbidden claims, offer/CTA, and language.

## Reference-image discipline

Seedance responds strongly to references. Avoid fighting the image with redundant visual text.

### Recommended reference order

| Reference | Meaning |
|---|---|
| `@Image1` | Headshot / talent look reference |
| `@Image2` | Styled body shot / outfit / body language |
| `@Image3` | Product image, preferably clean and well-lit |

If there is only one product image, use `@Image1` for the product and adapt the prompt accordingly.

### Critical rule

Do **not** over-describe the product visually when a product image is present. Treat the image as the source of truth. Textual product descriptions can cause visual drift when they conflict with what Seedance reads from the reference.

### Face/likeness note

Seedance/fal.ai policies may block realistic face uploads or exact face transfer. When this happens:

- describe broad non-identifying appearance traits in the prompt;
- do not promise exact face consistency;
- avoid celebrity/public-figure imitation unless explicitly licensed and policy-compliant;
- expect looser consistency across generations.

## Workflow

### 1. Pick the native UGC format

Choose the lowest-friction format that matches the product:

| Format | Best for | Notes |
|---|---|---|
| Selfie review | supplements, apps, beauty, gadgets | Casual talking head, handheld, imperfect cadence |
| Unboxing | physical products, packaging, launches | Sound-led reveal; dialogue optional |
| Try-on / apply-demo-react | beauty, apparel, wellness | Show use + micro-reaction |
| Lifestyle demo | products used in context | Product is part of a moment, not a showroom prop |
| ASMR | texture, packaging, food, beauty | No voice; close-up actions and sound cues |
| Comparison | alternatives, units, before/after | Keep claims factual and sourced |

### 2. Write the script only if needed

For dialogue/VO formats, write 1–4 short lines. Make it sound like a creator, not an ad:

- incomplete thoughts are allowed;
- avoid corporate adjectives;
- one idea per beat;
- include a casual imperfection or micro-pause;
- prefer `I tried this because...` over `Introducing...`.

For ASMR/unboxing/no-voice formats, skip script and lean on visual/action beats.

### 3. Generate the Seedance prompt

Use this structure:

```text
Create a native vertical UGC video for TikTok/Reels. Handheld phone camera, natural lighting, casual creator cadence, slightly imperfect framing, realistic everyday environment. Avoid glossy commercial polish.

References:
- @Image1: [talent/look reference or product if product-only]
- @Image2: [styled body/environment reference]
- @Image3: product reference; use this as the visual source of truth for the product.

Scene:
[One concise paragraph: location, energy, camera style, product interaction. Do not over-describe product visuals if image reference exists.]

Timeline:
0.0–2.0s — [hook action; motion starts immediately]
2.0–5.0s — [product interaction/demo beat]
5.0–8.0s — [reaction/proof/context beat]
8.0–12.0s — [close/CTA/visual payoff]

Dialogue / VO:
[Only if needed. Keep lines short and natural. Include timestamp or beat mapping.]

On-screen text:
[Optional short captions/native text overlays]

Constraints:
- Vertical 9:16.
- Native social feed feel, not a polished ad.
- Keep product consistent with @Image3.
- No extra logos, labels, or packaging changes.
- No exaggerated medical/financial/performance claims.
```

### 4. Cost and execution planning

Before running generation, estimate cost from the current provider pricing. Do not rely on stale guide pricing. As of the referenced guide, a rough estimate was `$0.30/sec` at 720p; current fal.ai search results may show different rates such as about `$0.18/sec` for some Seedance 2.0 720p modes. Verify live pricing when cost matters.

If executing through fal.ai:

- require `FAL_KEY` or configured fal.ai credentials;
- upload references in the intended order;
- log prompt, model endpoint, resolution, duration, seed/settings, and returned URL/path;
- save the prompt and output together for iteration.

### 5. QA the generated video

Review the output against:

- **Native feel:** does it look like feed content, not a TV ad?
- **First second:** is there motion/context immediately?
- **Cadence:** does dialogue feel over-scripted or too clean?
- **Product consistency:** shape, label, color, size, and packaging remain stable.
- **Reference drift:** talent, environment, hands, product do not mutate distractingly.
- **Claims:** no unsupported health, financial, legal, or performance claims.
- **Platform fit:** 9:16, safe margins for captions/UI, readable on phone.
- **CTA:** soft and natural unless paid-ad brief requires harder CTA.

Iterate by changing one thing at a time: format, opening beat, dialogue, reference order, or camera instruction.

## Prompt templates

### Selfie review

```text
Concept: [creator] casually reviews [product] after using it in [specific moment].

Create a native vertical selfie-review UGC video. Handheld front-camera feel, natural room noise, casual creator cadence, slightly imperfect framing.

References:
- @Image1: creator look reference
- @Image2: creator styling/body reference
- @Image3: product reference; use as visual source of truth.

Timeline:
0.0–1.5s — creator lifts product into frame mid-sentence, already moving.
1.5–4.0s — quick personal reason/problem context.
4.0–8.0s — shows how they use it; product remains close to camera briefly.
8.0–12.0s — small honest reaction + soft CTA.

Dialogue:
"Okay, I didn't think I'd care about this, but..."
"I've been using it for [specific routine], and it actually makes [specific outcome] easier."
"If you're already dealing with [problem], this is worth checking out."
```

### Unboxing / ASMR

```text
Create a native vertical unboxing/ASMR UGC video. No dialogue. Close handheld camera, desk surface, natural light, crisp packaging sounds, tactile movements.

References:
- @Image1: product/package reference; use as visual source of truth.

Timeline:
0.0–2.0s — hands slide package into frame and tap the box lightly.
2.0–5.0s — slow tear/open; texture and sound emphasized.
5.0–8.0s — product reveal with slight camera push-in.
8.0–12.0s — product placed in everyday context; short on-screen text appears.

On-screen text:
"tiny upgrade for my [routine]"

Constraints:
- No fake label changes.
- No extra accessories unless present in reference.
- Natural social feed feel.
```

### Lifestyle demo

```text
Create a native vertical lifestyle-demo UGC video. The product appears naturally inside a real routine rather than being presented like an ad.

References:
- @Image1: creator/look reference
- @Image2: environment/style reference
- @Image3: product reference; use as visual source of truth.

Timeline:
0.0–2.0s — creator enters frame already doing [routine].
2.0–5.0s — product is used as part of the action, not held like a billboard.
5.0–9.0s — quick payoff moment; expression/reaction stays subtle.
9.0–14.0s — close shot of product in context + soft caption.

Dialogue/VO:
[Optional, one or two casual lines only.]
```

## Common pitfalls

1. **Over-scripted ad voice** — remove brand-speak, shorten lines, add casual phrasing.
2. **Over-describing referenced products** — let image references control visuals.
3. **Too many references** — start with 1–3 clean references before adding more.
4. **No first-second motion** — static intros feel like AI ads.
5. **Exact-face expectations** — policy/model behavior can prevent direct realistic face transfer.
6. **Unsupported claims** — especially health, supplements, finance, legal, medical, and results-based claims.
7. **Changing too many variables per iteration** — isolate prompt edits.
8. **Ignoring cost** — video generation compounds quickly; estimate duration × current per-second price.

## Output format

When using this skill, return:

````md
## Product UGC Plan
- Format:
- Platform:
- Duration:
- References needed:
- Risk notes:

## Script / Beats
...

## Seedance Prompt
```text
...
```

## Execution Notes
- Model/provider:
- Estimated cost:
- Assets required:

## QA Checklist
- [ ] Native feed feel
- [ ] First-second motion
- [ ] Product consistency
- [ ] Claim safety
- [ ] 9:16/mobile-safe
````

## Verification checklist

- [ ] Prompt uses explicit reference mapping.
- [ ] Product visual description does not fight product image reference.
- [ ] Timeline has concrete action beats.
- [ ] Dialogue, if present, sounds native and short.
- [ ] Claims are safe/sourced.
- [ ] Cost estimate uses current provider pricing when execution is requested.
- [ ] Generated artifact is reviewed before claiming success.
