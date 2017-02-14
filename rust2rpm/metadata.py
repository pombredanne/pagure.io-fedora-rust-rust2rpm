__all__ = ["Dependency", "Metadata"]

import json
import subprocess
import sys

import semantic_version as semver

REQ_TO_CON = {">": "<=",
              "<": ">=",
              ">=": "<",
              "<=": ">"}

class Target(object):
    def __init__(self, kind, name):
        self.kind = kind
        self.name = name

    def __repr__(self):
        return "<Target {self.kind}|{self.name}>".format(self=self)

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
    def __init__(self):
        self.name = None
        self.license = None
        self.license_file = None
        self.description = None
        self._version = None
        self._targets = []
        self._provides = []
        self._requires = []
        self._conflicts = []
        self._build_requires = []
        self._build_conflicts = []
        self._test_requires = []
        self._test_conflicts = []

    @classmethod
    def from_json(cls, metadata):
        self = cls()

        md = metadata["packages"][0]
        self.name = md["name"]
        self.license = md["license"]
        self.license_file = md["license_file"]
        self.description = md.get("description")
        self._version = semver.SpecItem("={}".format(md["version"]))

        # Targets
        self._targets = [Target(tgt["kind"][0], tgt["name"]) for tgt in md["targets"]]

        # Provides
        self._provides = [Dependency(self.name, self._version)]
        for feature in md["features"]:
            self._provides.append(Dependency(self.name, self._version, feature=feature))

        # Dependencies
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

        return self

    @classmethod
    def from_file(cls, path):
        do_decode = sys.version_info < (3, 6)
        # --no-deps is to disable recursive scanning of deps
        metadata = subprocess.check_output(["cargo", "metadata", "--no-deps",
                                            "--manifest-path={}".format(path)],
                                           universal_newlines=do_decode)
        return cls.from_json(json.loads(metadata))

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

    @property
    def version(self):
        return str(self._version.spec) if self._version is not None else None

    @property
    def targets(self):
        return self._targets[:]

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
