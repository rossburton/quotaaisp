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
    import http.client, urllib.request, urllib.parse, base64

    request = urllib.request.Request("https://chaos2.aa.net.uk/broadband/quota/xml")
    request.add_header("Authorization", b"Basic " + base64.b64encode(username.encode("ascii") + b":" + password.encode("ascii")))
    result = urllib.request.urlopen(request)

    if result.getcode() != http.client.OK:
        print("Cannot access CHAOS: %s" % http.client.responses[result.getcode()])
        sys.exit(1)
    return result

def parse(broadband):
    """
    broadband is a ElementTree.Element for the <broadband> node.  Returns a dict
    of parsed data.
    """
    if broadband.get("quota-monthly") is None or broadband.get("quota-remaining") is None or broadband.get("quota-timestamp") is None:
       raise Exception("Missing attributes")

    data = {
        "monthly": int(broadband.get("quota-monthly")),
        "left": int(broadband.get("quota-remaining")),
        "time": parseTime(broadband.get("quota-timestamp")),
        }
    return data


def analyse(data):
    assert(isinstance(data['left'], Number))
    assert(isinstance(data['monthly'], Number))
    assert(isinstance(data['time'], arrow.Arrow))

    # Amount of data used this quota allocation
    data['used'] = data['monthly'] - data['left']
    data['percent_remaining'] = int(data['left']*100 / data['monthly'])
    data['percent_used'] = int((data['monthly'] - data['left'])*100 / data['monthly'])

    data['expiry'] = data['time'].ceil('month')
    data['start'] = data['time'].floor('month')

    # How far through the current quota allocation we are in time. 0% is just
    # started, 100% is finished.
    data['percent_time'] = int((data['time'].int_timestamp - data['start'].int_timestamp) * 100 / (data['expiry'].int_timestamp - data['start'].int_timestamp))

    return data


if __name__ == "__main__":
    import sys
    username, password = get_auth()
    if not username or not password:
        print("Please set username/password")
        sys.exit(1)

    tree = ET.parse(fetch(username, password))
    for broadband in tree.iter("{https://chaos2.aa.net.uk/}quota"):
        data = parse(broadband)
        analyse(data)

        if data['used'] < 0:
            print("%dGB in credit, %dGB remaining\nRenewed %s" % (
                abs(data['used'] / 1000 / 1000 / 1000),
                data['left'] / 1000 / 1000 / 1000,
                data['expiry'].humanize(granularity='day')))
        else:
            print("%dGB used, %dGB remaining (%d%% used)\nRenewed %s (%d%%)" % (
                data['used'] / 1000 / 1000 / 1000,
                data['left'] / 1000 / 1000 / 1000,
                data['percent_used'],
                data['expiry'].humanize(granularity='day'),
                data['percent_time']))

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
