import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

import pytest

import rust2rpm

DUMMY_LIB = """
pub fn say_hello() {
    println!("Hello, World!");
}
"""
DEPGEN = os.path.join(os.path.dirname(__file__), "cargodeps.py")


@pytest.mark.parametrize("req, features, rpmdep", [
    ("=1.0.0", [],
     "crate(test) = 1.0.0"),
    ("=1.0.0", ["feature"],
     "(crate(test) = 1.0.0 with crate(test/feature))"),
    (">=1.0.0,<2.0.0", [],
     "(crate(test) >= 1.0.0 with crate(test) < 2.0.0)"),
    (">=1.0.0,<2.0.0", ["feature"],
     "((crate(test) >= 1.0.0 with crate(test) < 2.0.0) with crate(test/feature))"),
])
def test_dependency(req, features, rpmdep):
    dep = rust2rpm.Dependency("test", req, features)
    assert str(dep) == rpmdep

@pytest.fixture
def cargo_toml(request):
    def make_cargo_toml(contents):
        toml = os.path.join(tmpdir, "Cargo.toml")
        with open(toml, "w") as fobj:
            fobj.write(textwrap.dedent(contents))
        return toml

    tmpdir = tempfile.mkdtemp(prefix="cargo-deps-")
    srcdir = os.path.join(tmpdir, "src")
    os.mkdir(srcdir)
    with open(os.path.join(srcdir, "lib.rs"), "w") as fobj:
        fobj.write(DUMMY_LIB)

    def finalize():
        shutil.rmtree(tmpdir)
    request.addfinalizer(finalize)

    return make_cargo_toml

@pytest.mark.parametrize("toml, provides, requires", [

    # Basic provides
    ("""
     [package]
     name = "hello"
     version = "0.0.0"
     """,
     ["crate(hello) = 0.0.0"],
     []),

    # Basic provides for feature
    ("""
     [package]
     name = "hello"
     version = "1.2.3"

     [features]
     color = []
     """,
     ["crate(hello) = 1.2.3",
      "crate(hello/color) = 1.2.3"],
     []),

    # Caret requirements
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "^0"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 0.0.0 with crate(libc) < 1.0.0)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "^0.0"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 0.0.0 with crate(libc) < 0.1.0)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "^0.0.3"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 0.0.3 with crate(libc) < 0.0.4)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "^0.2.3"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 0.2.3 with crate(libc) < 0.3.0)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "^1"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.0.0 with crate(libc) < 2.0.0)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "^1.2"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.2.0 with crate(libc) < 2.0.0)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "^1.2.3"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.2.3 with crate(libc) < 2.0.0)"]),

    # Tilde requirements
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "~1"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.0.0 with crate(libc) < 2.0.0)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "~1.2"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.2.0 with crate(libc) < 1.3.0)"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "~1.2.3"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.2.3 with crate(libc) < 1.3.0)"]),

    # Wildcard requirements
    pytest.mark.xfail(("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "*"
     """,
     ["crate(hello) = 0.0.0"],
     ["crate(libc) >= 0.0.0"])),
    pytest.mark.xfail(("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "1.*"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.0.0 with crate(libc) < 2.0.0)"])),
    pytest.mark.xfail(("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "1.2.*"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.2.0 with crate(libc) < 1.3.0)"])),

    # Inequality requirements
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = ">= 1.2.0"
     """,
     ["crate(hello) = 0.0.0"],
     ["crate(libc) >= 1.2.0"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "> 1"
     """,
     ["crate(hello) = 0.0.0"],
     ["crate(libc) > 1.0.0"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "< 2"
     """,
     ["crate(hello) = 0.0.0"],
     ["crate(libc) < 2.0.0"]),
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = "= 1.2.3"
     """,
     ["crate(hello) = 0.0.0"],
     ["crate(libc) = 1.2.3"]),

    # Multiple requirements
    ("""
     [package]
     name = "hello"
     version = "0.0.0"

     [dependencies]
     libc = ">= 1.2, < 1.5"
     """,
     ["crate(hello) = 0.0.0"],
     ["(crate(libc) >= 1.2.0 with crate(libc) < 1.5.0)"]),

])
def test_depgen(toml, provides, requires, cargo_toml):
    md = rust2rpm.Metadata.from_file(cargo_toml(toml))
    assert [str(x) for x in md.provides] == provides
    assert [str(x) for x in md.requires] == requires
