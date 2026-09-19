"""Kruti Dev (and font-compatible DevLys) -> Unicode Devanagari converter.

This is a Python 3 port of the ``kru2uni`` tool from the Language
Technologies Research Centre (LTRC), IIIT Hyderabad:
https://github.com/ltrc/kru2uni (GNU GPLv3, see LICENSE-THIRD-PARTY.md at
the repo root). Original authors: Nehal J Wani, Raveesh Motlani.

Do not call this on text from a run that isn't actually in a legacy
8-bit Hindi font (Kruti Dev / DevLys family) -- it will mangle genuine
Latin/English text, because the mapping works on raw character glyphs
with no notion of "this run is English". Caller (``run_decoder.py``)
is responsible for deciding, per XML run, whether to route text through
this converter.
"""
from __future__ import annotations

import re

# fmt: off
_K2U = [
    ('\xf1', '॰'), ('Q+Z', 'QZ+'), ('sas', 'sa'), ('aa', 'a'),
    (')Z', 'र्द्ध'), ('ZZ', 'Z'),
    ('‘', '"'), ('’', '"'), ('“', "'"), ('”', "'"),
    ('\xe5', '०'), ('ƒ', '१'), ('„', '२'),
    ('…', '३'), ('†', '४'), ('‡', '५'),
    ('ˆ', '६'), ('‰', '७'), ('Š', '८'),
    ('‹', '९'), ('\xb6+', 'फ़्'), ('d+', 'क़'),
    ('[+k', 'ख़'), ('[+', 'ख़्'), ('x+', 'ग़'),
    ('T+', 'ज़्'), ('t+', 'ज़'), ('M+', 'ड़'),
    ('<+', 'ढ़'), ('Q+', 'फ़'), (';+', 'य़'), ('j+', 'ऱ'),
    ('u+', 'ऩ'), ('\xd9k', 'त्त'),
    ('\xd9', 'त्त्'), ('\xe4', 'क्त'),
    ('–', 'दृ'), ('—', 'कृ'),
    ('\xe9', 'न्न'), ('™', 'न्न्'),
    ('=kk', '=k'), ('f=k', 'f='), ('\xe0', 'ह्न'),
    ('\xe1', 'ह्य'), ('\xe2', 'हृ'),
    ('\xe3', 'ह्म'), ('\xbaz', 'ह्र'),
    ('\xba', 'ह्'), ('\xed', 'द्द'),
    ('{k', 'क्ष'), ('{', 'क्ष्'),
    ('=', 'त्र'), ('\xab', 'त्र्'),
    ('N\xee', 'छ्य'), ('V\xee', 'ट्य'),
    ('B\xee', 'ठ्य'), ('M\xee', 'ड्य'),
    ('<\xee', 'ढ्य'), ('|', 'द्य'),
    ('K', 'ज्ञ'), ('}', 'द्व'),
    ('J', 'श्र'), ('V\xaa', 'ट्र'),
    ('M\xaa', 'ड्र'), ('<\xaa\xaa', 'ढ्र'),
    ('N\xaa', 'छ्र'), ('\xd8', 'क्र'),
    ('\xdd', 'फ्र'), ('nzZ', 'र्द्र'),
    ('\xe6', 'द्र'), ('\xe7', 'प्र'),
    ('\xc1', 'प्र'), ('xz', 'ग्र'),
    ('#', 'रु'), (':', 'रू'), ('v‚', 'ऑ'),
    ('vks', 'ओ'), ('vkS', 'औ'), ('vk', 'आ'), ('v', 'अ'),
    ('b\xb1', 'ईं'), ('\xc3', 'ई'), ('bZ', 'ई'),
    ('b', 'इ'), ('m', 'उ'), ('\xc5', 'ऊ'), (',s', 'ऐ'),
    (',', 'ए'), ('_', 'ऋ'), ('\xf4', 'क्क'),
    ('d', 'क'), ('Dk', 'क'), ('D', 'क्'),
    ('[k', 'ख'), ('[', 'ख्'), ('x', 'ग'),
    ('Xk', 'ग'), ('X', 'ग्'), ('\xc4', 'घ'),
    ('?k', 'घ'), ('?', 'घ्'), ('\xb3', 'ङ'),
    ('pkS', 'चै'), ('p', 'च'), ('Pk', 'च'),
    ('P', 'च्'), ('N', 'छ'), ('t', 'ज'),
    ('Tk', 'ज'), ('T', 'ज्'), ('>', 'झ'),
    ('\xf7', 'झ्'), ('\xa5', 'ञ'), ('\xea', 'ट्ट'),
    ('\xeb', 'ट्ठ'), ('V', 'ट'), ('B', 'ठ'),
    ('\xec', 'ड्ड'), ('\xef', 'ड्ढ'),
    ('M+', 'ड़'), ('<+', 'ढ़'), ('M', 'ड'),
    ('<', 'ढ'), ('.k', 'ण'), ('.', 'ण्'),
    ('r', 'त'), ('Rk', 'त'), ('R', 'त्'),
    ('Fk', 'थ'), ('F', 'थ्'), (')', 'द्ध'),
    ('n', 'द'), ('/k', 'ध'), ('/', 'ध्'),
    ('\xcb', 'ध्'), ('\xe8', 'ध'), ('u', 'न'),
    ('Uk', 'न'), ('U', 'न्'), ('i', 'प'),
    ('Ik', 'प'), ('I', 'प्'), ('Q', 'फ'),
    ('\xb6', 'फ्'), ('c', 'ब'), ('Ck', 'ब'),
    ('C', 'ब्'), ('Hk', 'भ'), ('H', 'भ्'),
    ('e', 'म'), ('Ek', 'म'), ('E', 'म्'),
    (';', 'य'), ('\xb8', 'य्'), ('j', 'र'),
    ('y', 'ल'), ('Yk', 'ल'), ('Y', 'ल्'),
    ('G', 'ळ'), ('o', 'व'), ('Ok', 'व'), ('O', 'व्'),
    ("'k", 'श'), ("'", 'श्'), ('"k', 'ष'),
    ('"', 'ष्'), ('l', 'स'), ('Lk', 'स'),
    ('L', 'स्'), ('g', 'ह'), ('\xc8', 'ीं'),
    ('saz', '्रें'), ('z', '्र'),
    ('\xcc', 'द्द'), ('\xcd', 'ट्ट'),
    ('\xce', 'ट्ठ'), ('\xcf', 'ड्ड'),
    ('\xd1', 'कृ'), ('\xd2', 'भ'), ('\xd3', '्य'),
    ('\xd4', 'ड्ढ'), ('\xd6', 'झ्'),
    ('\xdck', 'श'), ('\xdc', 'श्'), ('‚', 'ॉ'),
    ('kas', 'ों'), ('ks', 'ो'), ('kS', 'ौ'),
    ('\xa1k', 'ाँ'), ('ak', 'kं'), ('k', 'ा'),
    ('ah', 'ीं'), ('h', 'ी'), ('aq', 'ुं'),
    ('q', 'ु'), ('aw', 'ूं'), ('\xa1w', 'ूँ'),
    ('w', 'ू'), ('`', 'ृ'), ('̀', 'ृ'),
    ('as', 'ें'), ('\xb1s', 's\xb1'), ('s', 'े'),
    ('aS', 'ैं'), ('S', 'ै'), ('a\xaa', '्रं'),
    ('\xaa', '्र'), ('fa', 'ंf'), ('a', 'ं'),
    ('\xa1', 'ँ'), ('%', ':'), ('W', 'ॅ'), ('•', 'ऽ'),
    ('\xb7', 'ऽ'), ('∙', 'ऽ'), ('~j', '्र'),
    ('~', '्'), ('\\', '?'), ('+', '़'), ('^', '‘'),
    ('*', '’'), ('\xde', '“'), ('\xdf', '”'), ('(', ';'),
    ('\xbc', '('), ('\xbd', ')'), ('\xbf', '{'), ('\xc0', '}'),
    ('\xbe', '='), ('A', '।'), ('-', '.'), ('&', '-'),
    ('Œ', '॰'), (']', ','), ('~ ', '् '), ('@', '/'),
    ('\xae', 'ैं'),
]
# fmt: on

_KRUTIDEV_CONSONANTS = [
    'd', '[k', 'x', '?k', '\xb3', 'p', 'N', 't', '>', '\xa5', 'V', 'B', 'M',
    '<', '.k', 'r', 'Fk', 'n', '/k', 'u', 'i', 'Q', 'c', 'Hk', 'e', ';', 'j',
    'y', 'G', 'ऴ', 'o', "'k", '"k', 'l', 'g', 'M+', '<+', 'D', '[', 'X',
    '?', '\xb3~', 'P', 'N~', 'T', '\xf7', '\xa5~', 'V~', 'B~', 'M~', '<~',
    '.', 'R', 'F', 'n~', '/', '\xcb', '\xe8', 'U', 'I', '\xb6', 'C', 'H',
    'E', '\xb8', 'Z', 'Y', 'O', "'", 'Ü', '"', 'L', '\xba',
]

_KRUTIDEV_UNATTACHED_VOWEL_SIGNS = [
    'k', 'f', 'h', 'q', 'w', '`', 's', 'S', 'ks', 'kS', 'a', '%', '\xa1', 'W',
]

_UNICODE_UNATTACHED_VOWEL_SIGNS = [
    'ा', 'ि', 'ी', 'ु', 'ू', 'ृ', 'े',
    'ै', 'ो', 'ौ', 'ं', 'ः', 'ँ', 'ॅ',
]


def kru2uni(text: str) -> str:
    """Convert KrutiDev/DevLys-encoded text to Unicode Devanagari.

    Assumes the input is entirely in the legacy font encoding. Mixed
    Latin/English text will be mangled -- callers must only pass text
    from runs already identified as legacy-Hindi-font runs.
    """
    if not text:
        return text

    text = text.replace(' \xaa', '\xaa').replace(' ~j', '~j').replace(' z', 'z')

    for m in list(re.finditer(r'[—–]', text)):
        index = m.start()
        if index < len(text) - 1 and text[index + 1] not in (
            _KRUTIDEV_CONSONANTS + _KRUTIDEV_UNATTACHED_VOWEL_SIGNS
        ):
            text = text[:index] + '&' + text[index + 1:]

    for old, new in _K2U:
        text = text.replace(old, new)

    text = text.replace('\xb1', 'Zं')
    text = text.replace('\xc6', 'र्f')

    match = re.search('f(.?)', text)
    while match:
        grp = match.group(1)
        text = text.replace('f' + grp, grp + 'ि')
        match = re.search('f(.?)', text)

    text = text.replace('\xc7', 'fa').replace('\xaf', 'fa')
    text = text.replace('\xc9', 'र्fa')

    match = re.search('fa(.?)', text)
    while match:
        grp = match.group(1)
        text = text.replace('fa' + grp, grp + 'िं')
        match = re.search('fa(.?)', text)

    text = text.replace('\xca', 'ीZ')

    match = re.search('ि्(.?)', text)
    while match:
        grp = match.group(1)
        text = text.replace('ि्' + grp, '्' + grp + 'ि')
        match = re.search('ि्(.?)', text)

    text = text.replace('्Z', 'Z')

    match = re.search('(.?)Z', text)
    while match:
        grp = match.group(1)
        idx = text.index(grp + 'Z')
        while idx >= 0 and text[idx] in (
            'अ', 'आ', 'इ', 'ई', 'उ', 'ऊ',
            'ए', 'ऐ', 'ओ', 'औ', 'ा', 'ि',
            'ी', 'ु', 'ू', 'ृ', 'े', 'ै',
            'ो', 'ौ', 'ं', 'ः', 'ँ', 'ॅ',
        ):
            idx -= 1
            grp = text[idx] + grp
        text = text.replace(grp + 'Z', 'र्' + grp)
        match = re.search('(.?)Z', text)

    for matra in _UNICODE_UNATTACHED_VOWEL_SIGNS:
        text = text.replace(' ' + matra, matra)
        text = text.replace(',' + matra, matra + ',')
        text = text.replace('्' + matra, matra)

    text = text.replace('््र', '्र')
    text = text.replace('्र्', 'र्')
    text = text.replace('््', '्')
    text = text.replace('् ', ' ')

    return text
