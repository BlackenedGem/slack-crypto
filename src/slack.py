import logging
import requests
import json

from src.coinbase import Currency, Coinbase
from src.stats import HourData
from src.constants import SlackColourThresholds

class Slack:
    ATTACHMENT_MIN_WIDTH = 21

    @classmethod
    def post_to_slack(cls, name: str, icon_url: str, text: str, attachments: list, slack_url: str, channel=""):
        slack_data = {"username": name, "icon_url": icon_url, "text": text, "attachments": attachments, "channel": channel}
        response = "null"

        try:
            response = requests.post(slack_url, data=json.dumps(slack_data), headers={"content-type": "application/json"})
            if response.status_code != requests.codes.ok:
                cls.slack_error_msg(response, slack_data)
                return -1
        except requests.exceptions.ConnectionError:
            logging.exception("Connection refused")
            cls.slack_error_msg(response, slack_data)
            return -1
        except Exception as e:
            logging.exception("An exception occurred:")
            logging.exception(e)
            cls.slack_error_msg(response, slack_data)
            return -1

    @classmethod
    def slack_error_msg(cls, response, slack_data):
        logging.error("An error occurred posting to slack")
        logging.error("Response given:")
        logging.error(response)
        logging.error("Data sent:")
        logging.error(slack_data)

    @classmethod
    def generate_attachments(cls, currency: Currency, hour_price_map: dict, cur_price: float, hours):
        attachments = []

        for time_ago in sorted(hour_price_map.keys()):
            price_ago = hour_price_map[time_ago]

            attachments.append(cls.format_price_entry(cur_price, price_ago, currency, time_ago, hours))

        return attachments

    @classmethod
    def generate_post(cls, prices: list, current_stats: HourData, currency: Currency):
        cur_price = current_stats.cur_price
        price_1_hour = prices[1]
        price_24_hour = prices[24]
        price_7_day = prices[24 * 7]

        sign_str = "up" if current_stats.is_diff_positive else "down"
        attachment_pretext = f"{currency.crypto_long}'s price has gone {sign_str}. Current price: {currency.fiat_symbol}{cls.format_num(current_stats.cur_price)}"

        # noinspection PyListCreation
        attachments = []

        hour_entry = cls.format_price_entry(cur_price, price_1_hour, currency, 1)
        hour_entry['pretext'] = attachment_pretext
        attachments.append(hour_entry)
        attachments.append(cls.format_price_entry(cur_price, price_24_hour, currency, 24))
        attachments.append(cls.format_price_entry(cur_price, price_7_day, currency, 7, False))

        # Try to add 28 day stats
        # noinspection PyBroadException
        try:
            cb = Coinbase(currency)
            price_28_days = cb.price_days_ago(28)
            attachments.append(cls.format_price_entry(cur_price, price_28_days, currency, 28, False))
        except Exception as e:
            logging.exception(e)
            logging.exception("Ignoring error, posting 3 historical prices instead of 4 (28 day price omitted)")
        
        return attachments

    @classmethod
    def format_price_entry(cls, cur_price: float, historical_price: float, currency: Currency, units_ago: int, hours=True):
        diff = cur_price - historical_price
        diff /= historical_price
        diff *= 100

        if diff > SlackColourThresholds.GOOD:
            colour = "good"
        elif diff > SlackColourThresholds.NEUTRAL:
            colour = ""
        elif diff > SlackColourThresholds.WARNING:
            colour = "warning"
        else:
            colour = "danger"

        time_unit = "hour" if hours else "day"
        if units_ago != 1:
            time_unit += "s"
        pretext = f"Price {units_ago} {time_unit} ago:"
        chars_to_pad = 2 * (cls.ATTACHMENT_MIN_WIDTH - len(pretext))
        pretext += " " * chars_to_pad

        text = f"{pretext}{currency.fiat_symbol}{cls.format_num(historical_price)} ({diff:+.2f}%)"
        attachment = {"fallback": "some price changes", "text": text, "color": colour}

        return attachment

    @staticmethod
    def format_num(num: float):
        if num < 100:
            return f"{num:,.2f}"
        if num < 1000:
            return f"{num:,.1f}"
        else:
            return f"{num:,.0f}"
