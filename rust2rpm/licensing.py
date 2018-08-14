import os as _os
import sys as _sys
import csv as _csv
import functools as _functools

SPDX_TO_FEDORA_CSV = _os.path.dirname(__file__) + '/spdx_to_fedora.csv'

def translate_slashes(license):
    "Replace all slashes with OR, emit warning"
    split = [l.strip() for l in license.split("/")]
    if len(split) > 1:
        print('Upstream uses deprecated "/" syntax. Replacing with "OR"',
              file=_sys.stderr)
    return ' OR '.join(split)

@_functools.lru_cache()
def spdx_to_fedora_map():
    with open(SPDX_TO_FEDORA_CSV, newline='') as f:
        reader = _csv.DictReader(f)
        return {line['SPDX License Identifier'] : line['Fedora Short Name']
                for line in reader
                if line['SPDX License Identifier']}

def translate_license_fedora(license):
    comments = ''
    final = []
    for tag in license.split():
        # We accept all variant cases, but output lowercase which is what Fedora LicensingGuidelines specify
        if tag.upper() == 'OR':
            final.append('or')
        elif tag.upper() == 'AND':
            final.append('and')
        else:
            mapped = spdx_to_fedora_map().get(tag, None)
            if mapped is None:
                comments += f'# FIXME: Upstream uses unknown SPDX tag {tag}!'
                final.append(tag)
            elif mapped is '':
                comments += f"# FIXME: Upstream SPDX tag {tag} not listed in Fedora's good licenses list.\n"
                comments += "# FIXME: This package might not be allowed in Fedora!\n"
                final.append(tag)
            else:
                final.append(mapped)
                if mapped != tag:
                    print(f'Upstream license tag {tag} translated to {mapped}',
                          file=_sys.stderr)
    return (' '.join(final), comments or None)

def translate_license(target, license):
    license = translate_slashes(license)
    if target.startswith("fedora") or target.startswith("epel"):
        return translate_license_fedora(license)
    return license, None
