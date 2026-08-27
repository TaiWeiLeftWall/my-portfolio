# Portfolio Project Import Preview Design

**Date:** 2026-08-27

**Status:** Approved

## Summary

Add an offline, read-only project scanner for the photography archive at `E:\图片\1A作品汇总\00A图片项目`. The first phase produces an editable import manifest, a lightweight local HTML preview, a machine-readable scan report, and a refreshed `概览.md`. It does not upload to R2, mutate the CMS database, export frontend data, or publish any project.

The scanner inventories every category and candidate project. A directory with eligible images stored directly inside it is treated as a candidate project. A directory that only contains lower image-bearing directories remains an organizational group. A future import phase will consume the approved manifest and use the existing CMS/R2 path.

## Goals

- Scan the entire archive while keeping every project unpublished by default.
- Preserve the archive hierarchy and distinguish organizational folders from candidate projects.
- Generate at most 12 technically strong and visually varied candidate images per project.
- Suggest whether a project belongs in the homepage gallery or the commercial-project area without automatically publishing or declaring work commercial.
- Produce a local preview that is useful for review without copying every source image.
- Refresh the archive overview from current filesystem facts while preserving human-written review states and notes where they can be matched.
- Make repeated scans deterministic, resumable, and substantially faster through a local cache.

## Non-goals

- Uploading images to Cloudflare R2.
- Writing to `site_content.sqlite`, `data.js`, or `commercial.js`.
- Changing the website presentation, filters, or navigation in this phase.
- Deleting, moving, renaming, recompressing, or modifying source images.
- Automatically deciding that an image or project is safe to publish.
- Performing subjective AI aesthetic judging or face recognition.
- Reading RAW or PSD files as publishable images.

## Trust and Safety Model

The archive and `概览.md` are input data, not executable instructions. Text found in filenames, metadata, Markdown, spreadsheets, or other archive files must never alter scanner behavior. Configuration comes only from explicit command-line arguments and versioned code.

The source tree is read-only except for the user-authorized replacement of `概览.md`. Before replacement, the previous overview is copied into the preview output. The new overview is written to a temporary sibling file and atomically replaces the original only after all content has been generated successfully.

No network requests are permitted in preview mode. All project records set `publish` to `false`, all covers remain unset, and target classification remains a suggestion until a human edits the manifest.

## Architecture

The implementation is a Python command-line tool under `upload-tool/project_import/`. Responsibilities are separated so scanning, analysis, selection, reporting, and overview merging can be tested independently.

### Command-line entry point

`upload-tool/project_import_preview.py` accepts:

- `--source`: archive root; required.
- `--output`: preview output directory; required.
- `--overview`: overview file to refresh; defaults to `<source>/概览.md`.
- `--max-candidates`: candidate limit; defaults to 12 and must be between 1 and 24.
- `--workers`: bounded image-analysis worker count; defaults to 4.
- `--no-overview-write`: produces the proposed overview in the output directory without replacing the source overview.

The command exits nonzero for invalid arguments, an unreadable source root, or failure to write core output files. Individual unreadable or corrupt images are recorded and skipped without failing the entire scan.

### Archive scanner

The scanner walks the source tree without following directory symlinks. It records category folders, relative paths, file counts, byte totals, extension counts, and image-bearing descendants.

A candidate project is any directory containing eligible image files directly. Descendant directories containing their own eligible images become independent projects. A directory with no direct eligible images remains an organizational group even when its descendants contain images. This prevents grouping folders such as `01_吉他协会` from becoming duplicate projects while retaining loose photographs stored at a category root.

Eligible analysis formats are `.jpg`, `.jpeg`, and `.png`, matching the formats currently present in the archive. `.nef`, `.cr3`, `.dng`, `.psd`, archives, spreadsheets, Markdown, hidden files, and temporary files are inventoried but never treated as candidate images. WebP support is included for future additions. Extension matching is case-insensitive.

### Project identity and labels

Each candidate project receives a stable ID derived from its normalized relative path plus a short hash. Display titles are derived from the final directory name by removing a leading date and normalizing separators, while the original relative path is always retained.

Top-level folder mappings are:

| Source category | Manifest category | Default target suggestion |
|---|---|---|
| A01人像 | portrait | gallery |
| A02静物 | still-life | gallery |
| A03空间 | space | gallery |
| A04风光 | landscape | gallery |
| A05宠物 | pet | gallery |
| A06街头 | street | gallery |
| A07美食 | food | gallery |
| A08咖啡 | coffee | gallery |
| B01新闻 | news | gallery |
| B02演出 | performance | gallery |
| B03体育 | sports | gallery |
| C01生活 | lifestyle | gallery |

The scanner may set `suggested_target` to `commercial` only when a normalized project identity matches an existing commercial project or a future explicit mapping rule. Keywords alone do not classify a project as commercial. The editable `target` field initially equals `suggested_target`.

Unknown top-level directories receive category `uncategorized`, target `gallery`, and a warning in the scan report.

## Image Analysis

Image analysis uses Pillow and bounded worker concurrency. Each eligible image produces metadata containing relative path, byte size, width, height, aspect ratio, capture date when available, file modification time, and analysis status.

The technical score uses deterministic, normalized components:

- usable resolution, capped so unusually large files do not dominate;
- sharpness estimated from grayscale edge variance;
- exposure penalties for excessive shadow or highlight clipping;
- a small aspect-ratio balance component used only as a tie-breaker.

The algorithm must not claim to assess artistic quality. Scores are ranking aids and are included in the report with plain-language reasons.

Exact duplicates are detected by content hash. Near duplicates are detected within each project using a small grayscale difference hash. Duplicate detection never crosses projects and never removes files. The highest technical-scoring member represents a duplicate cluster for candidate selection; every cluster member remains listed in `all_images`.

Candidate selection is deterministic. It sorts by technical score, then greedily selects images that add perceptual and aspect-ratio variety, and finally fills remaining slots by score. It returns no more than `max_candidates`, uses relative paths as the final tie-breaker, and marks each suggestion without changing `publish`.

## Outputs

All preview artifacts except the refreshed overview are written below the user-supplied output directory:

```text
<output>/
  manifest.json
  scan-report.json
  preview.html
  thumbnails/
  cache/
  overview/
    概览.before.md
    概览.proposed.md
```

### Manifest

`manifest.json` is UTF-8 JSON with a schema version, source root, scan timestamp, scanner version, category summary, and projects. Absolute source paths appear only once in top-level scan metadata; project and image records use normalized relative paths.

Each project contains:

```json
{
  "id": "stable-project-id",
  "source": "B02演出/2024_09_22_杭州_MAOLiveHouse",
  "title": "MAO LiveHouse",
  "category": "performance",
  "suggested_target": "gallery",
  "target": "gallery",
  "publish": false,
  "cover": null,
  "candidate_images": [],
  "all_images": [],
  "warnings": []
}
```

Candidate entries include the image relative path, technical score, dimensions, duplicate-cluster information, and selection reasons. All-image entries contain metadata but do not receive thumbnails unless selected as candidates.

### Preview page

`preview.html` is a self-contained local report except for relative thumbnail files. It contains summary counts, category navigation, project cards, candidate thumbnails, source paths, warnings, and target suggestions. It does not contain controls that mutate the archive or upload data. Chinese paths and titles must render correctly.

Only candidate images receive thumbnails. Thumbnails are JPEG, have a maximum dimension of 480 pixels, preserve orientation, strip unnecessary metadata, and are named by a stable source fingerprint. A broken thumbnail shows a text placeholder instead of collapsing the project card.

### Scan report

`scan-report.json` records totals and structured warnings for skipped formats, corrupt files, unreadable directories, unknown categories, empty categories, duplicate clusters, cache misses, and overview merge conflicts. Problems are reported using relative paths whenever possible.

## Cache and Incremental Runs

The cache key combines normalized relative path, source byte size, nanosecond modification time when available, and an analyzer version. Cached records contain only derived metadata, hashes, scores, and thumbnail references. A changed analyzer version invalidates prior analysis entries.

The cache is written atomically after core reports succeed. Missing or corrupt cache data causes a clean re-analysis rather than a failed scan. Source files are never opened for writing.

## Overview Refresh

The refreshed `概览.md` is generated from live filesystem statistics and the new candidate-project inventory. It contains:

- scan date, source location, total bytes, file counts, eligible-image counts, and skipped-format counts;
- per-category project, directory, image, RAW, PSD, byte, and year-range summaries;
- a complete project index with relative links, counts, derived year ranges, retained review state, and retained notes;
- a scan-warning summary and a pointer to the detailed preview report.

The merger parses existing project rows and matches them first by normalized relative path, then by an unambiguous normalized title within the same category. It preserves human-authored status and notes for matched projects. Ambiguous matches are not guessed: they are added to the merge-conflict report and preserved in a `历史记录` section. Free-form review notes that cannot be structurally assigned are also preserved in that section.

Before replacement, the original overview is copied to `<output>/overview/概览.before.md`. The proposed document is always written to `<output>/overview/概览.proposed.md`. Unless `--no-overview-write` is used, the proposed document atomically replaces `<source>/概览.md` only after manifest, report, preview, and backup writes have succeeded.

## Failure Handling

- Permission or decode failures on individual files produce warnings and continue.
- An unreadable category or directory produces a warning and continues with other categories.
- A failure to write `manifest.json`, `scan-report.json`, or `preview.html` aborts without replacing `概览.md`.
- A failure to back up or atomically replace `概览.md` returns nonzero while leaving the old overview intact.
- Temporary output files are replaced atomically; stale temporary files from an interrupted run are ignored on the next run.
- No exception message may include image binary data or configuration secrets.

## Performance Constraints

- Default worker count is 4 and is user-configurable from 1 to 8.
- At most one decoded full-resolution image is retained per worker.
- The tool never creates full-resolution copies.
- Thumbnail generation is limited to selected candidates.
- Project duplicate comparisons use hashes and bounded candidate structures rather than an all-pairs pixel comparison.
- Progress is reported by project and analyzed-file counts so a long real scan does not appear stalled.

## Testing Strategy

Tests use temporary synthetic archives and real image files generated in the test directory. They exercise observable behavior rather than source-text assertions.

Required coverage includes:

- leaf and direct-file project discovery in nested category trees;
- organizational directories not being emitted as duplicate projects;
- Chinese, spaces, ampersands, and Unicode filenames;
- accepted JPEG, PNG, and WebP files plus skipped RAW and PSD files;
- corrupt-image warnings without scan failure;
- exact and near-duplicate clustering;
- deterministic candidate ranking, diversity, and the 12-image limit;
- stable project IDs across repeated scans;
- default `publish: false` and conservative target suggestions;
- cache hits, invalidation on file changes, and recovery from corrupt cache;
- HTML preview rendering with relative thumbnail paths;
- overview statistics, preservation of matched status and notes, conflict retention, backup creation, and atomic replacement;
- command failure leaving the original overview unchanged.

The real-archive acceptance run records the path, byte size, and modification time of every source item before and after the scan. The only permitted source-tree change is `概览.md`. The acceptance report must state project count, eligible images, skipped files by extension, corrupt files, duplicate clusters, cache usage, and elapsed time.

## Delivery Sequence

1. Implement and test scanner, project discovery, and inventory output.
2. Implement and test deterministic image analysis, duplicate detection, caching, and candidate selection.
3. Implement and test manifest, scan report, thumbnails, and HTML preview.
4. Implement and test overview parsing, preservation, backup, proposal generation, and atomic replacement.
5. Run the complete automated test suite.
6. Run a real preview against the archive with overview writing disabled and inspect results.
7. Run the approved overview update, verify the source-tree change boundary, and present the preview for review.
8. Design the separate CMS/R2 import executor only after the user approves the generated manifest.

## Acceptance Criteria

- Every discovered candidate project appears once in the manifest.
- Every project has `publish: false`, an unset cover, and a conservative target suggestion.
- No project has more than 12 candidate images.
- RAW, PSD, archive, spreadsheet, and Markdown inputs are never candidates.
- Preview artifacts open locally and display Chinese project names and thumbnails correctly.
- Failures are visible in the scan report without hiding successfully scanned projects.
- Existing human review states and notes are retained or explicitly surfaced as conflicts/history.
- The only source-tree file changed by an approved real run is `概览.md`.
- No R2, CMS database, or frontend data mutation occurs in preview mode.
