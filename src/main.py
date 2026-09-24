
from dotenv import load_dotenv
import logging
import os 
import sys
load_dotenv()

from dataclasses import asdict

from etsy_setup import setup
from order_gsheet.order_adder import add_order
from order_gsheet.order_updater import update_priorities
from order_data_fetcher import get_order_items

from datetime import datetime
import smtplib
from email.message import EmailMessage

TAB = "Order Management"

# Configure root logger to output to stdout
logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

LOG_FILE = 'order_fufillment_log.txt'

def notify_email(body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Order sync failed"
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["ALERT_TO"]
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_APP_PASSWORD"])
        s.send_message(msg)

def main():
    setup()

    with open(LOG_FILE, 'a', encoding='UTF-8') as f:
        for itm in get_order_items():
            try:
                if add_order(**asdict(itm)):
                    f.write(f"Added transaction {itm.transaction_id} @ {datetime.now()}\n")
            except Exception as e:
                f.write(f"Could not add order: {e}\n")
                notify_email(str(e))

        try:
            update_priorities()
        except Exception as e:
            f.write(f"Could not update priorities: {e}\n")
            notify_email(str(e))
        


if __name__ == '__main__':
    main()