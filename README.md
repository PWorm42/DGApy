[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/PaulWorm/DGApy/graphs/commit-activity)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://opensource.org/license/mit/)
[![Documentation Status](https://readthedocs.org/projects/dgapy/badge/?version=latest)](https://dgapy.readthedocs.io/en/latest/)
[![DOI](https://zenodo.org/badge/731899515.svg)](https://zenodo.org/doi/10.5281/zenodo.10406492)

[//]: # ([![coverage]&#40;./coverage.svg&#41;]&#40;&#41;)

[//]: # ([![pipeline status]&#40;https://gitlab.com/PWorm/dga/badges/main/pipeline.svg&#41;]&#40;https://gitlab.com/PWorm/dga/-/commits/main&#41;)

[//]: # (<div id="top">top</div>)

[//]: # (<div id="bottom">bottom</div>)

# <img style="vertical-align:middle" src="./Logo/DGApy_Logo.png" alt="drawing" width="64"/>  <font size="4"> DGApy </font>

# Table of content

- [Description](#description)
- [Installation](#installation)
- [Usage](#usage)
- [Testing](#testing)
- [Documentation](#documentation)
- [About](#about)

## Description

DGApy is a python package that implements tools for the Matsubara Green's function formalism of correlated electrons on a
lattice. Based on the implemented frameworks, the dynamical vertex approximation (DGA) for the Hubbard model, a Feynman
diagrammatic
extension of dynamical mean field theory (DMFT), can be calculated.

DGApy supports:

- All primitive lattices
- General tight-binding models
- DGA calculations for the Hubbard model
- Solving the linearized Eliashberg equation to obtain superconducting eigenvalues
- Calculation of the optical conductivity, including ladder-like vertex corrections
- Analytic continuation of Matsubara Green's functions and physical susceptibilities to the real axis

A detailed description of the underlying theory and applications to nickelate and cuprate superconductors can be found in my
[PhD thesis](https://repositum.tuwien.at/handle/20.500.12708/176739).

Relevant and related literature:

- [Original derivation of DGA](https://journals.aps.org/prb/abstract/10.1103/PhysRevB.75.045118)
- [Asymptotic corrections for improved frequency convergence](https://iopscience.iop.org/article/10.1088/2515-7639/ac7e6d)
- [Maximum entropy analytic continuation](https://www.sciencedirect.com/science/article/pii/S0010465522002387)
- [DMFT impurity solver](https://www.sciencedirect.com/science/article/abs/pii/S0010465518303217?via%3Dihub)

In case you use this code, please cite it. Please also consider citing my thesis and the relevant papers. A bibtex file (dga_bib.
md) containing all the references is included in the root directory for your convenience.

## Publications using DGApy

DGApy has already been successfully used in several scientific publications:

- S. Di Cataldo, **P. Worm** <em> et al.</em>; arXiv preprint
    - [Unconventional superconductivity without doping: infinite-layer nickelates under
      pressure](https://arxiv.org/abs/2311.06195)
- **P. Worm** <em> et al.</em>; arXiv preprint
    - [Spin fluctuations sufficient to mediate superconductivity in nickelates](https://arxiv.org/abs/2312.08260)

## Installation

Before installation fetch the repository via

```
git clone git@github.com:PaulWorm/DGApy.git
```

We recommend to use [anaconda](https://www.anaconda.com/) for managing your python environments. To create a new conda
environment use

```
conda create --name dga_py python=3.9
```

Activate the environment:

```
conda activate dga_py 
```

Before installation of the code install mpi4py using the conda environment:

```
conda install -c conda-forge mpi4py mpich
```

which provides the MPICH MPI implementation and the python package mpi4py. Then go into the dga folder and install the code:

```
cd ./dga
. install.sh
```

This provides the python package dga and several command line interfaces. A detailed description of them
is provided below and in the tutorial "04RunningTheCode.md".

## Usage

### Python package

To use the dga python package, import it via

```
import dga.<submodule name>
```

The package is split into several modules. Here we list the most common ones:

- matsubara_frequencies (mf): handle Matsubara frequencies and frequency transformations
- brillouin_zone (bz): handle the Brillouin zone, mapping into the irreducible BZ and mapping to k-paths
- wannier: handle the tight-binding Hamiltonian and fourier transformation from real to reciprocal space
- two_point (twop): classes for the one-particle Green's function and self-energy
- local_four_point (lfp): handle local (impurity) four-point functions
- four_point (fp): handle non-local (ladder) four-point functions
- analytic_continuation (ac): perform the numeric analytic continuation
    - based on the [ana_cont](https://github.com/josefkaufmann/ana_cont) package
- eliashberg_equation (eq): power iteration eigenvalue solver for the linearized Eliashberg equation
- optics: calculate the optical conductivity

It is recommended to complete the tutorial, contained in the "tutorial" folder, to get a first impression on how the modules
can be used.

### Command line interfaces

With this python package also a command line interface (cli) is provided. Contrary to the different modules, which are
intended to be used as a toolbox, the cli implements the dynamical vertex approximation for the Hubbard model.

### dga_dc

Create the default config file for dga_main in the current folder.

### dga_main

To run a dga calculation perform the following steps:

- Prepare a config file
- Prepare the DMFT input files
- Run the dga_main cli

For the DMFT input file structure currently two input formats are supported.

#### type: "w2dyn"

Either the output of the [w2dynamics](https://github.com/w2dynamics/w2dynamics) code.

- '1p-data.hdf5': converged dmft solution
- 'g4iw_sym.hdf5': symmetrized output (cli: sym1b) of the measurement of the two-particle Green's function for the same anderson
  impurity model as obtained from the DMFT cycle; it is advised to use the same chemical potential (mu) as in the '1p-data.
  hdf5' file and not perform a new mu
  search.

#### type: "default"

If you are not using [w2dynamics](https://github.com/w2dynamics/w2dynamics) and you do not want to implement a parser to your
impurity solver a generic input format is also supported, which uses a single numpy file:

- fname_1p: 'dmft_input.npy': numpy dictionary with the following entries:
    - 'giw': one-particle Green's function
    - 'siw': self-energy
    - 'n': occupation
    - 'mu_dmft': chemical potential
    - 'beta': inverse temperature
    - 'u': on-site Hubbard interaction
    - 'g4iw_dens': density-channel (upup + updown) two-particle Green's function; (w,v,vp) layout
    - 'g4iw_magn': magnetic-channel (upup - updown) two-particle Green's function; (w,v,vp) layout

### dga_test

Run the test suite in the terminal. This will run the unit tests and linting.

## Testing:

#### Unit testing

To run the unit tests, run

```
dga_test 
```

This will run unit tests and linting which are also included in the gitlab CI.

#### End-to-end testing

Several tests use datasets generated with [w2dynamics](https://github.com/w2dynamics/w2dynamics). They input files are
contained in the default input structure in the "tests" folder.

## Documentation

A [standard documentation](https://dgapy.readthedocs.io/en/latest/) is still under construction. For now the tutorial in the "
tutorial" folder is the best source for
learning how to use the code.

## About

This package has been developed by [Paul Worm](https://www.linkedin.com/in/pworm/). If you have any questions feel free to
contact me via [e-mail](mailto:pworm42@gmail.com).

I would like to thank Simone Di Cataldo and Juraj Krisnik for testing the Code and providing valuable feedback.

[//]: # (#### Acknowledgements)




