# Hindi Government Letter RAG System

A local, offline RAG pipeline that retrieves similar past departmental
letters from a corpus of real Hindi government correspondence and
drafts a new one with Ollama + Qwen3 1.7B. Built for an 8GB RAM,
no-GPU laptop (Intel i7-8550U) -- everything here runs CPU-only.

This covers ingestion through RAG generation, a local web UI (FastAPI)
for drafting and downloading letters, DOCX/PDF export, and an
admin/data-management page for uploading, reviewing, correcting, and
deleting corpus documents. Optional LoRA fine-tuning is still out of
scope (see "What's not built yet" below) -- per the original project
plan, RAG comes first, and fine-tuning is only worth doing if
evaluation later shows RAG alone isn't enough.

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
              -> embeddings (configurable backend) -> local vector store (pure Python + numpy, persistent)

USER REQUEST -> department auto-detect (if not given explicitly)
             -> hybrid retrieval (department filter -> letter-type filter
                                    -> BM25 keyword -> vector-store semantic -> RRF fuse)
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
src/ingestion/indexing.py     shared LetterRecord -> vector store logic (used by CLI and web app alike)
src/metadata/                 regex field extraction, human-override sidecars
src/embeddings/                pluggable Embedder (Ollama or sentence-transformers)
src/store/                    local vector store (pure Python + numpy, no native extensions)
src/retrieval/                hybrid (BM25 + semantic + RRF) retrieval, department auto-detection
src/generation/                RAG prompt builder + Ollama chat client
src/export/                    DOCX rendering + DOCX->PDF via headless LibreOffice
app/                            FastAPI app: routers (generate/catalog/export/admin), dependencies, schemas
static/                         plain HTML/CSS/JS frontend (no build step, no CDN -- offline-first)
scripts/ingest.py             index data/letters/ into the vector store
scripts/inspect_letter.py     print decoded text for manual QA
scripts/generate.py           retrieve + draft a new letter (CLI)
scripts/run_web.py             start the web app
tests/                        pytest suite, all model calls mocked/faked (OCR/PDF tests self-skip if the system deps aren't installed)
```

## Install (on your own machine -- not this build environment)

This repo was built and tested in a Linux sandbox with no network
access to ollama.com or huggingface.co, so the steps below were never
run end-to-end with a real model here. Pick the section for your OS.

### Linux / macOS

```bash
# 1. Install Ollama, then pull the generation model
ollama pull qwen3:1.7b

# 2. Pull the embedding model (default EMBEDDING_BACKEND=ollama uses this):
ollama pull qwen3-embedding:0.6b
#    If that's unavailable, use the sentence-transformers fallback
#    instead: pip install sentence-transformers, and set
#    EMBEDDING_BACKEND=sentence_transformers + EMBEDDING_MODEL to a
#    HuggingFace model name (e.g. intfloat/multilingual-e5-small) in
#    your .env. Not installed by default -- it pulls in torch and
#    scikit-learn, both with compiled native extensions.

# 3. If you have scanned (image-only) PDF letters, install OCR support
#    (Debian/Ubuntu; unlike Ollama, this WAS verified end-to-end in the
#    build sandbox -- tesseract-ocr + tesseract-ocr-hin + a synthetic
#    Hindi scan round-tripped through OCR exactly correctly there):
sudo apt-get install -y tesseract-ocr tesseract-ocr-hin
# If your letters are only .docx (no scanned PDFs), you can skip this --
# ingestion works fine without a tesseract binary present, it just
# can't fall back to OCR on a page with no text layer.

# 3b. For PDF export, install LibreOffice Writer specifically -- NOT
#     just `libreoffice` or `libreoffice-core`, which have no document
#     filters at all and fail to even load a .docx (found and fixed
#     during this project's own build: `soffice --convert-to pdf`
#     silently errored with "source file could not be loaded" until
#     libreoffice-writer was installed). Also verified end-to-end here
#     -- generated a real letter, converted it, and visually confirmed
#     correct Devanagari conjunct/matra shaping in the output PDF.
sudo apt-get install -y libreoffice-writer
# A Devanagari font also needs to be installed for the PDF to render
# correctly (not just be present as text) -- Noto Sans Devanagari
# (this project's default, DOCX_FONT_NAME in .env) or Windows' Nirmala
# UI/Mangal work too if already installed:
sudo apt-get install -y fonts-noto-core
# Skip 3b entirely if you only need DOCX export -- that has no
# external dependency beyond python-docx.

# 4. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 5. Config
cp .env.example .env
# edit .env if you changed the embedding backend/model above
```

### Windows

Native Windows support needed two real fixes beyond "just run the
Linux steps," both applied in this repo, not left as workarounds you
have to remember:

- The vector store is pure Python + numpy (`src/store/vector_store.py`),
  not ChromaDB. ChromaDB's dependency tree (`chroma-hnswlib`, a C
  extension with spotty prebuilt Windows wheel coverage requiring MSVC
  Build Tools to build from source; opentelemetry's gRPC exporter,
  which unconditionally loads a native DLL that Windows Application
  Control / Smart App Control blocks on a stock machine even with
  telemetry disabled) caused unrecoverable install/import failures
  during this project's own Windows testing. numpy has solid prebuilt
  wheels everywhere and needs no OS-level security exception.
- PDF export (`src/export/pdf_export.py`) now finds `soffice.exe` even
  when the LibreOffice installer didn't add it to PATH (checks the
  default `C:\Program Files\LibreOffice\...` locations), and builds
  its temporary-profile URI with `Path.as_uri()` instead of manual
  string concatenation, so it works correctly even when your project
  path contains spaces (e.g. `C:\Projects\ollama rag letters\...`).

```powershell
# 1. Install Python 3.11+ (Python 3.14 currently lacks prebuilt wheels
#    for some dependencies on Windows). If `py -3.11` doesn't find one:
winget install --id Python.Python.3.11 -e

# 2. Install Ollama (https://ollama.com/download/windows), then:
ollama pull qwen3:1.7b
ollama pull qwen3-embedding:0.6b
#    (default EMBEDDING_BACKEND=ollama uses this -- confirmed working
#    end-to-end on Windows during this project's own testing). If
#    that's unavailable, the sentence-transformers fallback is NOT
#    recommended on Windows: it pulls in torch and scikit-learn, and
#    scikit-learn's compiled Cython extension has been confirmed
#    blocked by Windows Smart App Control on at least one real
#    machine (the same failure mode as chromadb's gRPC DLL -- see
#    above). Try disabling Smart App Control, or WSL2, before falling
#    back to it on Windows.

# 3. If you have scanned (image-only) PDF letters, install Tesseract
#    OCR with the Hindi language pack (UB-Mannheim installer is the
#    common choice: https://github.com/UB-Mannheim/tesseract/wiki).
#    Make sure "Hindi" is checked in the installer's language list, or
#    ingestion will fall back to English-only OCR on scanned pages.
#    Skip this if your letters are only .docx (no scanned PDFs).

# 3b. For PDF export, install LibreOffice
#     (https://www.libreoffice.org/download/) with the default
#     components (Writer included). It doesn't need to be on PATH --
#     this project checks the standard install locations automatically.
#     Skip this entirely if you only need DOCX export.

# 4. Python environment
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 5. Config
copy .env.example .env
# edit .env if you changed the embedding backend/model above
```

Hindi text printed to a plain `cmd.exe`/PowerShell console can raise
`UnicodeEncodeError` on Windows' legacy code-page default; every
script under `scripts/` forces UTF-8 console I/O on startup
(`scripts/_console.py`) so this shouldn't come up, but if you see it
from your own code, `sys.stdout.reconfigure(encoding="utf-8")` is the
fix.

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

Expect CPU-only generation on 8GB hardware to take a while -- real
end-to-end testing hit Ollama's default 300s client timeout on a
single letter, so "tens of seconds" was too optimistic. The client
timeout defaults to `GENERATION_TIMEOUT_SECONDS=600` (10 minutes) for
this reason; raise it further in `.env` if you still see a
`ReadTimeout`.

If `scripts/inspect_letter.py` shows garbled Devanagari for a letter
from your own corpus, the font-name-to-mapping-table logic in
`src/ingestion/legacy_fonts/font_family_resolver.py` likely needs a
new font name added, or (if it's a genuinely different legacy
encoding, not Kruti Dev/DevLys-compatible) a new mapping table --
`kru2uni.py` was validated only against Kruti Dev/DevLys-family fonts.

## Web UI

```bash
python scripts/run_web.py
# then open http://127.0.0.1:8000/  (letter drafting)
#      and http://127.0.0.1:8000/admin.html  (data management)
```

The generation page lets you pick a department (or leave it blank for
auto-detection), enter your request and any known facts, generate a
draft, edit it inline, and download it as `.docx` or `.pdf`. The admin
page lists every source document with its segment count and how many
segments are flagged `needs_review`, lets you upload a new file
(assigning department/office), view a document's extracted text per
letter, correct a letter's department/type/subject (writes the same
`.meta.json` sidecar the CLI respects), delete a whole document (file
+ its index entries) or just drop one bad segment from the index
without touching its source file, search across everything, and
rebuild the whole index from disk.

No frontend build step and no CDN dependencies (fonts, JS, CSS are all
served locally) -- matches the project's local/offline-first
requirement; the browser renders Devanagari using whatever font is
actually installed on your machine (`DOCX_FONT_NAME` in `.env`
controls the *export* font specifically, independent of what the
browser picks for on-screen display).

The server starts and serves both pages even without a running Ollama
server -- only `POST /api/generate` needs one; browsing/uploading/
editing the corpus doesn't.

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
   was unverified from the build sandbox but has since been confirmed
   pullable (`ollama pull qwen3-embedding:0.6b`) on a real Windows
   machine. `EMBEDDING_BACKEND=ollama` is the default for this reason:
   it's a pure HTTP call to your Ollama server with no local ML
   library and nothing for Windows Smart App Control/WDAC to block.
   `EMBEDDING_BACKEND` is still pluggable if you'd rather use
   `sentence-transformers` (not installed by default -- see
   requirements.txt), but that backend pulls in torch and
   scikit-learn, both of which ship compiled native extensions and hit
   the same class of Smart App Control block as chromadb did (see
   "Windows" install section above) on at least one real machine this
   project was tested against.
5. **Real-hardware performance is unbenchmarked.** Qwen3 1.7B +
   an embedding model + the local vector store resident on 8GB
   RAM/CPU-only was never run together in the build sandbox.
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
8. **Web UI end-to-end generation flow is untested with a real model.**
   The FastAPI app, its routes, and both pages were tested with a real
   browser (Playwright) and a real uploaded/ingested/deleted document
   round-trip through the actual admin API -- but `POST /api/generate`
   itself was only exercised with a faked Ollama response (same
   constraint as the CLI: no live Ollama server reachable from the
   build sandbox). DOCX and PDF export *were* verified with real
   output files, including visually confirming correct Devanagari
   rendering in the PDF.
9. **No auth on the web UI.** It binds to `127.0.0.1` by default
   (`WEB_HOST` in `.env`) for local-machine use. If you expose it on a
   network, put it behind your own auth/reverse proxy first -- nothing
   here does that for you.
10. **Admin delete is real deletion.** "Delete document" removes the
    source file from disk and its entries from the index; there's a
    browser confirm dialog but no undo. "Delete letter" (one segment)
    only touches the index, not the source file.

## What's not built yet

Optional LoRA/QLoRA fine-tuning is the only piece still out of scope --
per the original project plan, RAG comes first, and fine-tuning is
only worth pursuing if evaluation later shows RAG alone falls short.
