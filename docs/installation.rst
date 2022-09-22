Installation
============

Internally in Equinor, ecl2df is distributed through Komodo and
nothing is needed besides activating Komodo.

See https://fmu-docs.equinor.com/docs/komodo/equinor_komodo_usage.html
for Komodo instructions.

On Linux computers outside Equinor, ecl2df with OPM installed alongside,
should be installed from https://pypi.org:

.. code-block:: console

  pip install ecl2df[opm]

On MacOS, OPM package is not available on pypi, and you will only
have parts of ecl2df working, or you can compile it yourself.

