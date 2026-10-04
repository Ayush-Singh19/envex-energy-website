#!/usr/bin/env python3
"""src/index.html is the source. "Envex Energy Landing.dc.html" is the same file
minus the bundler-thumbnail <template>, which only the Claude Design bundler reads.
Run after every edit so the two can never drift (they silently did before)."""
import re, sys, pathlib
src = pathlib.Path('src/index.html').read_text(encoding='utf-8')
out = re.sub(r'<template id="__bundler_thumbnail".*?</template>\n', '', src, flags=re.S)
if out == src: sys.exit('thumbnail template not found in src/index.html')
pathlib.Path('Envex Energy Landing.dc.html').write_text(out, encoding='utf-8', newline='')
print('synced -> Envex Energy Landing.dc.html (%d lines)' % out.count('\n'))
