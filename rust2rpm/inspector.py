import argparse
import sys

from . import Metadata
from .metadata import normalize_deps

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-n", "--name", action="store_true", help="Print name")
    group.add_argument("-v", "--version", action="store_true", help="Print version")
    group.add_argument("-t", "--target-kinds", action="store_true", help="Print target kinds")
    group.add_argument("-l", "--list-features", action="store_true", help="Print features")
    group.add_argument("-P", "--provides", action="store_true", help="Print Provides")
    group.add_argument("-R", "--requires", action="store_true", help="Print Requires")
    group.add_argument("-BR", "--build-requires", action="store_true", help="Print BuildRequires")
    group.add_argument("-TR", "--test-requires", action="store_true", help="Print TestRequires")
    parser.add_argument("-f", "--feature", help="Feature to work on")
    parser.add_argument("file", nargs="*", help="Path(s) to Cargo.toml")
    args = parser.parse_args()

    files = args.file or sys.stdin.readlines()

    if not args.feature:
        args.feature = None

    def print_deps(deps):
        if len(deps) > 0:
            print("\n".join(sorted(normalize_deps(deps))))

    for f in files:
        f = f.rstrip()
        md = Metadata.from_file(f)
        if args.name:
            print(md.name)
        if args.version:
            print(md.version)
        if args.target_kinds:
            print("\n".join(set(tgt.kind for tgt in md.targets)))
        if args.list_features:
            for f in sorted(f for f in md.dependencies if f is not None):
                print(f)
        if args.provides:
            print(md.provides(args.feature))
        if args.requires:
            # Someone should own /usr/share/cargo/registry
            print("cargo")
            print_deps(md.requires(args.feature))
        if args.build_requires:
            print("rust-packaging")
            print_deps(md.requires(args.feature or "default", resolve=True))
        if args.test_requires:
            print_deps(md.dev_dependencies)

if __name__ == "__main__":
    main()
