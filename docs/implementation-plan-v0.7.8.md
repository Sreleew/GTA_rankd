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

### Phrase-aware smart cutting (implemented on `feature/smart-short-editing`, not yet released)

The excerpt selector now prefers a nearby sentence or natural-pause boundary before the audio peak and keeps the complete payoff phrase plus a short reaction tail. It still preserves short source clips in full.

Automatic pause removal is intentionally conservative and requires Whisper word-level DTW timestamps. Segment-level SRT fallback never triggers jump cuts. The current limits are:
- pause must be at least 3.0 seconds
- keep 0.55 seconds of context on both sides
- protect the detected audio peak within a 2.5-second guard
- at most 2 cuts and 6 seconds removed per Short
- each retained segment must be at least 1.25 seconds

The renderer trims and concatenates video and matching audio in one FFmpeg filter graph. Captions, audio peak, dynamic zoom and thumbnail selection use the resulting joined timeline. The Short metadata records the removed pauses and retained source ranges, and the job card explains whether a cut occurred or DTW precision was unavailable.

Validation on the feature branch:
- Linux: 143 passed, 1 skipped (PowerShell-only test unavailable on Linux).
- Windows: 144 passed, no skips.
- A real FFmpeg integration test verifies a stitched MP4's output duration, audio track, vertical dimensions and generated thumbnail.

This is not part of the stable v0.7.8 release until a future version is explicitly approved and published. Real GTA clips still need editorial review to calibrate false cuts and ensure streamer reactions remain intact.

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
