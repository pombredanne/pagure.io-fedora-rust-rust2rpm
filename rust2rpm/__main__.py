import argparse
import configparser
import contextlib
from datetime import datetime, timezone
import difflib
import itertools
import os
import shlex
import shutil
import tarfile
import tempfile
import time
import subprocess

import jinja2
import requests
import tqdm

from . import Metadata

DEFAULT_EDITOR = "vi"
XDG_CACHE_HOME = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
CACHEDIR = os.path.join(XDG_CACHE_HOME, "rust2rpm")
API_URL = "https://crates.io/api/v1/"
JINJA_ENV = jinja2.Environment(loader=jinja2.ChoiceLoader([
                               jinja2.FileSystemLoader(["/"]),
                               jinja2.PackageLoader("rust2rpm", "templates"), ]),
                               trim_blocks=True, lstrip_blocks=True)

def get_default_target():
    # TODO: add fallback for /usr/lib/os-release
    with open("/etc/os-release") as os_release_file:
        conf = configparser.ConfigParser()
        conf.read_file(itertools.chain(["[os-release]"], os_release_file))
        os_release = conf["os-release"]
    os_id = os_release.get("ID")
    os_like = os_release.get("ID_LIKE")
    if os_like is not None:
        os_like = shlex.split(os_like)
    else:
        os_like = []

    # Order matters here!
    if os_id == "mageia" or ("mageia" in os_like):
        return "mageia"
    elif os_id == "fedora" or ("fedora" in os_like):
        return "fedora"
    elif "suse" in os_like:
        return "opensuse"
    else:
        return "plain"

def detect_editor():
    terminal = os.getenv("TERM")
    terminal_is_dumb = terminal is None or terminal == "dumb"
    editor = None
    if not terminal_is_dumb:
        editor = os.getenv("VISUAL")
    if editor is None:
        editor = os.getenv("EDITOR")
    if editor is None:
        if terminal_is_dumb:
            raise Exception("Terminal is dumb, but EDITOR unset")
        else:
            editor = DEFAULT_EDITOR
    return editor

def detect_packager():
    rpmdev_packager = shutil.which("rpmdev-packager")
    if rpmdev_packager is not None:
        return subprocess.check_output(rpmdev_packager, universal_newlines=True).strip()

    git = shutil.which("git")
    if git is not None:
        name = subprocess.check_output([git, "config", "user.name"], universal_newlines=True).strip()
        email = subprocess.check_output([git, "config", "user.email"], universal_newlines=True).strip()
        return "{} <{}>".format(name, email)

    return None

def file_mtime(path):
    t = datetime.fromtimestamp(os.stat(path).st_mtime, timezone.utc)
    return t.astimezone().isoformat()

def local_toml(toml, version):
    if os.path.isdir(toml):
        toml = os.path.join(toml, "Cargo.toml")

    return toml, None, version

def local_crate(crate, version):
    cratename, version = os.path.basename(crate)[:-6].rsplit("-", 1)
    return crate, cratename, version

def download(crate, version):
    if version is None:
        # Now we need to get latest version
        url = requests.compat.urljoin(API_URL, "crates/{}/versions".format(crate))
        req = requests.get(url)
        req.raise_for_status()
        versions = req.json()["versions"]
        version = next(version["num"] for version in versions if not version["yanked"])

    os.makedirs(CACHEDIR, exist_ok=True)
    cratef_base = "{}-{}.crate".format(crate, version)
    cratef = os.path.join(CACHEDIR, cratef_base)
    if not os.path.isfile(cratef):
        url = requests.compat.urljoin(API_URL, "crates/{}/{}/download#".format(crate, version))
        req = requests.get(url, stream=True)
        req.raise_for_status()
        total = int(req.headers["Content-Length"])
        with open(cratef, "wb") as f:
            for chunk in tqdm.tqdm(req.iter_content(), "Downloading {}".format(cratef_base),
                                   total=total, unit="B", unit_scale=True):
                f.write(chunk)
    return cratef, crate, version

@contextlib.contextmanager
def toml_from_crate(cratef, crate, version):
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = "{}/".format(tmpdir)
        with tarfile.open(cratef, "r") as archive:
            for n in archive.getnames():
                if not os.path.abspath(os.path.join(target_dir, n)).startswith(target_dir):
                    raise Exception("Unsafe filenames!")
            archive.extractall(target_dir)
        toml_relpath = "{}-{}/Cargo.toml".format(crate, version)
        toml = "{}/{}".format(tmpdir, toml_relpath)
        if not os.path.isfile(toml):
            raise IOError("crate does not contain Cargo.toml file")
        yield toml

def make_patch(toml, enabled=True, tmpfile=False):
    if not enabled:
        return []

    editor = detect_editor()

    mtime_before = file_mtime(toml)
    toml_before = open(toml).readlines()

    # When we are editing a git checkout, we should not modify the real file.
    # When we are editing an unpacked crate, we are free to edit anything.
    # Let's keep the file name as close as possible to make editing easier.
    if tmpfile:
        tmpfile = tempfile.NamedTemporaryFile("w+t", dir=os.path.dirname(toml),
                                              prefix="Cargo.", suffix=".toml")
        tmpfile.writelines(toml_before)
        tmpfile.flush()
        fname = tmpfile.name
    else:
        fname = toml
    subprocess.check_call([editor, fname])
    mtime_after = file_mtime(toml)
    toml_after = open(fname).readlines()
    toml_relpath = "/".join(toml.split("/")[-2:])
    diff = list(difflib.unified_diff(toml_before, toml_after,
                                     fromfile=toml_relpath, tofile=toml_relpath,
                                     fromfiledate=mtime_before, tofiledate=mtime_after))
    return diff

def _is_path(path):
    return "/" in path or path in {".", ".."}

def make_diff_metadata(crate, version, patch=False, store=False):
    if _is_path(crate):
        # Only things that look like a paths are considered local arguments
        if crate.endswith(".crate"):
            cratef, crate, version = local_crate(crate, version)
        else:
            toml, crate, version = local_toml(crate, version)
            diff = make_patch(toml, enabled=patch, tmpfile=True)
            metadata = Metadata.from_file(toml)
            return metadata.name, diff, metadata
    else:
        cratef, crate, version = download(crate, version)

    with toml_from_crate(cratef, crate, version) as toml:
        diff = make_patch(toml, enabled=patch)
        metadata = Metadata.from_file(toml)
    if store:
        shutil.copy2(cratef, os.path.join(os.getcwd(), f"{crate}-{version}.crate"))
    return crate, diff, metadata

def main():
    parser = argparse.ArgumentParser("rust2rpm",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-", "--stdout", action="store_true",
                        help="Print spec and patches into stdout")
    parser.add_argument("-t", "--target", action="store",
                        choices=("plain", "fedora", "mageia", "opensuse"), default=get_default_target(),
                        help="Distribution target")
    parser.add_argument("-p", "--patch", action="store_true",
                        help="Do initial patching of Cargo.toml")
    parser.add_argument("-s", "--store-crate", action="store_true",
                        help="Store crate in current directory")
    parser.add_argument("crate", help="crates.io name\n"
                                      "path/to/local.crate\n"
                                      "path/to/project/")
    parser.add_argument("version", nargs="?", help="crates.io version")
    args = parser.parse_args()

    crate, diff, metadata = make_diff_metadata(args.crate, args.version,
                                               patch=args.patch,
                                               store=args.store_crate)

    template = JINJA_ENV.get_template("main.spec")

    if args.patch and len(diff) > 0:
        patch_file = "{}-fix-metadata.diff".format(crate)
    else:
        patch_file = None

    kwargs = {}
    kwargs["target"] = args.target
    bins = [tgt for tgt in metadata.targets if tgt.kind == "bin"]
    libs = [tgt for tgt in metadata.targets if tgt.kind in ("lib", "rlib", "proc-macro")]
    is_bin = len(bins) > 0
    is_lib = len(libs) > 0
    if is_bin:
        kwargs["include_main"] = True
        kwargs["bins"] = bins
    elif is_lib:
        kwargs["include_main"] = False
    else:
        raise ValueError("No bins and no libs")
    kwargs["include_devel"] = is_lib

    if args.target in ("fedora", "mageia", "opensuse"):
        kwargs["include_build_requires"] = True
        kwargs["include_provides"] = False
        kwargs["include_requires"] = False
    elif args.target == "plain":
        kwargs["include_build_requires"] = True
        kwargs["include_provides"] = True
        kwargs["include_requires"] = True
    else:
        assert False, "Unknown target {!r}".format(args.target)

    if args.target == "mageia":
        kwargs["pkg_release"] = "%mkrel 1"
        kwargs["rust_group"] = "Development/Rust"
    elif args.target == "opensuse":
        kwargs["spec_copyright_year"] = time.strftime("%Y")
        kwargs["pkg_release"] = "0"
        kwargs["rust_group"] = "Development/Libraries/Rust"
    else:
        kwargs["pkg_release"] = "1%{?dist}"

    if args.target == "opensuse":
        kwargs["date"] = time.strftime("%a %b %d %T %Z %Y")
    else:
        kwargs["date"] = time.strftime("%a %b %d %Y")
    kwargs["packager"] = detect_packager()

    spec_file = "rust-{}.spec".format(crate)
    spec_contents = template.render(md=metadata, patch_file=patch_file, **kwargs)
    if args.stdout:
        print("# {}".format(spec_file))
        print(spec_contents)
        if patch_file is not None:
            print("# {}".format(patch_file))
            print("".join(diff), end="")
    else:
        with open(spec_file, "w") as fobj:
            fobj.write(spec_contents)
            fobj.write("\n")
        if patch_file is not None:
            with open(patch_file, "w") as fobj:
                fobj.writelines(diff)

if __name__ == "__main__":
    main()
