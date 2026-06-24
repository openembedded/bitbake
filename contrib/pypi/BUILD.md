# Development Instructions

## Requirements

- Python >= 3.9
- pip >= 19 (for installation)

## Testing

To lint the `bitbake-setup` pypi packaging, run the ruff tool.
```bash
ruff check bin/bitbake-setup contrib/pypi
```

The steps to build and test the `bitbake-setup` pypi packaging have been automated with the `bitbake-selftest` tool.  This tool automatically creates a Python virtual environment for you.

Run the bitbake-selftest
```bash
BB_SKIP_PYPI_TESTS=no bin/bitbake-selftest -v bb.tests.setup.PyPIPackagingTest
```

## Packaging

### Create the development sandbox

To create the development sandbox run:
```bash
contrib/pypi/package-bitbake-setup.py
cd packaging_workspace
```

### Building the package

To install the development tools manually run:
```bash
python3 -m pip install -e '.[dev]'
```

To build a wheel (.whl) then use:
```bash
python3 -m build
```

This produces a wheel (.whl) file in the dist directory.  This may be installed using pip.

### Installing the package

```bash
python3 -m pip install dist/bitbake_setup-*-py3-none-any.whl
```
