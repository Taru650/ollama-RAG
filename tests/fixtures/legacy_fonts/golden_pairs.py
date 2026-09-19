"""Golden (raw KrutiDev/DevLys bytes -> expected Unicode) pairs.

Raw strings pulled directly from the two real sample letters'
word/document.xml (DevLys 040 runs). Used as regression fixtures for
kru2uni() and the run-level docx decode pipeline.
"""

GOLDEN_PAIRS = [
    ("Lkkj.k lekgj.kky;] Nijk", "सारण समाहरणालय, छपरा"),
    ("oSHko JhokLro] Hkk0iz0ls0", "वैभव श्रीवास्तव, भा0प्र0से0"),
    ("ftyk inkf/kdkjh", "जिला पदाधिकारी"),
    ("lsok esa]", "सेवा में,"),
    ("egk'k;", "महाशय"),
    ("vkns'k", "आदेश"),
]

# Multi-run word split across separate <w:r> elements in the real docx
# (the "f" i-matra run and the following consonant run are siblings,
# not concatenated ahead of time) -- regression fixture for the
# run-grouping fix in docx_loader.py.
SPLIT_RUN_WORD = ("f", "tyk")  # -> "जिला" only when decoded together
SPLIT_RUN_EXPECTED = "जिला"
