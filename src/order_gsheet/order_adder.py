"""
Add orders to the "Order Management" tab of the Order Fulfilment Tracking sheet
without touching its look.

Setup (one time):
  pip install gspread
  1. Google Cloud console -> create a project -> enable the Google Sheets API
  2. Create a service account -> download its JSON key as service_account.json
  3. Share the sheet with the service account's email (Editor)

How it keeps the style:
  - The sheet has newest orders at the TOP, so each order is inserted at row 2.
  - Only columns A:M are shifted down, so the leaderboard in O:P stays put.
  - Formatting and dropdowns are copied from an existing row (TEMPLATE_ROW),
    so new rows look exactly like the rest.
"""

import logging 

from order_gsheet import (
    GSheetEntry,
    GSheetColumn,
    TEMPLATE_ROW,
    gs_load,
    WORKSHEET,
)

from gspread.utils import ValueInputOption  # or: from gspread.enums import ValueInputOption

logger = logging.getLogger(__name__)


def add_order(
    **kwargs,
) -> bool:

    try:
        entry = GSheetEntry(**kwargs)
    except TypeError as e:
        raise TypeError("Could not create entry") from e

    tx_id = _to_id(entry.transaction_id)

    if tx_id is None:
        raise TypeError(f"Could not validate transaction id {tx_id}")

    entry_values = entry.to_values()

    tx_ids = {_to_id(id) for id in gs_load(GSheetColumn.TRANSACTION_ID)}
    tx_ids.discard(None)

    # col_num_transaction_id is always last column 
    if tx_id in tx_ids:
        logger.info(
            "Skipping duplicate transaction %s (receipt %s)",
            tx_id, entry.receipt_id,
        )
        return False

    def rng(row_start, row_end):  # 0-indexed, end-exclusive
        return {
            "sheetId": WORKSHEET.id,
            "startRowIndex": row_start,
            "endRowIndex": row_end,
            "startColumnIndex": 0,
            "endColumnIndex": len(entry_values),
        }

    # After inserting one row at index 1, the template row moves down by one,
    # so its 0-indexed position equals its old 1-indexed row number.
    template = rng(TEMPLATE_ROW, TEMPLATE_ROW + 1)
    new_row = rng(1, 2)

    WORKSHEET.spreadsheet.batch_update({"requests": [
        {"insertRange": {"range": new_row, "shiftDimension": "ROWS"}},
        {"copyPaste": {"source": template, "destination": new_row,
                       "pasteType": "PASTE_FORMAT"}},
        {"copyPaste": {"source": template, "destination": new_row,
                       "pasteType": "PASTE_DATA_VALIDATION"}},
    ]})

    range_end = chr((len(entry_values) - 1) % 26 + 65)

    WORKSHEET.update(
        range_name=f"A2:{range_end}2",
        values=[entry.to_values()],
        value_input_option=ValueInputOption.user_entered  # so dates parse as real dates
    )

    return True


def _to_id(value) -> int | None:
    """Normalise a cell value ('123', 123, 123.0) to an int ID.
 
    Returns None for blanks, headers, and anything else that isn't numeric.
    """
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None

if __name__ == "__main__":
    add_order(tray_color="Purple", scoop_color="Marble", name="Jane Doe")