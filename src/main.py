
from dotenv import load_dotenv
import logging
import sys
load_dotenv()

from dataclasses import asdict

from etsy_setup import setup
from order_gsheet.order_adder import add_order
from order_gsheet.order_updater import update_priorities
from order_data_fetcher import get_order_items

from datetime import datetime
TAB = "Order Management"

# Configure root logger to output to stdout
logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

LOG_FILE = 'order_fufillment_log.txt'

def main():
    setup()

    with open(LOG_FILE, 'a', encoding='UTF-8') as f:
        for itm in get_order_items():
            try:
                if add_order(**asdict(itm)):
                    f.write(f"Added transaction {itm.transaction_id} @ {datetime.now()}\n")
            except Exception as e:
                f.write(f"Could not add order: {e}\n")

        try:
            update_priorities()
        except Exception as e:
            f.write(f"Could not update priorities: {e}\n")
        


if __name__ == '__main__':
    main()