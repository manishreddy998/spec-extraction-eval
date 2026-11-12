"""The attributes we extract from every safety data sheet (SDS).

SDS documents follow the GHS 16-section layout, which makes them a good test bed:
the structure is predictable, but every manufacturer formats it differently.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SignalWord = Literal["Danger", "Warning", "None"]
PhysicalState = Literal["solid", "liquid", "gas"]


class SDSRecord(BaseModel):
    product_name: Optional[str] = Field(None, description="Trade or product name from Section 1.")
    manufacturer: Optional[str] = Field(None, description="Company that issued the SDS (Section 1).")
    cas_numbers: list[str] = Field(default_factory=list, description="CAS registry numbers of listed ingredients (Section 3).")
    signal_word: Optional[SignalWord] = Field(None, description="GHS signal word (Section 2). 'None' if not classified.")
    hazard_statements: list[str] = Field(default_factory=list, description="GHS H-codes, e.g. H225, H319 (Section 2).")
    un_number: Optional[str] = Field(None, description="UN number from Section 14, e.g. UN1993, or None if not regulated.")
    flash_point_c: Optional[float] = Field(None, description="Flash point in degrees Celsius (Section 9).")
    physical_state: Optional[PhysicalState] = Field(None, description="Physical state at room temperature (Section 9).")
    ph: Optional[float] = Field(None, description="pH value if stated (Section 9).")
    revision_date: Optional[str] = Field(None, description="Revision or issue date as YYYY-MM-DD.")


FIELDS: list[str] = list(SDSRecord.model_fields)
