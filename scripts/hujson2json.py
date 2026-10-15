#!/usr/bin/env python3
"""Convert HuJSON (JSON with // and /* */ comments and trailing commas) to JSON on stdout.

Usage: hujson2json.py FILE [KEY ...]        keep only KEYs (all keys if none given)
       hujson2json.py FILE --drop KEY ...   keep everything except KEYs
"""
import json
import re
import sys


def strip(src: str) -> str:
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            out.append(src[i : j + 1])
            i = j + 1
        elif src.startswith("//", i):
            nl = src.find("\n", i)
            i = n if nl == -1 else nl
        elif src.startswith("/*", i):
            i = src.index("*/", i) + 2
        else:
            out.append(c)
            i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def main(argv: list[str]) -> None:
    doc = json.loads(strip(open(argv[1]).read()))
    args = argv[2:]
    if args[:1] == ["--drop"]:
        doc = {k: v for k, v in doc.items() if k not in args[1:]}
    elif args:
        doc = {k: doc[k] for k in args if k in doc}
    json.dump(doc, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv)
