import os 

import json
import base64
from datetime import date, timedelta
from dataclasses import dataclass

import gspread
from gspread.utils import ValueRenderOption, rowcol_to_a1


TAB = "Order Management"
HEADER_ROW = 1
TEMPLATE_ROW = 3   # a normal-looking row (1-indexed, as the sheet looks today)
SHEETS_EPOCH = date(1899, 12, 30)  # Google Sheets' day-zero

_creds_json = base64.b64decode(os.environ["GOOGLE_APPLICATION_CREDENTIALS_B64"]).decode("utf-8")
_creds_dict = json.loads(_creds_json)
_gc = gspread.service_account_from_dict(_creds_dict)

WORKSHEET = _gc.open_by_key(os.environ["ORDER_FUFILLMENT_TRACKING_GSHEET_ID"]).worksheet(TAB)

class GSheetColumn:
    PRIORITY: str = 'Priority'
    TWO_TONE_TOP: str = '2 Tone Top'
    TRAY_COLOR_BOTT: str = 'Tray Color/Bott'
    SCOOP_LOGO_COLOR: str = 'Scoop/Logo Color'
    TYPE: str = 'Type'
    CLAIMED_BY: str = 'Claimed By:'
    ORDER_DATE: str = 'Order date'
    SHIP_BY_DATE: str = 'Ship by date'
    STATUS: str = 'Status'
    LABEL_CREATED: str = 'Label Created'
    LABEL_PRINTED: str = 'Label Printed'
    CUSTOMER: str = 'Customer'
    SALES_PLATFORM: str = 'Sales platofrm'
    QTY: str = 'Qty'
    RECEIPT_ID: str = 'Receipt ID'
    TRANSACTION_ID: str = 'Transaction ID'

class Priority:
    TODAY: str = "SHIP TODAY!"
    TOMORROW: str = "Send Tmr👀"
    LATE: str = "ZLATE!!!"
    GOT_TIME: str = "Got Time B)"
    DONE: str = "Done"
    UNKNOWN: str = "Unkown"
    @staticmethod
    def get_priority(ship_date: date | None) -> str:
        if ship_date is None: return Priority.UNKNOWN
        
        today = date.today()
        if ship_date == today:
            return Priority.TODAY
        elif ship_date == today + timedelta(days=1):
            return Priority.TOMORROW
        elif ship_date < today:
            return Priority.LATE
        else:
            return Priority.GOT_TIME


@dataclass(frozen=True)
class GSheetEntry:
    receipt_id: int 
    transaction_id: int 
    tray_color: str 
    scoop_color: str 
    name: str 
    lighter_type: str 
    order_date: date
    ship_by: date 
    quantity: int
    label_printed: str = "No"
    label_created: str = "No"
    status: str = "Received"
    claimed_by: str = "Unassigned"
    priority: str = "Got Time B)"
    platform: str = "Etsy"
    top: str = "NA"

    def to_values(self):
        return [
            # Priority     2 Tone Top Tray Color/Bott  Scoop/Logo Color
            self.priority, self.top,  self.tray_color, self.scoop_color,

            # Type             Claimed By:      Order date            Ship by date
            self.lighter_type, self.claimed_by, _fmt(self.order_date), _fmt(self.ship_by),

            # Status        Label Created    Label Printed       Customer   Sales platform
            self.status, self.label_created, self.label_printed, self.name, self.platform,

            # Qty          Receipt ID       Transaction ID
            self.quantity, self.receipt_id, self.transaction_id,
        ]

def gs_load(col_name: str) -> list:
    headers = WORKSHEET.row_values(HEADER_ROW)

    tx_id_col = headers.index(col_name) + 1
    return WORKSHEET.col_values(
        tx_id_col,
        value_render_option=ValueRenderOption.unformatted,
    )[HEADER_ROW:] # drop header 



def _fmt(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"