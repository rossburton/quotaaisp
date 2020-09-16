#! /usr/bin/env python3

import arrow
from numbers import Number
import xml.etree.ElementTree as ET


def parseTime(s):
    return arrow.get(s, "YYYY-MM-DD HH:mm:ss")

def get_auth():
    import configparser, os

    cp = configparser.ConfigParser()
    cp.read(os.path.expanduser("~/.config/quotaaisp.conf"))
    if cp.has_option("Config", "Username") and cp.has_option("Config", "Password"):
        return cp.get("Config", "Username"), cp.get("Config", "Password")
    else:
        return None, None

def fetch(username, password):
    import http.client, urllib.request, urllib.parse, base64, json

    request = urllib.request.Request("https://chaos2.aa.net.uk/broadband/info")
    request.add_header("Authorization", b"Basic " + base64.b64encode(username.encode("ascii") + b":" + password.encode("ascii")))
    result = urllib.request.urlopen(request)

    if result.getcode() != http.client.OK:
        print("Cannot access CHAOS: %s" % http.client.responses[result.getcode()])
        sys.exit(1)
    
    return json.loads(result.read())

def analyse(data):
    result = dict(data)

    quota_remaining = result['quota_remaining'] = int(data['quota_remaining'])
    quota_monthly = result['quota_monthly'] = int(data['quota_monthly'])
    quota_timestamp = parseTime(data['quota_timestamp'])

    # Amount of data used this quota allocation
    result['used'] = quota_monthly - quota_remaining
    result['percent_remaining'] = int(quota_remaining*100 / quota_monthly)
    result['percent_used'] = int((quota_monthly - quota_remaining)*100 / quota_monthly)

    result['expiry'] = quota_timestamp.ceil('month')
    result['start'] = quota_timestamp.floor('month')

    # How far through the current quota allocation we are in time. 0% is just
    # started, 100% is finished.
    result['percent_time'] = int((quota_timestamp.timestamp - result['start'].timestamp) * 100 / (result['expiry'].timestamp - result['start'].timestamp))

    return result


if __name__ == "__main__":
    import sys
    username, password = get_auth()
    if not username or not password:
        print("Please set username/password")
        sys.exit(1)

    data = fetch(username, password)
    for info in data['info']:
        result = analyse(info)

        print(f"Download {result['tx_rate_adjusted']} Upload {result['rx_rate']}")
        if result['used'] < 0:
            print("%dGB in credit, %dGB remaining\nRenewed %s" % (
                abs(result['used'] / 1000 / 1000 / 1000),
                result['quota_remaining'] / 1000 / 1000 / 1000,
                result['expiry'].humanize()))
        else:
            print("%dGB used, %dGB remaining (%d%% used)\nRenewed %s (%d%%)" % (
                result['used'] / 1000 / 1000 / 1000,
                result['quota_remaining'] / 1000 / 1000 / 1000,
                result['percent_used'],
                result['expiry'].humanize(),
                result['percent_time']))

# configure ; set traffic-control smart-queue Bufferbloat upload rate 790000bit; commit; save

import unittest
class QuotaaispTest(unittest.TestCase):
    def create_data(self):
        xml = ET.Element("broadband")
        # 200GB monthly quota
        xml.set("quota-monthly", "200000000000")
        # 156GB remaining
        xml.set("quota-remaining", "156575605264")
        # Current time is 5pm, 13th July 2015
        xml.set("quota-timestamp", "2015-07-13 17:00:00")
        return xml

    def test_basic(self):
        xml = self.create_data()
        data = analyse(parse(xml))
        self.assertEqual(data['percent_used'], 21)
        self.assertEqual(data['percent_remaining'], 78)
        self.assertEqual(data['percent_time'], 40)

    def test_used(self):
        xml = self.create_data()
        xml.set("quota-monthly", 200)

        xml.set("quota-remaining", 200)
        data = analyse(parse(xml))
        self.assertEqual(data['used'], 0)

        xml.set("quota-remaining", 100)
        data = analyse(parse(xml))
        self.assertEqual(data['used'], 100)

        xml.set("quota-remaining", 0)
        data = analyse(parse(xml))
        self.assertEqual(data['used'], 200)


    def test_percent_time(self):
        xml = self.create_data()

        xml.set("quota-timestamp", "2015-07-13 17:00:00")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_time'], 40)

        xml.set("quota-timestamp", "2015-07-01 00:00:00")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_time'], 0)

        xml.set("quota-timestamp", "2015-07-31 23:59:59")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_time'], 100)


    def test_percent_remaining(self):
        xml = self.create_data()

        xml.set("quota-remaining", "200000000000")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_remaining'], 100)

        xml.set("quota-remaining", "100000000000")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_remaining'], 50)

        xml.set("quota-remaining", "000000000000")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_remaining'], 0)


    def test_percent_used(self):
        xml = self.create_data()

        xml.set("quota-remaining", "200000000000")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_used'], 0)

        xml.set("quota-remaining", "100000000000")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_used'], 50)

        xml.set("quota-remaining", "000000000000")
        data = analyse(parse(xml))
        self.assertEqual(data['percent_used'], 100)

    def test_auth(self):
        username, password = get_auth()
        if username and password:
            node = ET.parse(fetch(username, password)).getroot()
            self.assertEqual(node.tag, "{https://chaos2.aa.net.uk/}chaos")
            node = node.find("{https://chaos2.aa.net.uk/}quota")
            self.assertIsNotNone(node)
        else:
            self.skipTest("Cannot find authentication credentials")

    def test_fetch(self):
        username, password = get_auth()
        if username and password:
            response = fetch(username, password)
            tree = ET.parse(response)
            #ET.dump(tree)
        else:
            self.skipTest("Cannot find authentication credentials")
