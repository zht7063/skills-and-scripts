#!/usr/bin/env python3
"""Static HTML checks only; does not execute JS, render, or prove offline behavior."""
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote


class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.refs, self.resources, self.notes = [], [], [], []
        self.inline_style = False

    def resource(self, value):
        value = value.strip()
        if value and not value.startswith(('data:', '#')):
            self.resources.append(value)

    def css(self, value):
        for match in re.finditer(r'url\(\s*([\'"]?)(.*?)\1\s*\)', value, re.I):
            ref = match.group(2).strip()
            if ref.startswith('#'):
                self.refs.append(unquote(ref[1:]))
            else:
                self.resource(ref)
        if re.search(r'@import\b', value, re.I):
            self.notes.append('CSS @import found; inspect its offline dependency manually.')

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get('id'):
            self.ids.append(d['id'])
        href = d.get('href', d.get('xlink:href', ''))
        if href.startswith('#') and len(href) > 1:
            self.refs.append(unquote(href[1:]))
        for attr in ('src', 'poster'):
            if d.get(attr):
                self.resource(d[attr])
        if tag == 'object' and d.get('data'):
            self.resource(d['data'])
        if tag in ('image', 'use') and href:
            self.resource(href)
        if tag == 'link' and any(x in d.get('rel', '').split() for x in ('stylesheet', 'preload', 'icon', 'modulepreload')):
            self.resource(href)
        if d.get('srcset'):
            self.notes.append('srcset found; inspect all candidates manually.')
        for value in d.values():
            if value:
                self.css(value)
        if tag == 'style':
            self.inline_style = True

    def handle_endtag(self, tag):
        if tag == 'style':
            self.inline_style = False

    def handle_data(self, data):
        if self.inline_style:
            self.css(data)


def audit(path):
    parser = Audit()
    parser.feed(Path(path).read_text(encoding='utf-8'))
    counts = Counter(parser.ids)
    return {
        'duplicate_ids': sorted(k for k, count in counts.items() if count > 1),
        'unresolved_fragment_refs': sorted(set(parser.refs) - set(parser.ids)),
        'nonembedded_resources': sorted(set(parser.resources)),
        'manual_checks': sorted(set(parser.notes)),
        'limits': 'Static source only. JS-created IDs may resolve at runtime; JS fetch/import, rendering, mobile viewers and print require separate checks.'
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('html', type=Path)
    cli.add_argument('--strict-offline', action='store_true')
    args = cli.parse_args()
    result = audit(args.html)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    failed = bool(result['duplicate_ids'] or result['unresolved_fragment_refs'])
    if args.strict_offline:
        failed |= bool(result['nonembedded_resources'] or result['manual_checks'])
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
