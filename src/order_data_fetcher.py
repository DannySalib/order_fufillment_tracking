import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import requests 

from etsy_setup import (
    ETSY_API_BASE,
    SHOP_ID,
    get_headers,
)

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class OrderItem:
    receipt_id: int
    transaction_id: int
    name: str
    tray_color: str
    scoop_color: str
    lighter_type: str
    quantity: int
    order_date: datetime
    ship_by: datetime
    top: str = "NA"

class ListingID:
    MULTI_FUNCTIONAL_ASHTRAY = 4441845381
    TWO_TONE_MULTI_FUNCTIONAL_ASHTRAY = 4506620630
    ASH_TRAY_LID = 4518105925
    SHOREMAN = 4465534350


def get_order_items() -> list[OrderItem]:

    items: list[OrderItem] = []

    for receipt in fetch_open_receipts():
        receipt_id = receipt["receipt_id"]

        for tx in fetch_transactions(receipt_id):
            listing_id = tx.get("listing_id")
            variations = tx.get("variations", [])
            variation_data = _get_variation_data(listing_id, variations)

            if variation_data is None:
                logging.info(
                    f"Unexpected listing id '{listing_id}' "
                    f"title '{tx.get("title")}' "
                    f"receipt '{receipt_id}' " 
                    f"transaction '{tx.get("transaction_id")}' "
                )
                continue

            items.append(OrderItem(
                receipt_id=receipt_id,
                transaction_id=tx["transaction_id"],         
                name=receipt["name"],
                order_date=_from_ts(tx["created_timestamp"]),
                ship_by=_from_ts_opt(tx.get("expected_ship_date")),
                quantity=tx['quantity'],
                **variation_data
            ))

    return items

def fetch_open_receipts(page_size=100):
    """All paid-but-not-yet-shipped receipts, paginated."""
    results, offset = [], 0
    while True:
        resp = requests.get(
            f"{ETSY_API_BASE}/shops/{SHOP_ID}/receipts",
            headers=get_headers(),
            params={
                "was_paid": "true",
                "was_shipped": "false",
                "was_canceled": "false",
                "limit": page_size,
                "offset": offset,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        offset += page_size
        if offset >= data["count"]:
            break
    return results

def fetch_transactions(receipt_id):
    resp = requests.get(
        f"{ETSY_API_BASE}/shops/{SHOP_ID}/receipts/{receipt_id}/transactions",
        headers=get_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["results"]

def _from_ts(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)

def _from_ts_opt(ts: int | None) -> datetime:
    return _from_ts(ts) if ts is not None else datetime.today() + timedelta(days=7)

def _get_variation_data(listing_id: int, variations: list[dict]):
    match listing_id:
        case ListingID.MULTI_FUNCTIONAL_ASHTRAY: 
            return _get_variations_functional_ashtray(variations)
        case ListingID.TWO_TONE_MULTI_FUNCTIONAL_ASHTRAY: 
            return _get_variations_two_tone_ashtray(variations)
        case ListingID.ASH_TRAY_LID: 
            return _get_variations_ashtray_lid(variations)
        case ListingID.SHOREMAN: 
            return _get_variations_shoreman(variations)
        case _:
            return None

def _get_variations_functional_ashtray(variations: list[dict]) -> dict:
    return dict(
        tray_color=_get_variation_value(variations, "tray color", "tray colour"),
        scoop_color=_get_variation_value(variations, "scoop color", "scoop colour"),
        lighter_type=_get_variation_value(variations, "lighter type"),
    )

def _get_variations_two_tone_ashtray(variations: list[dict]) -> dict:
    color_way = _get_variation_value(variations, "colorway (top/bottom)").split(" / ")
    top, tray_color, *_ = color_way if len(color_way)>=2 else (None, None)
    return dict(
        tray_color=tray_color,
        top=top,
        scoop_color=_get_variation_value(variations, "scoop color", "scoop colour"),
        lighter_type=_get_variation_value(variations, "lighter type")
    )

def _get_variations_ashtray_lid(variations: list[dict]) -> dict:
    return dict(
        tray_color=_get_variation_value(variations, "primary color"),
        scoop_color=_get_variation_value(variations, "logo color"),
        lighter_type="lid",
    ) 

def _get_variations_shoreman(variations: list[dict]) -> dict:
    return dict(
        tray_color=_get_variation_value(variations, "color", "colour"),
        lighter_type=_get_variation_value(variations, "lighter type"),
        scoop_color="shoreman",
    )

    
def _get_variation_value(variations, *names, default=""):
    return next((
            v["formatted_value"]
            for v in variations
            if v["formatted_name"].lower().strip() in names
    ), default)

if __name__ == "__main__":
    from etsy_setup import setup
    setup()

    print(get_order_items())
