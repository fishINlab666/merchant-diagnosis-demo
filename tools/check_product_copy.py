#!/usr/bin/env python3
"""Check selected product copy for positioning terms; not a semantic review.

Only DEFAULT_FILES and explicitly added --file targets are read. Generated
routes must be added explicitly; merchant inputs and frozen reports are not
discovered or scanned. HTML extraction is static and does not execute scripts.
"""
import argparse
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import sys


DEFAULT_FILES = ('index.html', 'README.md', '.agents/skills/merchant-diagnosis/README.md')
TERMS = re.compile(
    r'面试|求职|应聘|(?<![a-z])(?:interviews?|job[\s\-‐‑–—]+(?:seeking|hunting))(?![a-z])',
    re.IGNORECASE,
)
ATTRIBUTES = re.compile(
    r'''([^\s=<>/]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))'''
)
ENTITIES = re.compile(r'&(?:\#x[0-9a-fA-F]+|\#[0-9]+|[a-zA-Z][a-zA-Z0-9]*);?')
BLOCK_TAGS = frozenset(('address', 'article', 'aside', 'blockquote', 'br', 'button',
                        'dd', 'div', 'dl', 'dt', 'fieldset', 'figcaption', 'figure',
                        'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head',
                        'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre',
                        'section', 'table', 'td', 'th', 'title', 'tr', 'ul'))


def located(text, first_line=1):
    lines = []
    line = first_line
    for character in text:
        lines.append(line)
        if character == '\n':
            line += 1
    return text, lines


def decoded(text, first_line):
    """Retain physical source lines even when an entity decodes to a newline."""
    _, source_lines = located(text, first_line)
    chunks, lines, cursor = [], [], 0
    for match in ENTITIES.finditer(text):
        chunks.append(text[cursor:match.start()])
        lines.extend(source_lines[cursor:match.start()])
        value = unescape(match.group())
        chunks.append(value)
        lines.extend([source_lines[match.start()]] * len(value))
        cursor = match.end()
    chunks.append(text[cursor:])
    lines.extend(source_lines[cursor:])
    return ''.join(chunks), lines


class ProductHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.chunks = []
        self.lines = []
        self.attributes = []
        self.ignored = None
        self.in_head = False
        self.in_title = False

    def append(self, text, lines=None):
        self.chunks.append(text)
        self.lines.extend(lines if lines is not None else [self.getpos()[0]] * len(text))

    def handle_starttag(self, tag, attrs):
        if self.ignored:
            return
        if tag in ('script', 'style'):
            self.ignored = tag
            return
        if tag in BLOCK_TAGS:
            self.append('\n')
        if tag == 'head':
            self.in_head = True
        if tag == 'title':
            self.in_title = True
        selected = {'aria-label', 'title', 'alt'}
        if tag == 'meta':
            selected.add('content')
        raw = self.get_starttag_text()
        for match in ATTRIBUTES.finditer(raw):
            if match.group(1).lower() not in selected:
                continue
            group = next(index for index in (2, 3, 4) if match.group(index) is not None)
            line = self.getpos()[0] + raw[:match.start(group)].count('\n')
            self.attributes.append(decoded(match.group(group), line))

    def handle_endtag(self, tag):
        if self.ignored:
            if tag == self.ignored:
                self.ignored = None
            return
        if tag in BLOCK_TAGS:
            self.append('\n')
        if tag == 'head':
            self.in_head = False
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if not self.ignored and (not self.in_head or self.in_title):
            self.append(*located(data, self.getpos()[0]))

    def handle_entityref(self, name):
        if not self.ignored and (not self.in_head or self.in_title):
            self.append(unescape('&' + name + ';'))

    def handle_charref(self, name):
        self.handle_entityref('#' + name)

    def segments(self):
        return [(''.join(self.chunks), self.lines)] + self.attributes


def blank(match):
    return re.sub(r'[^\n]', ' ', match.group())


def markdown_copy(source):
    # Keep labels and code text: backticks are also used around button wording.
    # Only destination syntax and recognizable code paths are masked.
    source = re.sub(r'(?<=\])\([^\n)]*\)', blank, source)
    source = re.sub(r'^ {0,3}\[[^\]\n]+\]:[^\n]*', blank, source, flags=re.MULTILINE)
    source = re.sub(r'<(?:https?://|mailto:)[^>\n]+>', blank, source)
    path = re.compile(
        r'''[^\s`<>"'()]*\.(?:html?|md|py|[cm]?js|jsx|ts|tsx|json|csv|xlsx?|txt|pdf|zip|png|jpe?g|mp4|ya?ml|toml)\b''',
        re.IGNORECASE,
    )
    return re.sub(r'(`+)(.*?)\1', lambda match: path.sub(blank, match.group()),
                  source, flags=re.DOTALL)


def findings(source, suffix):
    if suffix.lower() in ('.html', '.htm'):
        parser = ProductHTML()
        parser.feed(source)
        parser.close()
        segments = parser.segments()
    else:
        segments = [located(markdown_copy(source))]
    found = set()
    for text, lines in segments:
        for match in TERMS.finditer(text):
            found.add((lines[match.start()], ' '.join(match.group().split())))
    return sorted(found)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                        help='Repository root; defaults to the directory containing tools/.')
    parser.add_argument('--file', action='append', default=[], metavar='PATH',
                        help='Additional product surface, relative to --root; may be repeated.')
    options = parser.parse_args()
    root = options.root.resolve()
    if not root.is_dir():
        parser.error(f'root directory not found: {root}')
    paths = dict.fromkeys((root / name).resolve() for name in (*DEFAULT_FILES, *options.file))
    errors, hits = [], []
    for path in paths:
        name = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        try:
            source = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as exc:
            errors.append(f'{name}: {type(exc).__name__}')
            continue
        hits.extend(f'{name}:{line}: {term}' for line, term in findings(source, path.suffix))
    for error in errors:
        print(error, file=sys.stderr)
    for hit in hits:
        print(hit)
    return 2 if errors else int(bool(hits))


if __name__ == '__main__':
    sys.exit(main())
