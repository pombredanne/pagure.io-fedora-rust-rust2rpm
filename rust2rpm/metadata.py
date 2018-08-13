__all__ = ["Dependency", "Metadata"]

import itertools
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


def _req_to_str(name, spec=None, feature=None):
    f_part = "/{}".format(feature) if feature is not None else ""
    basestr = "crate({}{})".format(name, f_part)
    if spec is None:
        return basestr
    if spec.kind == spec.KIND_EQUAL:
        spec.kind = spec.KIND_SHORTEQ
    if spec.kind == spec.KIND_ANY:
        if spec.spec == "":
            # Just wildcard
            return basestr
        else:
            # Wildcard in string
            assert False, spec.spec
    version = str(spec.spec).replace('-', '~')
    return "{} {} {}".format(basestr, spec.kind, version)

class Dependency(object):
    def __init__(self, name, req, features=(), provides=False):
        self.name = name
        self.spec = self._parse_req(req)
        self.features = features
        self.provides = provides
        if self.provides:
            if len(self.spec.specs) > 1 or \
               (len(self.spec.specs) == 1 and self.spec.specs[0].kind != self.spec.specs[0].KIND_EQUAL):
                raise Exception("Provides can't be applied to ranged version, {!r}".format(self.spec))

    def __repr__(self):
        if self.provides:
            spec = self.spec.specs[0]
            provs = [_req_to_str(self.name, spec)]
            for feature in self.features:
                provs.append(_req_to_str(self.name, spec, feature))
            return " and ".join(provs)

        reqs = [_req_to_str(self.name, spec=req) for req in self.spec.specs]
        features = [_req_to_str(self.name, feature=feature) for feature in self.features]

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
        if "*" in s and s != "*":
            # XXX: https://github.com/rbarrois/python-semanticversion/issues/51
            s = "~{}".format(s.replace(".*", "", 1))
            if ".*" in s:
                s = s.replace(".*", "")
        spec = semver.Spec(s.replace(" ", ""))
        parsed = []
        for req in spec.specs:
            ver = req.spec
            if req.kind == req.KIND_ANY:
                parsed.append("*")
                continue
            coerced = semver.Version.coerce(str(ver))
            if req.kind in (req.KIND_CARET, req.KIND_TILDE):
                if ver.prerelease:
                    # pre-release versions only match the same x.y.z
                    if ver.patch is not None:
                        upper = ver.next_patch()
                    elif ver.minor is not None:
                        upper = ver.next_minor()
                    else:
                        upper = ver.next_major()
                elif req.kind == req.KIND_CARET:
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
        self.provides = []
        self.requires = []
        self.build_requires = []
        self.test_requires = []

    @classmethod
    def from_json(cls, metadata):
        self = cls()

        md = metadata
        self.name = md["name"]
        self.license = md["license"]
        self.license_file = md["license_file"]
        self.description = md.get("description")
        self.version = md["version"]
        version = "={}".format(self.version)

        # Targets
        self.targets = [Target(tgt["kind"][0], tgt["name"]) for tgt in md["targets"]]

        # Provides
        # All optional depdencies are also features
        # https://github.com/rust-lang/cargo/issues/4911
        features = itertools.chain((x["name"] for x in md["dependencies"] if x["optional"]),
                                   md["features"])
        provides = Dependency(self.name, version, features=features, provides=True)
        self.provides = str(provides).split(" and ")

        # Dependencies
        for dep in md["dependencies"]:
            if dep["kind"] is None:
                requires = self.requires
            elif dep["kind"] == "build":
                requires = self.build_requires
            elif dep["kind"] == "dev":
                requires = self.test_requires
            else:
                raise ValueError("Unknown kind: {!r}, please report bug.".format(dep["kind"]))
            requires.append(Dependency(dep["name"], dep["req"], features=dep["features"]))

        return self

    @classmethod
    def from_file(cls, path):
        do_decode = sys.version_info < (3, 6)
        metadata = subprocess.check_output(["cargo", "read-manifest",
                                            "--manifest-path={}".format(path)],
                                           universal_newlines=do_decode)
        return cls.from_json(json.loads(metadata))
