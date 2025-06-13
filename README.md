# Loco

[![Build and test loco](https://github.com/Daniel-Brai/Loco/actions/workflows/ci.yml/badge.svg)](https://github.com/Daniel-Brai/Loco/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Daniel-Brai/Loco/branch/main/graph/badge.svg)](https://codecov.io/gh/Daniel-Brai/Loco)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Fast, reliable localhost tunneling for web developers

Loco makes it dead simple to expose your local web applications to the internet.
Built with Python for simplicity, whether you're testing webhooks,
sharing work-in-progress with clients, or accessing your dev environment remotely,
Loco gets you there without the hassle.

## Why Loco?

- **Zero configuration** - Works out of the box
- **Lightning fast** - Optimized Python implementation with asyncio
- **Secure by default** - Built-in HTTPS and authentication
- **Developer friendly** - Clean CLI, detailed logs, easy integration
- **Rock solid** - Stable tunnels that don't drop connections
- **Pure Python** - Easy to install, modify, and extend

## Installation

### Requirements

- Python 3.12 or higher
- Linux, macOS, or Windows

### Install from PyPI (recommended)

```bash
pip install loco
```

### Build and Install from Source

1. Clone the repository:

```bash
git clone https://github.com/Daniel-Brai/Loco.git
cd Loco
```

2. Install dependencies and build:

```bash
# Using pip
pip install -e .

# Using uv (recommended)
uv pip install -e .
```

### Development Setup

1. Clone the repository:

```bash
git clone https://github.com/Daniel-Brai/Loco.git
cd Loco
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:

```bash
# Using pip
pip install -e ".[dev]"

# Using uv
uv pip install -e ".[dev]"
```

4. Set up pre-commit hooks:

```bash
pre-commit install
```

### Verify Installation

After installation, verify that Loco is working:

```bash
loco --version
```

This should display the Loco banner with version information.

## TODO

- [ ] Add support for custom domains (This may require DNS configuration or require me to set up a custom DNS service)
- [ ] Implement advanced authentication options
- [ ] Improve error handling and logging
- [ ] Add more detailed documentation
- [ ] Add more tests
