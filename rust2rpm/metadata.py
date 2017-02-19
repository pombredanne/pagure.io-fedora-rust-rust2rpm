__all__ = ["Dependency", "Metadata"]

import json
import subprocess
import sys

import semantic_version as semver

class Target(object):
    def __init__(self, kind, name):
        self.kind = kind
        self.name = name

    def __repr__(self):
        return "<Target {self.kind}|{self.name}>".format(self=self)

class Dependency(object):
    def __init__(self, name, req, features=(), provides=False):
        self.name = name
        if "*" in req:
            raise NotImplementedError("https://github.com/rbarrois/python-semanticversion/issues/51")
        self.spec = self._parse_req(req)
        self.features = features
        self.provides = provides
        if self.provides:
            if len(self.spec.specs) > 1 or \
               (len(self.spec.specs) == 1 and self.spec.specs[0].kind != self.spec.specs[0].KIND_EQUAL):
                raise Exception("Provides can't be applied to ranged version, {!r}".format(self.spec))

    def __repr__(self):
        def req_to_str(name, spec=None, feature=None):
            f_part = "/{}".format(feature) if feature is not None else ""
            basestr = "crate({}{})".format(name, f_part)
            if spec is not None:
                if spec.kind == spec.KIND_EQUAL:
                    spec.kind = spec.KIND_SHORTEQ
                return "{} {} {}".format(basestr, spec.kind, spec.spec)
            else:
                return basestr

        if self.provides:
            spec = self.spec.specs[0]
            provs = [req_to_str(self.name, spec)]
            for feature in self.features:
                provs.append(req_to_str(self.name, spec, feature))
            return " and ".join(provs)

        reqs = [req_to_str(self.name, spec=req) for req in self.spec.specs]
        features = [req_to_str(self.name, feature=feature) for feature in self.features]

        use_rich = False
        if len(reqs) > 1:
            reqstr = "({})".format(" with ".join(reqs))
            use_rich = True
        elif len(reqs) == 1:
            reqstr = reqs[0]
        else:
            reqstr = ""
        if len(features) > 0:
            featurestr = " with ".join(features)
            use_rich = True
        else:
            featurestr = ""

        if use_rich:
            if reqstr and featurestr:
                return "({} with {})".format(reqstr, featurestr)
            elif reqstr and not featurestr:
                return reqstr
            elif not reqstr and featurestr:
                return "({})".format(featurestr)
            else:
                assert False
        else:
            return reqstr

    @staticmethod
    def _parse_req(s):
        spec = semver.Spec(s.replace(" ", ""))
        parsed = []
        for req in spec.specs:
            ver = req.spec
            coerced = semver.Version.coerce(str(ver))
            if req.kind in (req.KIND_CARET, req.KIND_TILDE):
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
                parsed.append(">={}".format(coerced))
                parsed.append("<{}".format(upper))
            elif req.kind == req.KIND_NEQ:
                parsed.append(">{}".format(coerced))
                parsed.append("<{}".format(coerced))
            elif req.kind in (req.KIND_EQUAL, req.KIND_GT, req.KIND_GTE, req.KIND_LT, req.KIND_LTE):
                parsed.append("{}{}".format(req.kind, coerced))
            else:
                assert False, req.kind
        return semver.Spec(",".join(parsed))

class Metadata(object):
    def __init__(self):
        self.name = None
        self.license = None
        self.license_file = None
        self.description = None
        self.version = None
        self._targets = []
        self._provides = []
        self._requires = []
        self._build_requires = []
        self._test_requires = []

    @classmethod
    def from_json(cls, metadata):
        self = cls()

        md = metadata["packages"][0]
        self.name = md["name"]
        self.license = md["license"]
        self.license_file = md["license_file"]
        self.description = md.get("description")
        self.version = md["version"]
        version = "={}".format(self.version)

        # Targets
        self._targets = [Target(tgt["kind"][0], tgt["name"]) for tgt in md["targets"]]

        # Provides
        provides = Dependency(self.name, version, features=md["features"], provides=True)
        self._provides = str(provides).split(" and ")

        # Dependencies
        for dep in md["dependencies"]:
            if dep["kind"] is None:
                requires = self._requires
            elif dep["kind"] == "build":
                requires = self._build_requires
            elif dep["kind"] == "dev":
                requires = self._test_requires
            else:
                raise ValueError("Unknown kind: {!r}, please report bug.".format(dep["kind"]))
            requires.append(Dependency(dep["name"], dep["req"], features=dep["features"]))

        return self

    @classmethod
    def from_file(cls, path):
        do_decode = sys.version_info < (3, 6)
        # --no-deps is to disable recursive scanning of deps
        metadata = subprocess.check_output(["cargo", "metadata", "--no-deps",
                                            "--manifest-path={}".format(path)],
                                           universal_newlines=do_decode)
        return cls.from_json(json.loads(metadata))

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
    def build_requires(self):
        return self._requires + self._build_requires

    @property
    def test_requires(self):
        return self._test_requires[:]
