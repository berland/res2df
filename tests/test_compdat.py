"""Test module for compdat"""

import datetime
import os
from pathlib import Path

import packaging
import pandas as pd
import pytest

from ecl2df import EclFiles, compdat, csv2ecl, ecl2csv

try:
    import opm  # noqa
except ImportError:
    pytest.skip(
        "OPM is not installed",
        allow_module_level=True,
    )


TESTDIR = Path(__file__).absolute().parent
REEK = str(TESTDIR / "data/reek/eclipse/model/2_R001_REEK-0.DATA")
EIGHTCELLS = str(TESTDIR / "data/eightcells/EIGHTCELLS.DATA")

SCHFILE = str(TESTDIR / "data/reek/eclipse/include/schedule/reek_history.sch")

# Reek cases with multisegment well OP_6 including
# AICD and ICD completion from WellBuilder
SCHFILE_AICD = str(TESTDIR / "data/reek/eclipse/include/schedule/op6_aicd1_gp.sch")
SCHFILE_ICD = str(TESTDIR / "data/reek/eclipse/include/schedule/op6_icd1_gp.sch")
SCHFILE_VALV = str(TESTDIR / "data/reek/eclipse/include/schedule/op6_valve1_gp.sch")


def test_df():
    """Test main dataframe API, only testing that something comes out"""
    eclfiles = EclFiles(EIGHTCELLS)
    compdat_df = compdat.df(eclfiles)
    assert not compdat_df.empty
    assert "ZONE" in compdat_df
    assert "K1" in compdat_df
    assert "WELL" in compdat_df

    # Dump dataframe to Eclipse include file and re-parse:
    inc = compdat.df2ecl(compdat_df)
    df_from_inc = compdat.df(inc)
    pd.testing.assert_frame_equal(
        compdat_df.drop("ZONE", axis="columns"), df_from_inc, check_dtype=False
    )


def test_comp2df():
    """Test that dataframes are produced"""
    eclfiles = EclFiles(EIGHTCELLS)
    compdfs = compdat.deck2dfs(eclfiles.get_ecldeck())

    assert not compdfs["COMPDAT"].empty
    assert not compdfs["WELSEGS"].empty
    assert not compdfs["COMPSEGS"].empty
    assert not compdfs["COMPDAT"].columns.empty


def test_schfile2df():
    """Test that we can process individual files"""
    deck = EclFiles.file2deck(SCHFILE)
    compdfs = compdat.deck2dfs(deck)
    assert not compdfs["COMPDAT"].columns.empty
    assert not compdfs["COMPDAT"].empty


def test_str_compdat():
    """Test compdat parsing directly on strings"""
    schstr = """
COMPDAT
 'OP1' 33 110 31 31 'OPEN' 1* 6467.31299 0.216 506642.25  0 1* 'Y' 7.18 /
-- comments.
/
"""
    deck = EclFiles.str2deck(schstr)
    compdfs = compdat.deck2dfs(deck)
    compdat_df = compdfs["COMPDAT"]
    assert compdat_df.loc[0, "SATN"] == 0
    assert not compdat_df.loc[0, "DFACT"]
    assert compdat_df.loc[0, "DIR"] == "Y"

    schstr = """
COMPDAT
 'FOO' 303 1010 031 39  /
/
"""
    compdat_df = compdat.deck2dfs(EclFiles.str2deck(schstr))["COMPDAT"]
    assert len(compdat_df) == 9
    assert not compdat_df["DFACT"].values[0]
    assert not compdat_df["TRAN"].values[0]
    assert compdat_df["I"].values[0] == 303


def test_str2df():
    """Testing making a dataframe from an explicit string"""
    schstr = """
WELSPECS
 'OP1' 'OPWEST' 41 125 1759.74 'OIL' 0.0 'STD' 'SHUT' 'YES'  0  'SEG' /
/

COMPDAT
 'OP1' 33 110 31 31 'OPEN' 0 6467.31299 0.216 506642.25  0.0 0.0 'Y' 7.18 /
-- comments.
/

WELSEGS
  'OP1' 1689 1923 1.0E-5 'ABS' 'HFA' 'HO' / comment without -- identifier
-- foo bar
   2 2 1 1 1923.9 1689.000 0.1172 0.000015  /
/

COMPSEGS
  'OP1' / -- Yet a comment
  -- comment
  41 125 29  5 2577.0 2616.298 / icd on branch 1 in segment 17
/
-- (WSEGVALS is not processed)
WSEGVALV
  'OP1'   166   1   7.4294683E-06  0 / icd on segment 17, cell 41 125 29
/
"""
    deck = EclFiles.str2deck(schstr)
    compdfs = compdat.deck2dfs(deck)
    compdat_df = compdfs["COMPDAT"]
    welsegs = compdfs["WELSEGS"]
    compsegs = compdfs["COMPSEGS"]
    assert "WELL" in compdat_df
    assert len(compdat_df) == 1
    assert compdat_df["WELL"].unique()[0] == "OP1"

    # Check that we have not used the very long opm.io term here:
    assert "CONNECTION_TRANSMISSIBILITY_FACTOR" not in compdat_df
    assert "TRAN" in compdat_df

    assert "Kh" not in compdat_df  # Mixed-case should not be used.
    assert "KH" in compdat_df

    # Make sure the ' are ignored:
    assert compdat_df["OP/SH"].unique()[0] == "OPEN"

    # Continue to WELSEGS
    assert len(welsegs) == 1  # First record is appended to every row.

    # Since we have 'ABS' in WELSEGS, there should be an extra
    # column called 'SEGMENT_MD'
    assert "SEGMENT_MD" in welsegs
    assert welsegs["SEGMENT_MD"].max() == 1923.9

    # Test COMPSEGS
    assert len(compsegs) == 1
    assert "WELL" in compsegs
    assert compsegs["WELL"].unique()[0] == "OP1"
    assert len(compsegs.dropna(axis=1, how="all").iloc[0]) == 8

    # Check date handling
    assert "DATE" in compdat_df
    assert not all(compdat_df["DATE"].notna())
    compdat_date = compdat.deck2dfs(deck, start_date="2000-01-01")["COMPDAT"]
    assert "DATE" in compdat_date
    assert all(compdat_date["DATE"].notna())
    assert len(compdat_date["DATE"].unique()) == 1
    assert str(compdat_date["DATE"].unique()[0]) == "2000-01-01"


def test_tstep():
    """Test with TSTEP present"""
    schstr = """
DATES
   1 MAY 2001 /
/

COMPDAT
 'OP1' 33 110 31 31 'OPEN'  /
/

TSTEP
  1 /

COMPDAT
 'OP1' 34 111 32 32 'OPEN' /
/

TSTEP
  2 3 /

COMPDAT
  'OP1' 35 111 33 33 'SHUT' /
/
"""
    deck = EclFiles.str2deck(schstr)
    compdf = compdat.deck2dfs(deck)["COMPDAT"]
    dates = [str(x) for x in compdf["DATE"].unique()]
    assert len(dates) == 3
    assert "2001-05-01" in dates
    assert "2001-05-02" in dates
    assert "2001-05-07" in dates

    schstr_nodate = """
COMPDAT
 'OP1' 33 110 31 31 'OPEN'  /
/

TSTEP
  1 /

COMPDAT
 'OP1' 34 111 32 32 'OPEN' /
/
    """
    assert compdat.deck2dfs(EclFiles.str2deck(schstr_nodate)) == {}
    # (critical error logged)


def test_applywelopen_stringdeck():
    schstr = """
DATES
   1 MAY 2001 /
/

COMPDAT
 'OP1' 33 110 31 31 'OPEN'  /
/
WELOPEN
 'OP1' 'SHUT' /
/

TSTEP
  1 /

COMPDAT
 'OP2' 66 110 31 31 'OPEN'  /
/

WELOPEN
 'OP1' 'OPEN' /
/

TSTEP
  2 3 /

WELOPEN
 'OP1' 'POPN' /
 'OP2' 'SHUT' /
/
"""
    df = compdat.deck2dfs(EclFiles.str2deck(schstr))["COMPDAT"]
    assert df.shape[0] == 5
    assert df["OP/SH"].nunique() == 2
    assert df["DATE"].nunique() == 3

    schstr = """
DATES
   1 MAY 2001 /
/

COMPDAT
 'OP1' 33 110 31 31 'OPEN'  /
/
WELOPEN
 'OP2' 'SHUT' /
/"""
    with pytest.raises(ValueError):
        compdat.deck2dfs(EclFiles.str2deck(schstr))["COMPDAT"]


def test_unrollcompdatk1k2():
    """Test unrolling of k1-k2 ranges in COMPDAT"""
    schstr = """
COMPDAT
  -- K1 to K2 is a range of 11 layers, should be automatically
  -- unrolled to 11 rows.
  'OP1' 33 44 10 20  /
/
"""
    df = compdat.deck2dfs(EclFiles.str2deck(schstr))["COMPDAT"]
    assert df["I"].unique() == 33
    assert df["J"].unique() == 44
    assert (df["K1"].values == range(10, 20 + 1)).all()
    assert (df["K2"].values == range(10, 20 + 1)).all()

    # Check that we can read withoug unrolling:
    df_noroll = compdat.deck2dfs(EclFiles.str2deck(schstr), unroll=False)["COMPDAT"]
    assert len(df_noroll) == 1


def test_samecellperf():
    """Test that we allow multiple perforations in the same cell"""
    schstr = """
COMPDAT
  'OP1' 1 1 1 1 /
  'OP2' 1 1 1 1 /
/
"""
    df = compdat.deck2dfs(EclFiles.str2deck(schstr))["COMPDAT"]
    assert len(df) == 2


def test_unrollwelsegs():
    """Test unrolling of welsegs."""
    schstr = """
WELSEGS
  -- seg_start to seg_end (two first items in second record) is a range of
  -- 2 segments, should be automatically unrolled to 2 rows.
  'OP1' 1689 1923 1.0E-5 'ABS' 'HFA' 'HO' / comment without -- identifier
   2 3 1 1 1923.9 1689.000 0.1172 0.000015  /
/
"""
    df = compdat.deck2dfs(EclFiles.str2deck(schstr))["WELSEGS"]
    assert len(df) == 2

    df = compdat.deck2dfs(EclFiles.str2deck(schstr), unroll=False)["WELSEGS"]
    assert len(df) == 1


def test_unrollbogus():
    """Giving in empty dataframe, should not crash."""
    assert compdat.unrolldf(pd.DataFrame).empty

    bogusdf = pd.DataFrame([0, 1, 4], [0, 2, 5])
    unrolled = compdat.unrolldf(pd.DataFrame([0, 1, 4], [0, 2, 5]), "FOO", "bar")
    # (warning should be issued)
    assert (unrolled == bogusdf).all().all()


def test_initmerging():
    """Test that we can ask for INIT vectors to be merged into the data"""
    eclfiles = EclFiles(REEK)
    noinit_df = compdat.df(eclfiles)
    df = compdat.df(eclfiles, initvectors=[])
    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    df = compdat.df(eclfiles, initvectors=["FIPNUM", "EQLNUM", "SATNUM"])
    assert "FIPNUM" in df
    assert "EQLNUM" in df
    assert "SATNUM" in df
    assert len(df) == len(noinit_df)

    df = compdat.df(eclfiles, initvectors="FIPNUM")
    assert "FIPNUM" in df
    assert len(df) == len(noinit_df)

    with pytest.raises(AssertionError):
        compdat.df(eclfiles, initvectors=2)


def test_main_subparsers(tmp_path, mocker):
    """Test command line interface"""
    tmpcsvfile = tmp_path / "compdat.csv"
    mocker.patch(
        "sys.argv", ["ecl2csv", "compdat", "-v", EIGHTCELLS, "-o", str(tmpcsvfile)]
    )
    ecl2csv.main()

    assert Path(tmpcsvfile).is_file()
    disk_df = pd.read_csv(str(tmpcsvfile))
    assert "ZONE" in disk_df
    assert not disk_df.empty

    mocker.patch(
        "sys.argv",
        [
            "ecl2csv",
            "compdat",
            EIGHTCELLS,
            "--initvectors",
            "FIPNUM",
            "-o",
            str(tmpcsvfile),
        ],
    )
    ecl2csv.main()

    assert Path(tmpcsvfile).is_file()
    disk_df = pd.read_csv(str(tmpcsvfile))
    assert "FIPNUM" in disk_df
    assert not disk_df.empty

    mocker.patch(
        "sys.argv",
        [
            "ecl2csv",
            "compdat",
            EIGHTCELLS,
            "--initvectors",
            "FIPNUM",
            "EQLNUM",
            "-o",
            str(tmpcsvfile),
        ],
    )
    ecl2csv.main()

    assert Path(tmpcsvfile).is_file()
    disk_df = pd.read_csv(str(tmpcsvfile))
    assert "FIPNUM" in disk_df
    assert "EQLNUM" in disk_df
    assert not disk_df.empty


def test_csv2ecl_eightcells(tmp_path, mocker):
    """Test include file construction from CSV data"""
    os.chdir(tmp_path)
    eightcells_compdat = compdat.df(EclFiles(EIGHTCELLS))
    eightcells_compdat.to_csv("compdat.csv", index=False)

    mocker.patch(
        "sys.argv",
        ["csv2ecl", "compdat", "--verbose", "compdat.csv", "--output", "compdat.inc"],
    )
    csv2ecl.main()
    compdatinc = Path("compdat.inc").read_text()
    assert "'OP1' 1 1 1 1 'OPEN'" in " ".join(compdatinc.split())


def test_csv2ecl_reek(tmp_path, mocker):
    """Test include file construction from CSV data"""
    os.chdir(tmp_path)
    reek_compdat = compdat.df(EclFiles(REEK))
    reek_compdat.to_csv("compdat.csv", index=False)

    mocker.patch(
        "sys.argv",
        ["csv2ecl", "compdat", "--verbose", "compdat.csv", "--output", "compdat.inc"],
    )
    csv2ecl.main()
    compdatinc = Path("compdat.inc").read_text()
    # Reparse it into a dataframe using opm.common
    df_from_inc = compdat.df(compdatinc)
    pd.testing.assert_frame_equal(
        reek_compdat.drop("ZONE", axis="columns"), df_from_inc
    )


def test_defaulted_compdat_i_j(tmp_path):
    """I and J can be defaulted (that is 1* or 0) in COMPDAT records, then
    that information should be fetched from the most recent WELSPECS keyword
    """

    welspecs_str = """
WELSPECS
  OP1 OPWEST 20 30 1000 /
/
"""
    compdat_str_def_i = """
COMPDAT
  'OP1' 1* 0 10 11  /
/
"""
    compdat_str_def_j = """
COMPDAT
  'OP1' 20 1* 10 11  /
/
"""
    compdat_str_nodefaults = """
COMPDAT
  'OP1' 55 66 80 80  /
/
"""

    with pytest.raises(ValueError, match="WELSPECS must be provided when I"):
        compdat.deck2dfs(EclFiles.str2deck(compdat_str_def_i))["COMPDAT"]

    # I value of 0 also means defaulted:
    with pytest.raises(ValueError, match="WELSPECS must be provided when I"):
        compdat.deck2dfs(EclFiles.str2deck(compdat_str_def_i.replace("1*", "0")))[
            "COMPDAT"
        ]

    with pytest.raises(ValueError, match="WELSPECS must be provided when J"):
        compdat.deck2dfs(EclFiles.str2deck(compdat_str_def_j))["COMPDAT"]

    # J value of 0 also means defaulted:
    with pytest.raises(ValueError, match="WELSPECS must be provided when J"):
        compdat.deck2dfs(EclFiles.str2deck(compdat_str_def_j.replace("1*", "0")))[
            "COMPDAT"
        ]

    with pytest.raises(ValueError, match="WELSPECS must be provided"):
        # Wrong order:
        compdat.deck2dfs(EclFiles.str2deck(compdat_str_def_i + welspecs_str))["COMPDAT"]

    # Simplest example:
    compdat_df = compdat.deck2dfs(EclFiles.str2deck(welspecs_str + compdat_str_def_i))[
        "COMPDAT"
    ]
    assert compdat_df["I"].unique() == [20]
    assert compdat_df["J"].unique() == [30]

    # Two wells:
    compdat_df = compdat.deck2dfs(
        EclFiles.str2deck(
            welspecs_str.replace("OP1", "OP2").replace("30", "99")
            + welspecs_str
            + compdat_str_def_i
        )
    )["COMPDAT"]

    # Partial defaulting
    compdat_df = compdat.deck2dfs(
        EclFiles.str2deck(welspecs_str + compdat_str_def_i + compdat_str_nodefaults)
    )["COMPDAT"]

    assert set(compdat_df["I"].unique()) == {20, 55}
    assert set(compdat_df["J"].unique()) == {30, 66}

    compdat_df = compdat.deck2dfs(
        EclFiles.str2deck(
            welspecs_str.replace("OP1", "OP2").replace("30", "99")
            + welspecs_str
            + compdat_str_def_i
            + compdat_str_def_i.replace("OP1", "OP2")
        )
    )["COMPDAT"]

    assert compdat_df[compdat_df["WELL"] == "OP1"]["I"].unique() == [20]
    assert compdat_df[compdat_df["WELL"] == "OP2"]["I"].unique() == [20]
    assert compdat_df[compdat_df["WELL"] == "OP1"]["J"].unique() == [30]
    assert compdat_df[compdat_df["WELL"] == "OP2"]["J"].unique() == [99]

    # Same well redrilled to new location
    compdat_df = compdat.deck2dfs(
        EclFiles.str2deck(
            "DATES\n  1 JAN 2030 /\n/\n"
            + welspecs_str
            + compdat_str_def_i
            + "DATES\n  1 JAN 2040 /\n/\n"
            + welspecs_str.replace("30", "33")
            + compdat_str_def_i
        )
    )["COMPDAT"]
    assert compdat_df[compdat_df["DATE"].astype(str) == "2030-01-01"]["J"].unique() == [
        30
    ]
    assert compdat_df[compdat_df["DATE"].astype(str) == "2040-01-01"]["J"].unique() == [
        33
    ]


# Multisegement well testing
def test_msw_schfile2df():
    """Test that we can process individual files with AICD and ICD MSW"""
    deck = EclFiles.file2deck(SCHFILE_AICD)
    compdfs = compdat.deck2dfs(deck)
    assert not compdfs["WSEGAICD"].empty
    assert not compdfs["WSEGAICD"].columns.empty

    deck = EclFiles.file2deck(SCHFILE_ICD)
    compdfs = compdat.deck2dfs(deck)
    assert not compdfs["WSEGSICD"].empty
    assert not compdfs["WSEGSICD"].columns.empty

    deck = EclFiles.file2deck(SCHFILE_VALV)
    compdfs = compdat.deck2dfs(deck)
    assert not compdfs["WSEGVALV"].empty
    assert not compdfs["WSEGVALV"].columns.empty


def test_msw_str2df():
    """Testing making a dataframe from an explicit string including MSW"""
    schstr = """
WELSPECS
   'OP_6' 'DUMMY' 28 37 1575.82 OIL 0.0 'STD' 'SHUT' 'YES' 0 'SEG' /
/

COMPDAT
    'OP_6' 28 37 1 1 OPEN 0 1.2719 0.311 114.887 0.0 0.0 'X' 19.65 /
/

WELSEGS
-- WELL   SEGMENTTVD  SEGMENTMD WBVOLUME INFOTYPE PDROPCOMP MPMODEL
   'OP_6'        0.0        0.0   1.0E-5    'ABS'     'HF-'    'HO' /
--  SEG  SEG2  BRANCH  OUT MD       TVD       DIAM ROUGHNESS
     2    2    1        1  2371.596 1577.726  0.15 0.00065    /
/

COMPSEGS
   'OP_6' /
--  I   J   K   BRANCH STARTMD  ENDMD    DIR DEF  SEG
    28  37   1   2     2366.541 2376.651  1*  3*  31   /
/

WSEGAICD
-- WELL SEG SEG2   ALPHA    SF  RHO VIS EMU DEF    X    Y
-- FLAG   A   B   C    D    E    F
   OP_6  31   31 1.7e-05 -1.18 1000 1.0 0.5  4* 3.05 0.67
   OPEN 1.0 1.0 1.0 2.43 1.18 10.0  /
/

WSEGSICD
-- WELL   SEG  SEG2 ALPHA  SF             RHO     VIS  WCT
    OP_6  31   31   0.0001  -1.186915444  1000.0  1.0  0.5  /
/

WSEGVALV
-- WELL   SEG             CV      AC   L
    OP_6  31       0.0084252 0.00075  1*  /
/
"""
    deck = EclFiles.str2deck(schstr)
    compdfs = compdat.deck2dfs(deck)
    wsegaicd = compdfs["WSEGAICD"]
    wsegsicd = compdfs["WSEGSICD"]
    wsegvalv = compdfs["WSEGVALV"]

    # Test WSEGAICD
    assert len(wsegaicd) == 1
    assert "WELL" in wsegaicd
    assert wsegaicd["WELL"].unique()[0] == "OP_6"
    assert len(wsegaicd.dropna(axis=1, how="all").iloc[0]) == 20

    # Test WSEGSICD
    assert len(wsegsicd) == 1
    assert "WELL" in wsegsicd
    assert wsegsicd["WELL"].unique()[0] == "OP_6"
    assert len(wsegsicd.dropna(axis=1, how="all").iloc[0]) == 12

    # Test WSEGVALV
    assert len(wsegvalv) == 1
    assert "WELL" in wsegvalv
    assert wsegvalv["WELL"].unique()[0] == "OP_6"
    assert len(wsegvalv.dropna(axis=1, how="all").iloc[0]) == 5


def test_wsegaicd():
    """Test the WSEGAICD parser for column names and default values"""
    schstr = """WSEGAICD
    OP_6  31   31 1.7e-05 -1.18 1000 1.0 0.5  4* 3.05 0.67
   OPEN 1.0 1.0 1.0 2.43 1.18 10.0  /
/
    """
    deck = EclFiles.str2deck(schstr)
    wsegaicd = compdat.deck2dfs(deck)["WSEGAICD"]
    pd.testing.assert_frame_equal(
        wsegaicd,
        pd.DataFrame(
            data=[
                {
                    "WELL": "OP_6",
                    "SEGMENT1": 31,
                    "SEGMENT2": 31,
                    "STRENGTH": 1.7e-05,
                    "LENGTH": -1.18,
                    "DENSITY_CALI": 1000.0,
                    "VISCOSITY_CALI": 1.0,
                    "CRITICAL_VALUE": 0.5,
                    "WIDTH_TRANS": 0.05,
                    "MAX_VISC_RATIO": 5,
                    "METHOD_SCALING_FACTOR": -1,
                    "MAX_ABS_RATE": None,
                    "FLOW_RATE_EXPONENT": 3.05,
                    "VISC_EXPONENT": 0.67,
                    "STATUS": "OPEN",
                    "OIL_FLOW_FRACTION": 1.0,
                    "WATER_FLOW_FRACTION": 1.0,
                    "GAS_FLOW_FRACTION": 1.0,
                    "OIL_VISC_FRACTION": 2.43,
                    "WATER_VISC_FRACTION": 1.18,
                    "GAS_VISC_FRACTION": 10.0,
                    "DATE": None,
                }
            ]
        ),
    )


def test_wsegsicd():
    """Test the WSEGSICD parser for column names and default values

    Proves bug 232 is fixed.
    """
    schstr = """WSEGSICD
        'WELL_A'              31    31    0.00178 0.57975861     1*   1*        0.7
        1*         1*     1         1*
                         OPEN /
            /
    """
    deck = EclFiles.str2deck(schstr)
    wsegsicd = compdat.deck2dfs(deck)["WSEGSICD"]
    pd.testing.assert_frame_equal(
        wsegsicd,
        pd.DataFrame(
            data=[
                {
                    "WELL": "WELL_A",
                    "SEGMENT1": 31,
                    "SEGMENT2": 31,
                    "STRENGTH": 0.00178,
                    "LENGTH": 0.57975861,
                    "DENSITY_CALI": 1000.25,
                    "VISCOSITY_CALI": 1.45,
                    "CRITICAL_VALUE": 0.7,
                    "WIDTH_TRANS": 0.05,
                    "MAX_VISC_RATIO": 5,
                    "METHOD_SCALING_FACTOR": 1,
                    "MAX_ABS_RATE": None,
                    "STATUS": "OPEN",
                    "DATE": None,
                }
            ]
        ),
    )


def test_wsegvalv():
    """Test the WSEGVALV parser for column names and default values"""
    schstr = """
    WSEGVALV
    -- WELL    SEG         CV      AC  Lex     Dp    ROUGH      Ap  STATUS     A_MAX
    WELL_A   31  0.0084252 0.00075  0.5  0.216   0.0005  0.0366    SHUT    0.0008 /
    /
    """
    deck = EclFiles.str2deck(schstr)
    wsegvalv = compdat.deck2dfs(deck)["WSEGVALV"]
    pd.testing.assert_frame_equal(
        wsegvalv,
        pd.DataFrame(
            data=[
                {
                    "WELL": "WELL_A",
                    "SEGMENT_NUMBER": 31,
                    "CV": 0.0084252,
                    "AREA": 0.00075,
                    "EXTRA_LENGTH": 0.5,
                    "PIPE_D": 0.216,
                    "ROUGHNESS": 0.0005,
                    "PIPE_A": 0.0366,
                    "STATUS": "SHUT",
                    "MAX_A": 0.0008,
                    "DATE": None,
                }
            ]
        ),
    )


def test_wsegvalv_max_blank():
    """Test the WSEGVALV parser for column names and blank values. NB: Blank
    values are taken from other keywords in Eclipse except STATUS, which is OPEN
    by default. Combination of keywords is not tested here."""
    schstr = """
    WSEGVALV
    -- WELL    SEG         CV      AC
    WELL_A   31  0.0084252 0.00075  /
    /
    """
    deck = EclFiles.str2deck(schstr)
    wsegvalv = compdat.deck2dfs(deck)["WSEGVALV"]
    pd.testing.assert_frame_equal(
        wsegvalv,
        pd.DataFrame(
            data=[
                {
                    "WELL": "WELL_A",
                    "SEGMENT_NUMBER": 31,
                    "CV": 0.0084252,
                    "AREA": 0.00075,
                    "EXTRA_LENGTH": None,
                    "PIPE_D": None,
                    "ROUGHNESS": None,
                    "PIPE_A": None,
                    "STATUS": "OPEN",
                    "MAX_A": None,
                    "DATE": None,
                }
            ]
        ),
    )


def test_wsegvalv_max_default():
    """Test the WSEGVALV parser for column names and default values. NB: Default
    values are taken from other keywords in Eclipse except STATUS, which is OPEN
    by default. Combination of keywords is not tested here."""
    schstr = """
    WSEGVALV
    -- WELL    SEG         CV      AC
    WELL_A   31  0.0084252 0.00075  6* /
    /
    """
    deck = EclFiles.str2deck(schstr)
    wsegvalv = compdat.deck2dfs(deck)["WSEGVALV"]
    pd.testing.assert_frame_equal(
        wsegvalv,
        pd.DataFrame(
            data=[
                {
                    "WELL": "WELL_A",
                    "SEGMENT_NUMBER": 31,
                    "CV": 0.0084252,
                    "AREA": 0.00075,
                    "EXTRA_LENGTH": None,
                    "PIPE_D": None,
                    "ROUGHNESS": None,
                    "PIPE_A": None,
                    "STATUS": "OPEN",
                    "MAX_A": None,
                    "DATE": None,
                }
            ]
        ),
    )


@pytest.mark.parametrize(
    "dframe, expected",
    [
        pytest.param(
            pd.DataFrame(
                [
                    # This also tests that dataframe column
                    # order is arbitrary
                    {"WELL": "OP1", "J": "200", "I": 10},
                    {"WELL": "OP2", "I": 1000, "J": 1},
                ]
            ),
            """COMPDAT
  'OP1'   10 200 /
  'OP2' 1000   1 /
/""",
            id="column_alignment",
        ),
        pytest.param(
            pd.DataFrame([{"WELL": "OP1", "DATE": datetime.date(2001, 1, 1)}]),
            "DATES\n  1 'JAN' 2001 /\n/\n\nCOMPDAT\n  'OP1' /\n/",
            id="with-date",
        ),
        pytest.param(
            pd.DataFrame(
                [{"WELL": "OP1", "DATE": datetime.datetime(2001, 1, 1, 3, 3, 3)}]
            ),
            "DATES\n  1 'JAN' 2001 03:03:03 /\n/\n\nCOMPDAT\n  'OP1' /\n/",
            id="with-datetime",
        ),
        pytest.param(
            pd.DataFrame([{"WELL": "OP1", "DATE": "2000-01-01"}]),
            "DATES\n  1 'JAN' 2000 /\n/\n\nCOMPDAT\n  'OP1' /\n/",
            id="with-isodatestring",
        ),
        pytest.param(
            pd.DataFrame(
                [
                    {"WELL": "OP1", "DATE": "2000-01-01"},
                    {"WELL": "OP2", "DATE": "3000-01-01"},
                ]
            ),
            """DATES
  1 'JAN' 2000 /
/

COMPDAT
  'OP1' /
/

DATES
  1 'JAN' 3000 /
/

COMPDAT
  'OP2' /
/""",
            id="multiple-dates",
        ),
    ],
)
def test_df2ecl_compdat(dframe, expected):
    """Test construction of compdat keyword data from dataframes"""
    result = compdat.df2ecl_compdat(dframe)
    commentsstripped = "\n".join(
        [line for line in result.splitlines() if not line.startswith("--")]
    )
    # Pandas 1.1.5 gives a different amount of whitespace than what
    # these tests are written for. If so, be more slack about whitespace.
    if packaging.version.parse(pd.__version__) < packaging.version.parse("1.2.0"):
        commentsstripped = " ".join(commentsstripped.split())
        assert commentsstripped == " ".join(expected.split())
    else:
        # Relax about leading and trailing whitespace
        assert commentsstripped.strip() == expected.strip()
