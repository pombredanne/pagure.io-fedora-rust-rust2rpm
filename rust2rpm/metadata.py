__all__ = ["Dependency", "Metadata"]

import copy
import json
import subprocess

import semantic_version as semver
import rustcfg

class Target:
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind

    def __repr__(self):
        return f"<Target {self.name} ({self.kind})>"

class Dependency:
    def __init__(self, name, req=None, features=(), optional=False):
        self.name = name
        self.req = req
        self.features = features
        self.optional = optional

    @classmethod
    def from_json(cls, metadata):
        features = set(metadata['features'])
        if metadata['uses_default_features']:
            features.add('default')
        kwargs = {'name': metadata['name'],
                  'req': metadata['req'],
                  'optional': metadata['optional'],
                  'features': features}
        return cls(**kwargs)

    @staticmethod
    def _normalize_req(req):
        if "*" in req and req != "*":
            raise NotImplementedError(f"'*' is not supported: {req}")
        spec = semver.Spec(req.replace(" ", ""))
        reqs = []
        for req in spec.specs:
            if req.kind == req.KIND_ANY:
                # Any means any
                continue
            ver = req.spec
            if ver.prerelease:
                raise NotImplementedError(f"Pre-release requirement is not supported: {ver}")
            if req.kind in (req.KIND_NEQ, req.KIND_EMPTY):
                raise NotImplementedError(f"'!=' and empty kinds are not supported: {req}")
            coerced = semver.Version.coerce(str(ver))
            if req.kind == req.KIND_EQUAL:
                req.kind = req.KIND_SHORTEQ
            if req.kind in (req.KIND_CARET, req.KIND_COMPATIBLE):
                if ver.major == 0:
                    if ver.minor is not None:
                        if ver.minor != 0 or ver.patch is None:
                            upper = ver.next_minor()
                        else:
                            upper = ver.next_patch()
                    else:
                        upper = ver.next_major()
                else:
                    upper = ver.next_major()
                reqs.append((">=", coerced))
                reqs.append(("<", upper))
            elif req.kind == req.KIND_TILDE:
                if ver.minor is None:
                    upper = ver.next_major()
                else:
                    upper = ver.next_minor()
                reqs.append((">=", coerced))
                reqs.append(("<", upper))
            elif req.kind in (req.KIND_SHORTEQ,
                              req.KIND_GT,
                              req.KIND_GTE,
                              req.KIND_LT,
                              req.KIND_LTE):
                reqs.append((str(req.kind), coerced))
            else:
                raise AssertionError(f"Found unhandled kind: {req.kind}")
        return reqs

    @staticmethod
    def _apply_reqs(name, reqs, feature=None):
        fstr = f"/{feature}" if feature is not None else ""
        cap = f"crate({name}{fstr})"
        if not reqs:
            return cap
        deps = " with ".join(f"{cap} {op} {version}" for op, version in reqs)
        if len(reqs) > 1:
            return f"({deps})"
        else:
            return deps

    def normalize(self):
        return [self._apply_reqs(self.name, self._normalize_req(self.req), feature)
                for feature in self.features or (None,)]

    def __repr__(self):
        return f"<Dependency: {self.name} {self.req} ({', '.join(sorted(self.features))})>"

    def __str__(self):
        return "\n".join(self.normalize())

class Metadata:
    def __init__(self, name, version):
        self.name = name
        self.version = version
        self.license = None
        self.license_file = None
        self.readme = None
        self.description = None
        self.targets = set()
        self.dependencies = {}
        self.dev_dependencies = set()

    @classmethod
    def from_json(cls, metadata):
        md = metadata
        self = cls(md["name"], md["version"])

        self.license = md["license"]
        self.license_file = md["license_file"]
        self.readme = md["readme"]
        self.description = md.get("description")

        # dependencies + build-dependencies → runtime
        deps_by_name = {dep["name"]: Dependency.from_json(dep)
                        for dep in md["dependencies"]
                        if dep["kind"] != "dev"}

        deps_by_feature = {}
        for feature, f_deps in md["features"].items():
            features = {None}
            deps = set()
            for dep in f_deps:
                if dep in md["features"]:
                    features.add(dep)
                else:
                    pkg, _, f = dep.partition("/")
                    dep = copy.deepcopy(deps_by_name[pkg])
                    if f:
                        dep.features = {f}
                    deps.add(dep)
            deps_by_feature[feature] = (features, deps)

        mandatory_deps = set()
        for dep in deps_by_name.values():
            if dep.optional:
                deps_by_feature[dep.name] = ({None}, {copy.deepcopy(dep)})
            else:
                mandatory_deps.add(copy.deepcopy(dep))
        deps_by_feature[None] = (set(), mandatory_deps)

        if "default" not in deps_by_feature:
            deps_by_feature["default"] = ({None}, set())

        self.dependencies = deps_by_feature
        self.dev_dependencies = {Dependency.from_json(dep)
                                 for dep in md["dependencies"]
                                 if dep["kind"] == "dev"}

        self.targets = {Target(tgt["name"], tgt["kind"][0])
                        for tgt in md["targets"]}

        return self

    @classmethod
    def from_file(cls, path):
        metadata = subprocess.check_output(["cargo", "read-manifest",
                                            f"--manifest-path={path}"])
        return cls.from_json(json.loads(metadata))

    @property
    def all_dependencies(self):
        return set().union(*(x[1] for x in self.dependencies.values()))

    def provides(self, feature=None):
        if feature not in self.dependencies:
            raise KeyError(f"Feature {feature!r} doesn't exist")
        return Dependency(self.name, f"={self.version}", features={feature})

    @classmethod
    def _resolve(cls, deps_by_feature, feature):
        all_features = set()
        all_deps = set()
        ff, dd = copy.deepcopy(deps_by_feature[feature])
        all_features |= ff
        all_deps |= dd
        for f in ff:
            ff1, dd1 = cls._resolve(deps_by_feature, f)
            all_features |= ff1
            all_deps |= dd1
        return all_features, all_deps

    def requires(self, feature=None, resolve=False):
        if resolve:
            return self._resolve(self.dependencies, feature)[1]
        else:
            features, deps = self.dependencies[feature]
            fdeps = set(Dependency(self.name, f"={self.version}", features={feature})
                        for feature in features)
            return fdeps | deps

def normalize_deps(deps):
    return set().union(*(d.normalize() for d in deps))
