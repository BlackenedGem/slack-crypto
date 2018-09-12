import argparse
import sys
import os
import logging
from datetime import datetime

from src.history import History
from src.analysis import Analysis
from src.coinbase import Coinbase, Currencies
from src.slack import Slack
from src.stats import HourData
from src.constants import SlackImages

# Pre argparse constants
LOG_LOC = "log_webhook"

# region Argparse
parser = argparse.ArgumentParser(description="Post messages to slack if a cryptocurrency has changed price significantly")
parser.add_argument("url",
                    help="Slack incoming webhook URL")
parser.add_argument("--channel", "-c", default="",
                    help="Specify slack channel")
parser.add_argument("--name", "-n", default="Cryptocorn",
                    help="Webhook name",)
parser.add_argument("--ema", "-e", default=26, type=int,
                    help="Number of hours for EMA calculation")
parser.add_argument("--interval", "--i", default=60, type=int, choices=[5, 15, 60],
                    help="Resolution of data to fetch from coinbase (minutes)")
parser.add_argument("--threshold-ema", "-te", default=2.5, type=float,
                    help="Amount current price needs to be above/below the EMA to cause a post to be sent")
parser.add_argument("--threshold-reset", "-tr", default=1.25, type=float,
                    help="Amount EMA price needs to be within last post price to reset")
parser.add_argument("--script-name", "-sn", default="",
                    help="Name of the script. Changes the name of json file and log location (use this if you're running the script multiple"
                         "times with different parameters)")
parser.add_argument("--log-file", "-lf", action="store_true",
                    help=f"Output logs into files in /{LOG_LOC}")
args = parser.parse_args()
# endregion

# region Constants
# Configurable Constants
EMA_THRESHOLD_PERCENT = args.threshold_ema
EMA_NUM_HOURS = args.ema
EMA_RESET_PERCENT = args.threshold_reset

BOT_NAME = args.name
SLACK_CHANNEL = args.channel

# 'Hard' Constants - may rely on other values set but shouldn't be changed
SLACK_URL = args.url
if args.script_name != "":
    DATA_FILE = f"last_post_data_{args.script_name}.json"
else:
    DATA_FILE = "last_post_data.json"
# endregion

# region Logging
logger = logging.getLogger()
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

if args.log_file:
    if not os.path.isdir(LOG_LOC):
        os.mkdir(LOG_LOC)

    fileHandler = logging.FileHandler(f"{LOG_LOC}/" + datetime.now().strftime("%Y-%m-%d %H;%M;%S") + ".txt")
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)
# endregion

# Get data and convert accordingly
cb = Coinbase(Currencies.default(), args.interval)
prices = cb.price_list()
cur_price = prices[0]

# Get history from last runs, use it to work out what test to make
history = History(DATA_FILE)

# Get stats from coinbase data
# If change isn't large enough, then update history and exit
stats = HourData(prices, EMA_NUM_HOURS)
if Analysis.ema_checks(stats, history, EMA_THRESHOLD_PERCENT, EMA_RESET_PERCENT):
    sys.exit(1)

if not Analysis.should_post(history, stats, prices, EMA_THRESHOLD_PERCENT):
    sys.exit(1)

print("Message should be posted, generating attachment")
attachments = Slack.generate_post(prices, stats, Currencies.default())
image_url = SlackImages.get_image(stats.is_diff_positive)
print("Posting to slack")
Slack.post_to_slack(BOT_NAME, image_url, "", attachments, SLACK_URL, SLACK_CHANNEL)

history.price = stats.cur_price
history.rising = stats.is_diff_positive
history.ema_reset = False
history.save()

print("Done")
