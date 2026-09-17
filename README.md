# Hindi Government Letter RAG System

A local, offline RAG pipeline that retrieves similar past departmental
letters from a corpus of real Hindi government correspondence and
drafts a new one with Ollama + Qwen3 1.7B. Built for an 8GB RAM,
no-GPU laptop (Intel i7-8550U) -- everything here runs CPU-only.

This is **Phases 1-6** of a larger planned system: ingestion through
RAG generation. A web UI, DOCX/PDF export, an admin panel, and
optional LoRA fine-tuning are deliberately out of scope for this pass
(see "What's not built yet" below).

## Why this isn't a simple text-extraction pipeline

The two real sample letters this project was built and tested against
turned out to be typed in **legacy 8-bit Hindi fonts** (Kruti Dev
041/500, DevLys 040) rather than Unicode -- extremely common in Indian
government documents from the 2000s-2010s. A naive text extraction
produces garbage (`"Lkkj.k lekgj.kky;] Nijk"` instead of
`"सारण समाहरणालय, छपरा"`). Font usage is also mixed *within* a single
document at the XML-run level (Hindi body text in a legacy font,
English officer names/emails in genuine Unicode/Latin runs). So the
ingestion pipeline's first job is per-run legacy-font detection and
conversion -- see `src/ingestion/legacy_fonts/`.

The two sample files also turned out to hold a combined **46 distinct
letters** (45 banking-cell forwarding letters concatenated in one
`.docx`, plus one long disciplinary order as a separate file) -- not
the ~6 a quick visual skim would suggest. See
`src/ingestion/segmentation.py` for how letter boundaries are detected.

Many departments' letters exist only as scanned PDFs (no text layer at
all), which is a different problem from legacy-font decoding: there's
no encoding to fix, just pixels to read. `src/ingestion/pdf_loader.py`
tries the text layer first and falls back to OCR
(`src/ingestion/ocr.py`, Tesseract with the Hindi model) per page when
the text layer is too sparse to be real. OCR confidence and
legacy-font decode confidence share one audit signal
(`LetterRecord.needs_review` / `min_line_plausibility`) so low-quality
pages from either source get flagged the same way instead of two
separate mechanisms to remember.

## Architecture

```
docx (raw XML) -> per-run rFonts capture -> legacy-font decode -> Unicode text
              -> letter-boundary segmentation
              -> cleaning -> regex metadata extraction (+ human override sidecar)
              -> embeddings (configurable backend) -> Chroma (local, persistent)

USER REQUEST -> department auto-detect (if not given explicitly)
             -> hybrid retrieval (department filter -> letter-type filter
                                    -> BM25 keyword -> Chroma semantic -> RRF fuse)
             -> prompt builder (USER FACTS | RETRIEVED REFS [inert] | RULES)
             -> Ollama /api/chat (qwen3:1.7b) -> Hindi draft + references shown
```

Department is a first-class filter, not just a metadata tag: letters
already live under `data/letters/<department>/`, and when you ask for
a letter without passing `--department` explicitly,
`src/retrieval/department_detector.py` runs an unfiltered retrieval
pass on your request text and checks whether one department clearly
dominates the top hits. If so, generation is filtered to that
department automatically (so an Education request draws on Education
letters, not whatever happens to rank highest across every
department); if no department clearly wins, it searches everything,
same as if you'd passed no filter. This deliberately reuses the same
hybrid retriever rather than a second keyword-list classifier, so
"which department" and "which letters" never disagree with each
other.

## Project layout

```
config/settings.py           .env-driven configuration
data/letters/<department>/<office>/*.{docx,pdf,txt}   your letter corpus
src/ingestion/                docx/pdf/txt loading, legacy-font normalizer, OCR, segmentation
src/ingestion/ocr.py          Tesseract OCR fallback for scanned/image-only PDF pages
src/metadata/                 regex field extraction, human-override sidecars
src/embeddings/                pluggable Embedder (Ollama or sentence-transformers)
src/store/                    Chroma vector store wrapper
src/retrieval/                hybrid (BM25 + semantic + RRF) retrieval, department auto-detection
src/generation/                RAG prompt builder + Ollama chat client
scripts/ingest.py             index data/letters/ into the vector store
scripts/inspect_letter.py     print decoded text for manual QA
scripts/generate.py           retrieve + draft a new letter
tests/                        pytest suite, all model calls mocked/faked (OCR tests self-skip if tesseract isn't installed)
```

## Install (on your own machine -- not this build environment)

This repo was built and tested in a sandbox with no network access to
ollama.com or huggingface.co, so the steps below were never run
end-to-end with a real model here. Do this on your actual 8GB laptop:

```bash
# 1. Install Ollama, then pull the generation model
ollama pull qwen3:1.7b

# 2. Pull an embedding model. qwen3-embedding:0.6b's availability on
#    Ollama was NOT verified from the build sandbox -- try this first:
ollama pull qwen3-embedding:0.6b
#    If that fails, use the sentence-transformers fallback instead:
#    pip install sentence-transformers, and set EMBEDDING_BACKEND=sentence_transformers
#    in your .env (default already points at a small multilingual model).

# 3. If you have scanned (image-only) PDF letters, install OCR support
#    (Debian/Ubuntu; unlike Ollama, this WAS verified end-to-end in the
#    build sandbox -- tesseract-ocr + tesseract-ocr-hin + a synthetic
#    Hindi scan round-tripped through OCR exactly correctly there):
sudo apt-get install -y tesseract-ocr tesseract-ocr-hin
# If your letters are only .docx (no scanned PDFs), you can skip this --
# ingestion works fine without a tesseract binary present, it just
# can't fall back to OCR on a page with no text layer.

# 4. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 5. Config
cp .env.example .env
# edit .env if you changed the embedding backend/model above
```

## Run

```bash
# Index the letters under data/letters/
python scripts/ingest.py

# Manually inspect a converted letter before trusting the pipeline
# further -- read the printed Devanagari and confirm it isn't garbled.
python scripts/inspect_letter.py --file data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx --all

# Draft a new letter -- --department is optional now; omit it and the
# system auto-detects the department from your request text
python scripts/generate.py \
  --request "बैंक ऋण योजना समीक्षा के संबंध में जिला बैंकिंग कोषांग को पत्र तैयार करें।" \
  --fact "शाखा=उदाहरण बैंक शाखा"
```

`scripts/ingest.py` prints a list of letters flagged `needs_review`
(low legacy-font-decode confidence or, for a scanned PDF page, low OCR
confidence) -- check those with `inspect_letter.py` before trusting
them in retrieval.

Expect CPU-only generation on this hardware to take tens of seconds
per letter -- this was not benchmarked from the build sandbox, so
don't be surprised either way.

If `scripts/inspect_letter.py` shows garbled Devanagari for a letter
from your own corpus, the font-name-to-mapping-table logic in
`src/ingestion/legacy_fonts/font_family_resolver.py` likely needs a
new font name added, or (if it's a genuinely different legacy
encoding, not Kruti Dev/DevLys-compatible) a new mapping table --
`kru2uni.py` was validated only against Kruti Dev/DevLys-family fonts.

## Adding your own letters

Drop files under `data/letters/<department>/<office>/`. Department and
office names are not hardcoded anywhere -- any folder name becomes a
filterable value. Re-run `scripts/ingest.py`; it's safe to re-run
repeatedly (upserts by letter ID).

Auto-extracted metadata is never trusted blindly -- to correct a
field, create `<letter_id>.meta.json` next to the auto-generated
`.meta/<letter_id>.meta.auto.json` sidecar (same directory as the
source file, inside a `.meta/` subfolder) with just the fields you
want to override, e.g.:

```json
{"department": "education", "letter_type": "forwarding_request"}
```

Sidecar overrides always win and are never overwritten by re-ingesting.

## Testing

```bash
source .venv/bin/activate
pip install -r requirements.txt   # pytest, requests-mock included
pytest -q
```

All tests run without any live Ollama server or network access --
model-dependent components (`Embedder`, Ollama chat client) are
injected/mocked in tests. The legacy-font and segmentation tests run
against the two real sample letters committed in `data/letters/`.

## Known limitations (stated, not hidden)

1. **Corpus is thin.** Both real sample files are from one office pair
   (District Banking Cell forwarding letters + one District
   Establishment disciplinary order). Retrieval *plumbing* (filtering,
   top-k, fusion) is tested; retrieval *ranking quality* across
   departments/letter-types is not, and won't be meaningful until more
   real letters are added.
2. **Legacy-font mapping table coverage.** `kru2uni.py` (ported from
   the LTRC/IIIT-Hyderabad `kru2uni` tool, GPLv3 -- see
   `LICENSE-THIRD-PARTY.md`) was validated against the two real sample
   files and passes all committed regression fixtures, but a
   genuinely different legacy font (Chanakya, Walkman, etc.) has not
   been tested and may need a new mapping table.
3. **Segmentation heuristic.** Letter-boundary detection is anchored
   on a self-bootstrapped repeated placeholder line
   (पत्रांक/दिनांक template) and gated to avoid over-splitting
   single-letter documents. It was manually verified against both real
   files (45 + 1 = 46 letters, matching a full read-through) but hasn't
   been tested against a third format.
4. **Embedding model availability.** `qwen3-embedding:0.6b` on Ollama
   is unverified from the build sandbox; `EMBEDDING_BACKEND` is
   pluggable specifically so you can fall back to
   `sentence-transformers` without a code change.
5. **Real-hardware performance is unbenchmarked.** Qwen3 1.7B +
   an embedding model + Chroma resident on 8GB RAM/CPU-only was never
   run together in the build sandbox.
6. **OCR was validated on a synthetic scan, not a real one.** No real
   scanned PDF letter was available to test against -- the OCR path
   (`src/ingestion/ocr.py`) was verified with a Hindi phrase rendered
   to an image and PDF in-sandbox, which confirms the plumbing and
   the confidence-scoring works, but real scans (skewed, low-DPI,
   handwritten annotations, poor photocopies) will be harder and are
   untested. Always check the `needs_review` flags after ingesting
   real scans.
7. **Department auto-detection is unproven at scale.** It's tested
   against small synthetic corpora with clearly department-distinct
   vocabulary; with only two real departments actually in the corpus
   right now, it hasn't been exercised on real ambiguous cases (e.g.
   two departments both legitimately writing about "भूमि" or "बैठक").
   It always degrades safely to "search everything" rather than guess
   wrong, but that's a design choice being asserted, not yet observed
   against a large real corpus.

## What's not built yet

Web UI (FastAPI), DOCX/PDF export, the admin/data-management page, and
LoRA/QLoRA fine-tuning are all out of scope for this pass -- per the
original project plan, RAG comes first, and those are separate,
later phases.
