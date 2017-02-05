PYTHON ?= python3
RPM ?= $(shell command -v rpm)

ifeq (,$(RPM))
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
RPMDIR ?= $(PREFIX)/lib/rpm
else
PREFIX ?= $(shell $(RPM) --eval %{_prefix})
BINDIR ?= $(shell $(RPM) --eval %{_bindir})
RPMDIR ?= $(shell $(RPM) --eval %{_rpmconfigdir})
endif

PYTHON_BIN := $(shell $(PYTHON) -c 'import sys; sys.stdout.write(sys.executable)')

define mkzipapp
	@echo "Generating $(1) zipapp"
	$(eval $@_TMP := $(shell mktemp -d))
	$(eval $@_PWD := $(shell pwd))
	cd $($@_TMP) && \
	( \
		cp -av $($@_PWD)/$(1).py __main__.py && \
		mkdir rust2rpm && \
		cp -av $($@_PWD)/rust2rpm/*.py rust2rpm/ && \
		zip -r $(1).zip . && \
		echo "#!$(PYTHON_BIN)" | cat - $(1).zip > $(1).pyz && \
		chmod 755 $(1).pyz && \
		mv -f $(1).pyz $($@_PWD) \
	) ; RET=$$? ; \
	cd - ; \
	rm -rf $($@_TMP) ; \
	exit $$RET
endef

all: rust2rpm.pyz cargodeps.pyz

rust2rpm.pyz:
	$(call mkzipapp,rust2rpm)

cargodeps.pyz:
	$(call mkzipapp,cargodeps)

install: install-rust2rpm

install-all: install-rust2rpm install-cargodeps

install-rust2rpm: rust2rpm.pyz
	install -d -m 0755 $(DESTDIR)$(BINDIR)
	@echo "Installing rust2rpm zipapp"
	install -m 0755 -p rust2rpm.pyz $(DESTDIR)$(BINDIR)/rust2rpm

install-cargodeps: cargodeps.pyz
	install -d -m 0755 $(DESTDIR)$(RPMDIR)
	@echo "Installing cargodeps zipapp"
	install -m 0755 -p cargodeps.pyz $(DESTDIR)$(RPMDIR)/cargodeps.py
	@echo "Installing RPM macro"
	install -m 0644 -p data/macros.rust-srpm $(DESTDIR)$(RPMDIR)/macros.d/macros.rust-srpm
	install -m 0644 -p data/macros.rust $(DESTDIR)$(RPMDIR)/macros.d/macros.rust
	install -m 0644 -p data/macros.cargo $(DESTDIR)$(RPMDIR)/macros.d/macros.cargo
	install -m 0644 -p data/cargo.attr $(DESTDIR)$(RPMDIR)/fileattrs/cargo.attr

clean:
	@-rm -f rust2rpm.pyz cargodeps.pyz

.PHONY: all rust2rpm.pyz cargodeps.pyz clean
