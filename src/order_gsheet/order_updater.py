from datetime import date, timedelta
import logging 
from gspread.utils import rowcol_to_a1, ValueInputOption

logger = logging.getLogger(__name__)

from order_gsheet import (
    GSheetColumn,
    Priority,
    HEADER_ROW,
    SHEETS_EPOCH,
    WORKSHEET,
    gs_load
)

def update_priorities() -> None:
    # 1. Fetch current priorities and ship-by values
    raw_priorities = gs_load(GSheetColumn.PRIORITY)
    raw_ship_bys = gs_load(GSheetColumn.SHIP_BY_DATE)

    # 2. Pad lists to equal length so zip aligns properly
    n = max(len(raw_priorities), len(raw_ship_bys))
    raw_priorities += [""] * (n - len(raw_priorities))
    raw_ship_bys += [""] * (n - len(raw_ship_bys))

    # 3. Recalculate priorities while preserving "Done"
    new_priorities = []
    for current_p, raw_ship in zip(raw_priorities, raw_ship_bys):
        if current_p == Priority.DONE:
            new_priorities.append(Priority.DONE)
        else:
            ship_date = _parse_date(raw_ship)
            new_priorities.append(Priority.get_priority(ship_date))

    # 4. Write recalculated priorities back to Google Sheets
    headers = WORKSHEET.row_values(HEADER_ROW)
    if new_priorities:
        priority_col_num = headers.index(GSheetColumn.PRIORITY) + 1
        col_letter = rowcol_to_a1(1, priority_col_num).rstrip("0123456789")

        WORKSHEET.update(
            range_name=f"{col_letter}2:{col_letter}{len(new_priorities) + 1}",
            values=[[p] for p in new_priorities],
            value_input_option=ValueInputOption.user_entered
        )

def _parse_date(val: str | int | float | date | None) -> date | None:
    """Normalize input (date, Sheets serial number, or ISO string) to a date object."""
    if val is None or val == "":
        return None

    if isinstance(val, date):
        return val

    # Handle Google Sheets serial numbers (e.g. 45200 or float string)
    try:
        serial = float(val)
        return SHEETS_EPOCH + timedelta(days=serial)
    except (TypeError, ValueError):
        pass

    # Handle standard ISO date strings (e.g. "YYYY-MM-DD")
    if isinstance(val, str):
        try:
            return date.fromisoformat(val)
        except ValueError:
            return None

    return None