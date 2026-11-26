# GTA Ranked Studio v0.7.8 — Short lifecycle and quality

## Product objective

Turn the existing GTA workflow into a repeatable content-production pipeline. The first milestone is not a new visual detector: it is preserving the editing and publishing tools throughout the lifecycle of every generated Short.

## A. Short lifecycle

A Short has an editorial status, but its assets and actions remain available independently of that status.

Suggested lifecycle:
- `draft`: generated, awaiting review
- `approved`: validated by the user
- `published`: published to one or more destinations
- `archived`: intentionally removed from active queues

The status must never control whether the user can access:
- rendered video and output folder
- thumbnail preview and download
- title, description and hashtags
- platform-specific copy text
- edit/regenerate metadata
- re-open for review

Approval should only update status and review metadata. It must not delete, clear, or hide the associated metadata, thumbnail, or render actions.

## B. Quality gates based on the supplied 60-second 1080x1920 example

Observed issues:
- Generic “HIT THAT LIKE” CTA appears at the opening before the story/action is established.
- The gameplay occupies a relatively small central band while blurred background fills much of the vertical frame.
- Captions are generally readable, but the hook and subtitles are doing similar jobs.
- The ending appears to cut off before the spoken thought resolves.

Recommended improvements:
1. Prefer a clip-specific hook based on the most interesting spoken or visual event. Do not lead with generic like/subscribe CTAs.
2. Keep CTA overlays optional and place them after the viewer has received value, or at the end.
3. Add composition presets: `full_source` (current safe default), `gameplay_larger` (larger gameplay area with controlled crop), and `dynamic_focus` (only when a reliable subject/action region is available).
4. Preserve the original full-frame mode as default until the user selects another preset.
5. Use transcript boundaries and short audio handles to avoid cutting in the middle of a phrase.
6. Add an export QA report: duration, resolution, audio presence/peak, black/frozen frames, caption bounds, and opening/ending checks.

### First-seconds retention signal (implemented on the working branch)

The candidate scorer now estimates whether a moment starts with useful activity during its first five seconds. This is an explainable audio/transcript proxy, not a measurement of actual viewer retention or gameplay understanding. It contributes 10% of the existing score so the established audio, speech and reaction signals remain dominant. The UI displays it separately, SQLite stores it with a non-destructive migration, and scans remain usable without Whisper by falling back to audio-only evidence.

## C. Detection roadmap
### Post-export quality diagnostics (implemented on the working branch)

After rendering, FFprobe validates MP4 structure, output dimensions, duration, codec and expected audio-track presence. A single FFmpeg decode pass uses blackdetect, freezedetect and silencedetect to flag likely black frames, freezes and long silence. ASS events and transcript word timings are checked against the final duration. Alerts are intentionally non-blocking: dark, static or silent gameplay may be a valid creative choice, so results remain a human-review aid.


Build a modular event pipeline:
- cheap audio and transcript prefilter
- sampled-frame visual signals (HUD/kill feed/scene changes)
- targeted higher-resolution inspection around candidate timestamps
- event fusion and explainable score
- deduplication and diversity selection

Do not label generic audio peaks as kills. Visual detections should expose confidence and evidence, and uncertain cases should remain reviewable.

## D. Batch and scale

After the single-Short lifecycle is reliable:
- batch render from a ranked candidate list
- reusable channel profiles (branding, captions, language, title style, output platforms)
- platform-specific export metadata
- publishing queue with explicit user approval
- performance ingestion and feedback loop

## E. Non-regression requirements

- Keep existing local models, videos, projects, configuration, database and exports.
- Preserve current render defaults unless the user opts into a new profile.
- Keep cancel behavior and local-first processing.
- Add tests for draft -> approved -> reload -> actions still available.
- Add tests that approved state does not mutate title/description/hashtags/thumbnail paths.


## v0.7.9 — Editorial refresh

The new thumbnail renderer creates a cleaner 1080 × 1920 editorial cover: a real gameplay frame is the visual hero, the blurred background is darkened, the GTA Ranked identity is compact, and the headline is short and readable. The headline selector removes leading filler and prefers the meaningful end of a phrase; incomplete fragments fall back to a neutral creator/GTA label.

Metadata generation now prefers a complete sentence or a short phrase anchored by a concrete GTA noun. A clipped ASR opening such as "yeah huh shit got" is not used as a quote, hook or title. If the transcript cannot support a specific event summary, the fallback stays neutral rather than inventing a car theft, recovery or reaction. Local model output is checked independently for title, description, hook and thumbnail safety.

The release candidate includes regression tests for incomplete ASR fragments, meaningful phrase extraction and the redesigned thumbnail output. Real-world review on multiple clips remains necessary before changing the conservative thresholds or claiming that the renderer understands visual game events.
