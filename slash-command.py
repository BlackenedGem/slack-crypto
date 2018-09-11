import argparse
from server import Server

# region Argparse
parser = argparse.ArgumentParser(description="Post messages to slack if a cryptocurrency has changed price significantly")
parser.add_argument("webhook url",
                    help="Slack incoming webhook URL")
parser.add_argument("signing secret",
                    help="Slack signing secret")
parser.add_argument("--port", "-p", default=80, type=int,
                    help="Web server port to run on")
args = parser.parse_args()
# endregion

Server.SIGNING_SECRET = getattr(args, "signing secret")
Server.run(args.port)