import argparse
import json
from pathlib import Path
from .core import CodeGraph


def main():
    parser = argparse.ArgumentParser(prog="codegraph", description="CodeGraph Core CLI")
    sub = parser.add_subparsers(dest="cmd")

    scan = sub.add_parser("scan")
    scan.add_argument("--paths", nargs="+", default=["."])
    scan.add_argument("--summary", action="store_true")

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--q", required=True)
    prompt.add_argument("--top-k", type=int, default=5)
    prompt.add_argument("--paths", nargs="+", default=["."])

    args = parser.parse_args()
    cg = CodeGraph()

    if args.cmd == "scan":
        res = cg.scan(args.paths)
        if args.summary:
            print(json.dumps(res, indent=2))
    elif args.cmd == "prompt":
        cg.scan(args.paths)
        pack = cg.prompt_context(args.q, args.top_k)
        print(json.dumps(pack, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
