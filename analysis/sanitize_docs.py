"""Enmascara valores individuales del dataset (IDs, emails, números de tarjeta) antes de publicar.

El repo es público y las bases prohíben publicar registros del dataset: los reportes solo deben
tener agregados. Correr antes de cada commit:
  python analysis/sanitize_docs.py            # reescribe docs/*.md y README.md
  python analysis/sanitize_docs.py --check    # solo verifica (sale con 1 si encuentra algo)
  python analysis/sanitize_docs.py --check analysis/pass3   # también sirve para carpetas de scripts
"""
import argparse
import glob
import os
import re
import sys

PATTERNS = [
    (re.compile(r"\b(CLI|PRD|TRX|INT|TRS|CMP|SRV|AGT|SUC|EVT|SES|SND)-[A-Z0-9]{4,}\b"), r"\1-<id>"),
    (re.compile(r"\b[\w.+-]+@(?!users\.noreply\.github\.com)[\w-]+\.[\w.-]+\b"), "<email>"),
    (re.compile(r"\b(?!9007199254740992\b)\d{16}\b"), "<numero_tarjeta>"),  # excluye 2^53 (constante del RNG)
    (re.compile(r"\bE\d{5}\b"), "E<codigo>"),
]


def sanitize(text):
    count = 0
    for pattern, repl in PATTERNS:
        text, n = pattern.subn(repl, text)
        count += n
    return text, count


def targets(paths):
    for p in paths:
        if os.path.isdir(p):
            yield from glob.glob(os.path.join(p, "**", "*.md"), recursive=True)
            yield from glob.glob(os.path.join(p, "**", "*.py"), recursive=True)
        elif os.path.exists(p):
            yield p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", default=["docs", "README.md"])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    total = 0
    for path in targets(args.paths):
        text = open(path, encoding="utf-8").read()
        clean, n = sanitize(text)
        if n:
            total += n
            print(f"{path}: {n} valores {'encontrados' if args.check else 'enmascarados'}")
            if not args.check:
                open(path, "w", encoding="utf-8").write(clean)
    if args.check and total:
        sys.exit(1)
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
