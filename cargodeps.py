#!/usr/bin/python
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import subprocess
import sys

import semantic_version as semver

REQ_TO_CON = {">": "<=",
              "<": ">=",
              ">=": "<",
              "<=": ">"}

class Dependency(object):
    def __init__(self, name, spec, feature=None, inverted=False):
        self.name = name
        self.spec = spec
        self.feature = feature
        self.inverted = inverted

    def __repr__(self):
        f_part = "/{}".format(self.feature) if self.feature is not None else ""
        if self.inverted:
            kind = REQ_TO_CON[self.spec.kind]
        else:
            kind = self.spec.kind
        return "crate({}{}) {} {}".format(self.name, f_part, kind.replace("==", "="), self.spec.spec)

class Metadata(object):
    def __init__(self, path):
        self.name = None
        self.version = None
        self._provides = []
        self._requires = []
        self._conflicts = []
        self._build_requires = []
        self._build_conflicts = []
        self._test_requires = []
        self._test_conflicts = []

        # --no-deps is to disable recursive scanning of deps
        metadata = subprocess.check_output(["cargo", "metadata", "--no-deps",
                                            "--manifest-path={}".format(path)])
        self._parse_metadata(json.loads(metadata))

    @staticmethod
    def _parse_req(s):
        if "*" in s:
            raise NotImplementedError("https://github.com/rbarrois/python-semanticversion/issues/51")
        spec = semver.Spec(s.replace(" ", ""))
        specs = spec.specs
        if len(specs) == 1:
            req = specs[0]
            if req.kind in (req.KIND_CARET, req.KIND_TILDE):
                ver = req.spec
                lower = semver.Version.coerce(str(ver))
                if req.kind == req.KIND_CARET:
                    if ver.major == 0:
                        if ver.minor is not None:
                            if ver.patch is None or ver.minor != 0:
                                upper = ver.next_minor()
                            else:
                                upper = ver.next_patch()
                        else:
                            upper = ver.next_major()
                    else:
                      upper = ver.next_major()
                elif req.kind == req.KIND_TILDE:
                    if ver.minor is None:
                        upper = ver.next_major()
                    else:
                        upper = ver.next_minor()
                else:
                    assert False
                return (semver.Spec(">={}".format(lower)).specs[0],
                        semver.Spec("<{}".format(upper)).specs[0])
            else:
                return (req, None)
        elif len(specs) == 2:
            return (specs[0], specs[1])
        else:
            # it's something uber-complicated
            raise NotImplementedError("More than two ranges are unsupported, "
                                      "probably something is wrong with metadata")
        assert False

    def _parse_metadata(self, metadata):
        md = metadata["packages"][0]
        self.name = md["name"]
        self.version = semver.SpecItem("={}".format(md["version"]))

        # Provides
        self._provides = [Dependency(self.name, self.version)]
        for feature in md["features"]:
            self._provides.append(Dependency(self.name, self.version, feature=feature))

        # Requires, Conflicts
        self._requires = []
        self._conflicts = []
        for dep in md["dependencies"]:
            if dep["kind"] is None:
                requires = self._requires
                conflicts = self._conflicts
            elif dep["kind"] == "build":
                requires = self._build_requires
                conflicts = self._build_conflicts
            elif dep["kind"] == "dev":
                requires = self._test_requires
                conflicts = self._test_conflicts
            else:
                raise ValueError("Unknown kind: {!r}, please report bug.".format(dep["kind"]))
            req, con = self._parse_req(dep["req"])
            assert req is not None
            for feature in dep["features"] or [None]:
                requires.append(Dependency(dep["name"], req, feature=feature))
                if con is not None:
                    conflicts.append(Dependency(dep["name"], con, feature=feature, inverted=True))

    @property
    def provides(self):
        return self._provides[:]

    @property
    def requires(self):
        return self._requires[:]

    @property
    def conflicts(self):
        return self._conflicts[:]

    @property
    def build_requires(self):
        return self._requires + self._build_requires

    @property
    def build_conflicts(self):
        return self._conflicts + self._build_conflicts

    @property
    def test_requires(self):
        return self._test_requires[:]

    @property
    def test_conflicts(self):
        return self._test_conflicts[:]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
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
        md = Metadata(f)
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
