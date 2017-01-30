#!/usr/bin/python
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import subprocess
import sys

def get_metadata(path):
    # --no-deps is to disable recursive scanning of deps
    metadata = subprocess.check_output(["cargo", "metadata", "--no-deps",
                                        "--manifest-path={}".format(path)])
    return json.loads(metadata)["packages"][0]

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("-P", "--provides", action="store_true", help="Print Provides")
parser.add_argument("file", nargs="*", help="Path(s) to Cargo.toml")
args = parser.parse_args()

files = args.file or sys.stdin.readlines()

for f in files:
    f = f.rstrip()
    md = get_metadata(f)
    if args.provides:
        print("crate({}) = {}".format(md["name"], md["version"]))
