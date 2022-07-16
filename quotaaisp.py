#! /usr/bin/env python3

import configparser
import os
import unittest
import requests

import arrow


def parseTime(s):
    if isinstance(s, str):
        return arrow.get(s, "YYYY-MM-DD HH:mm:ss")
    return s


def get_auth():
    cp = configparser.ConfigParser()
    with open(os.path.expanduser("~/.config/quotaaisp.conf")) as f:
        cp.read_file(f)
    return cp.get("Config", "Username"), cp.get("Config", "Password")


def fetch():
    return requests.get(
        "https://chaos2.aa.net.uk/broadband/quota/json", auth=get_auth()
    ).json()


def fixup(data):
    lines = {}

    for option in data["options"]:
        if "option" not in option:
            continue

        option = option["option"][0]
        if option["name"] == "service":
            for choice in option["choice"]:
                value = choice["value"]
                if value:
                    lines[int(value)] = choice["title"]

    for quota in data["quota"]:
        quota["name"] = lines[int(quota["ID"])]
        quota["quota_monthly"] = int(quota["quota_monthly"])
        quota["quota_remaining"] = int(quota["quota_remaining"])
        quota["quota_timestamp"] = parseTime(quota["quota_timestamp"])

        # Amount of data used this quota allocation
        quota["quota_used"] = quota["quota_monthly"] - quota["quota_remaining"]
        quota["percent_remaining"] = int(
            quota["quota_remaining"] * 100 / quota["quota_monthly"]
        )
        quota["percent_used"] = int(
            (quota["quota_monthly"] - quota["quota_remaining"])
            * 100
            / quota["quota_monthly"]
        )

        quota["expiry"] = quota["quota_timestamp"].ceil("month")
        quota["start"] = quota["quota_timestamp"].floor("month")

        # How far through the current quota allocation we are in time. 0% is just
        # started, 100% is finished.
        quota["percent_time"] = int(
            (quota["quota_timestamp"].int_timestamp - quota["start"].int_timestamp)
            * 100
            / (quota["expiry"].int_timestamp - quota["start"].int_timestamp)
        )

    return data


if __name__ == "__main__":
    data = fetch()
    # with open("chaos.json") as f:
    #    data = json.load(f)
    data = fixup(data)

    for quota in data["quota"]:

        print(quota["name"])
        if quota["quota_used"] < 0:
            print(
                "%dGB in credit, %dGB remaining\nRenewed %s"
                % (
                    abs(quota["quota_used"] / 1000 / 1000 / 1000),
                    quota["quota_remaining"] / 1000 / 1000 / 1000,
                    quota["expiry"].humanize(),
                )
            )
        else:
            print(
                "%dGB used, %dGB remaining (%d%% used)\nRenewed %s (%d%%)"
                % (
                    quota["quota_used"] / 1000 / 1000 / 1000,
                    quota["quota_remaining"] / 1000 / 1000 / 1000,
                    quota["percent_used"],
                    quota["expiry"].humanize(),
                    quota["percent_time"],
                )
            )
        print()


class QuotaaispTest(unittest.TestCase):
    def create_data(self):
        return fixup(
            {
                "command": "quota",
                "options": [
                    {
                        "option": [
                            {
                                "choice": [
                                    {"title": "Line 1", "value": "1"},
                                ],
                                "name": "service",
                            }
                        ],
                    },
                ],
                "quota": [
                    {
                        "ID": "1",
                        "quota_monthly": "200000000000",
                        "quota_remaining": "156575605264",
                        "quota_timestamp": "2015-07-13 17:00:00",
                    },
                ],
            }
        )

    def test_basic(self):
        data = self.create_data()
        quota = data["quota"][0]
        self.assertEqual(quota["percent_used"], 21)
        self.assertEqual(quota["percent_remaining"], 78)
        self.assertEqual(quota["percent_time"], 40)

    def test_used(self):
        data = self.create_data()
        quota = data["quota"][0]
        quota["quota_monthly"] = 200

        quota["quota_remaining"] = 200
        data = fixup(data)
        self.assertEqual(quota["quota_used"], 0)

        quota["quota_remaining"] = 100
        data = fixup(data)
        self.assertEqual(quota["quota_used"], 100)

        quota["quota_remaining"] = 0
        data = fixup(data)
        self.assertEqual(quota["quota_used"], 200)

    def test_percent_time(self):
        data = self.create_data()
        quota = data["quota"][0]

        quota["quota_timestamp"] = "2015-07-13 17:00:00"
        data = fixup(data)
        self.assertEqual(quota["percent_time"], 40)

        quota["quota_timestamp"] = "2015-07-01 00:00:00"
        data = fixup(data)
        self.assertEqual(quota["percent_time"], 0)

        quota["quota_timestamp"] = "2015-07-31 23:59:59"
        data = fixup(data)
        self.assertEqual(quota["percent_time"], 100)

    def test_percent_remaining(self):
        data = self.create_data()
        quota = data["quota"][0]

        quota["quota_remaining"] = "200000000000"
        data = fixup(data)
        self.assertEqual(quota["percent_remaining"], 100)

        quota["quota_remaining"] = "100000000000"
        data = fixup(data)
        self.assertEqual(quota["percent_remaining"], 50)

        quota["quota_remaining"] = "000000000000"
        data = fixup(data)
        self.assertEqual(quota["percent_remaining"], 0)

    def test_percent_used(self):
        data = self.create_data()
        quota = data["quota"][0]

        quota["quota_remaining"] = "200000000000"
        data = fixup(data)
        self.assertEqual(quota["percent_used"], 0)

        quota["quota_remaining"] = "100000000000"
        data = fixup(data)
        self.assertEqual(quota["percent_used"], 50)

        quota["quota_remaining"] = "000000000000"
        data = fixup(data)
        self.assertEqual(quota["percent_used"], 100)

    def test_fetch(self):
        try:
            get_auth()
        except Exception as e:
            self.skipTest(f"Cannot find authentication credentials ({e}")
        data = fetch()
        self.assertIsNotNone(data)
