#! /usr/bin/env python2

USERNAME="USER"
PASSWORD="PASSWORD"

import arrow
from numbers import Number
import xml.etree.ElementTree as ET

def parseTime(s):
    return arrow.get(s, "YYYY-MM-DD HH:mm:ss")


def parse(broadband):
    """
    broadband is a ElementTree.Element for the <broadband> node.  Returns a dict
    of parsed data.
    """
    data = {
        "monthly": int(broadband.get("quota-monthly")),
        "left": int(broadband.get("quota-left")),
        "time": parseTime(broadband.get("quota-time")),
        "expiry": parseTime(broadband.get("quota-expiry"))
        }
    return data


def analyse(data):
    assert(isinstance(data['left'], Number))
    assert(isinstance(data['monthly'], Number))
    assert(isinstance(data['expiry'], arrow.Arrow))
    assert(isinstance(data['time'], arrow.Arrow))

    data['percent_remaining'] = data['left']*100 / data['monthly']

    last_month = data['expiry'].replace(months=-1)

    data['percent_time'] = int((data['time'].timestamp - last_month.timestamp) * 100 / (data['expiry'].timestamp - last_month.timestamp))



if __name__ == "__main__":
    import urllib
    result = urllib.urlopen("https://%s:%s@chaos.aa.net.uk/info" % (USERNAME, PASSWORD))
    tree = ET.parse(result)

    for broadband in tree.iter("{https://chaos.aa.net.uk/}broadband"):
        data = parse(broadband)
        analyse(data)
        print "%dGB remaining (%d%% of quota), renewed %s" % (
            data['left'] / 1000 / 1000 / 1000,
            data['percent_remaining'],
            data['expiry'].humanize())

import unittest
class QuotaaispTest(unittest.TestCase):
    def runTest(self):
        xml = ET.Element("broadband")
        xml.set("quota-monthly", "200000000000")
        xml.set("quota-left", "156575605264")
        xml.set("quota-time", "2015-07-13 17:00:00")
        xml.set("quota-expiry", "2015-08-01 00:00:00")
        data = parse(xml)
        analyse(data)
        self.assertEquals(data['percent_remaining'], 78)
        self.assertEquals(data['percent_time'], 40)
