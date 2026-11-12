import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from specx.rules import MISSING, cas_checksum_ok, flash_point_c, ph, un_number  # noqa: E402


def doc(sec9: str = "", sec14: str = "") -> str:
    return f"9. Physical and chemical properties\n{sec9}\n10. Stability and reactivity\n\n14. Transport information\n{sec14}\n15. Regulatory information\n"


def test_cas_checksum():
    assert cas_checksum_ok("67-64-1")      # acetone
    assert cas_checksum_ok("7732-18-5")    # water
    assert not cas_checksum_ok("67-64-2")


def test_flash_point_units_and_bounds():
    assert flash_point_c(doc("Flash Point: 122F (49°C) Tag Open")) == 49.0
    assert flash_point_c(doc("Flash Point: <-29.2°F Tag Closed")) == -34.0
    assert flash_point_c(doc("Flash point : > 93.3 °C")) == 93.3
    assert flash_point_c(doc("Flash Point, °C -96")) == -96.0


def test_flash_point_declines_when_unsure():
    assert flash_point_c(doc("Flash Point: 15-19°F (-9 - -7°C)")) is MISSING     # range
    assert flash_point_c(doc("Flash point < 0 °F (< -1B.8 °C)")) is MISSING      # corrupted digits
    assert flash_point_c(doc("Flash point : None")) is None


def test_ph_ignores_neighbouring_values():
    assert ph(doc("pH: Not Applicable Relative Density: 0.72")) is None
    assert ph(doc("pH : 13.5")) == 13.5
    assert ph(doc("pH\n(; Conc.: 100 % product)")) is MISSING


def test_un_number_from_table_layout():
    assert un_number(doc(sec14="UN Number: N.A. 1263 1263 N.A.\nProper Shipping Name: Not Regulated Paint")) == "UN1263"
    assert un_number(doc(sec14="U.S. (DOT) / Canadian TDG: Not Regulated for shipping.")) is None
