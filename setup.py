# -*- coding: utf-8 -*-
from setuptools import setup



setup(
    name="ecl2df",
    version="0.0.1",
    description="Convert Eclipse 100 input and output to DataFrames",
    url="http://github.com/equinor/ecl2df",
    author="Håvard Berland",
    author_email="havb@equinor.com",
    license="GPLv3",
    packages=["ecl2df"],
    setup_requires=["pytest-runner"],
    test_requirements=["pytest"],
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "nnc2csv=ecl2df.nnc2df:main",
            "eclgrid2csv=ecl2df.grid2df:main",
            "grid2csv=ecl2df.grid2df:main",
            "summary2csv=ecl2df.summary2df:main",
            "rft2csv=ecl2df.rft2df:main",
            "compdat2csv=ecl2df.compdat2df:main",
            "equil2csv=ecl2df.equil2df:main",
            "gruptree2csv=ecl2df.gruptree2df:main",
            "satfunc2csv=ecl2df.satfunc2df:main",
            "faults2csv=ecl2df.faults2df:main",
        ]
    },
)
