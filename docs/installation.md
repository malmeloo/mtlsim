# mtlsim Installation

mtlsim is a pure-Python project, which means it can be installed and run on any platform that supports Python 3.13+. We recommend using one of the following installation methods to ensure correct operation of the program.

## Option 1: Nix Flake (recommended)

Using the Nix installation method ensures that you are using the correct Python version and that all dependencies are installed correctly. This is the recommended installation method for most users.

Install Nix from [the NixOS website](https://nixos.org/download/) and run:

```bash
nix shell github:malmeloo/mtlsim
```

This will build the simulator and drop you in a shell where the `mtlsim` command is available.

## Option 2: Python / UVX

UVX is a Python package manager that can be used to install and run mtlsim. mtlsim can be run with UVX without installing it system-wide, which can help avoid dependency conflicts.

```bash
uvx run mtlsim
```


## Option 3: Python / Pip

mtlsim is available on PyPI. It can be installed with pip:

```bash
pip install mtlsim
```

## Option 4: Manual installation

This installation option is not recommended as it may lead to compatibility issues.

Install UV, clone the repository and run the simulator with:

```bash
uv run mtlsim
```

Only Python 3.13+ is officially supported.
