import argparse
import sys

from rust2rpm import Metadata

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-n", "--name", action="store_true", help="Print name")
    group.add_argument("-v", "--version", action="store_true", help="Print version")
    group.add_argument("-t", "--target-kinds", action="store_true", help="Print target kinds")
    group.add_argument("-P", "--provides", action="store_true", help="Print Provides")
    group.add_argument("-R", "--requires", action="store_true", help="Print Requires")
    group.add_argument("-C", "--conflicts", action="store_true", help="Print Conflicts")
    group.add_argument("-BR", "--build-requires", action="store_true", help="Print BuildRequires")
    group.add_argument("-BC", "--build-conflicts", action="store_true", help="Print BuildConflicts")
    group.add_argument("-TR", "--test-requires", action="store_true", help="Print TestRequires")
    group.add_argument("-TC", "--test-conflicts", action="store_true", help="Print TestConflicts")
    parser.add_argument("file", nargs="*", help="Path(s) to Cargo.toml")
    args = parser.parse_args()

    files = args.file or sys.stdin.readlines()

    def print_deps(deps):
        if len(deps) > 0:
            print("\n".join(str(dep) for dep in deps))

    for f in files:
        f = f.rstrip()
        md = Metadata.from_file(f)
        if args.name:
            print(md.name)
        if args.version:
            print(md.version)
        if args.target_kinds:
            print("\n".join(set(tgt.kind for tgt in md.targets)))
        if args.provides:
            print_deps(md.provides)
        if args.requires:
            print_deps(md.requires)
        if args.conflicts:
            print_deps(md.conflicts)
        if args.build_requires:
            print_deps(md.build_requires)
        if args.build_conflicts:
            print_deps(md.build_conflicts)
        if args.test_requires:
            print_deps(md.test_requires)
        if args.test_conflicts:
            print_deps(md.test_conflicts)

if __name__ == "__main__":
    main()
