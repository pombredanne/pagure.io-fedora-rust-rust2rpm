import pytest

import rust2rpm

@pytest.mark.parametrize("req, rpmdep", [
    ("^1.2.3",
     "(crate(test) >= 1.2.3 with crate(test) < 2.0.0)"),
    ("^1.2",
     "(crate(test) >= 1.2.0 with crate(test) < 2.0.0)"),
    ("^1",
     "(crate(test) >= 1.0.0 with crate(test) < 2.0.0)"),
    ("^0.2.3",
     "(crate(test) >= 0.2.3 with crate(test) < 0.3.0)"),
    ("^0.2",
     "(crate(test) >= 0.2.0 with crate(test) < 0.3.0)"),
    ("^0.0.3",
     "(crate(test) >= 0.0.3 with crate(test) < 0.0.4)"),
    ("^0.0",
     "(crate(test) >= 0.0.0 with crate(test) < 0.1.0)"),
    ("^0",
     "(crate(test) >= 0.0.0 with crate(test) < 1.0.0)"),
    ("~1.2.3",
     "(crate(test) >= 1.2.3 with crate(test) < 1.3.0)"),
    ("~1.2",
     "(crate(test) >= 1.2.0 with crate(test) < 1.3.0)"),
    ("~1",
     "(crate(test) >= 1.0.0 with crate(test) < 2.0.0)"),
    ("*",
     "crate(test)"),
    (">= 1.2.0",
     "crate(test) >= 1.2.0"),
    ("> 1",
     "crate(test) > 1.0.0"),
    ("< 2",
     "crate(test) < 2.0.0"),
    ("= 1.2.3",
     "crate(test) = 1.2.3"),
    (">= 1.2, < 1.5",
     "(crate(test) >= 1.2.0 with crate(test) < 1.5.0)"),
])
def test_dependency(req, rpmdep):
    dep = rust2rpm.Dependency("test", req)
    assert str(dep) == rpmdep
