# MTLsim

![PyPI Downloads](https://img.shields.io/pypi/dm/mtlsim)
![PyPI Version](https://img.shields.io/pypi/v/mtlsim)
![GitHub License](https://img.shields.io/github/license/malmeloo/mtlsim)


mtlsim is a simulator for Merkle Tree Ladder (MTL) mode in DNSSEC. Its main purpose is to evaluate the performance of MTL mode in various scenarios. mtlsim can ingest real zone and resolver data, simulate the behavior of MTL mode, and analyze the results.

Several ladder management strategies are included out of the box. However, mtlsim is designed to be extensible, allowing users to implement their own strategies relatively easily.

## Paper

mtlsim was written as part of Mike Almeloo's Master's thesis at the University of Twente. The associated paper, "Evaluating MTL Mode Parameters in Real-world Scenarios", can be found [here](https://purl.utwente.nl/essays/111423).

## Documentation

Usage and developer documentation can be found in the [docs](docs/) folder.

## License

Unless specified otherwise, mtlsim is published under the AGPL-3.0 license. See [LICENSE](LICENSE) for details.
