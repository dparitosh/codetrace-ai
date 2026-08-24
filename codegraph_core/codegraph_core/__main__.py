import argparse
import json
from pathlib import Path
from .core import CodeGraph, ScanConfig


def main():
    parser = argparse.ArgumentParser(prog="codegraph", description="CodeGraph Core CLI")
    sub = parser.add_subparsers(dest="cmd")

    scan = sub.add_parser("scan")
    scan.add_argument("--paths", nargs="+", default=["."])
    scan.add_argument("--extensions", nargs="+", help="Source extensions to scan, e.g. .py .ts")
    scan.add_argument("--exclude", nargs="*", default=[])
    scan.add_argument("--max-file-size", type=int, default=2_000_000)
    scan.add_argument("--summary", action="store_true")

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--q", required=True)
    prompt.add_argument("--top-k", type=int, default=5)
    prompt.add_argument("--paths", nargs="+", default=["."])
    prompt.add_argument("--extensions", nargs="+", help="Source extensions to scan, e.g. .py .ts")
    prompt.add_argument("--exclude", nargs="*", default=[])
    prompt.add_argument("--max-file-size", type=int, default=2_000_000)

    args = parser.parse_args()
    extensions = set(args.extensions) if getattr(args, "extensions", None) else None
    config = ScanConfig(extensions=extensions, max_file_size=args.max_file_size)
    cg = CodeGraph(config)

    if args.cmd == "scan":
        res = cg.scan(args.paths, excludes=args.exclude)
        if args.summary:
            print(json.dumps(res, indent=2))
    elif args.cmd == "prompt":
        cg.scan(args.paths, excludes=args.exclude)
        pack = cg.prompt_context(args.q, args.top_k)
        print(json.dumps(pack, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
