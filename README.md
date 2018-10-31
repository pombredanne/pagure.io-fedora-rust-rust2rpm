# rust2rpm

Convert Rust crates to RPM.

## `.rust2rpm.conf`

You can place configuration file which is used as source for additional
information for spec generation.

Some simple example would be better than many words ;)

```ini
[DEFAULT]
buildrequires =
  pkgconfig(foo) >= 1.2.3
lib.requires =
  pkgconfig(foo) >= 1.2.3

[fedora]
bin.requires =
  findutils
buildrequires =
lib.requires =
lib+default.requires =
  pkgconfig(bar) >= 2.0.0
```
