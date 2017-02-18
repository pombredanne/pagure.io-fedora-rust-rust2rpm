from setuptools import setup

ARGS = dict(
    name="rust2rpm",
    version="2",
    description="Convert Rust crates to RPM",
    license="MIT",
    keywords="rust cargo rpm",

    packages=["rust2rpm"],
    entry_points={
        "console_scripts": [
            "rust2rpm = rust2rpm.__main__:main",
            "cargo-inspector = rust2rpm.inspector:main",
        ],
    },
    install_requires=[
        # Metadata parser
        "semantic_version",

        # CLI tool
        "jinja2",
        "requests",
        "tqdm",
    ],

    author="Igor Gnatenko",
    author_email="ignatenkobrain@fedoraproject.org",
    url="https://pagure.io/fedora-rust/rust2rpm",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Software Distribution",
        "Topic :: Utilities",
    ],
)

if __name__ == "__main__":
    setup(**ARGS)
