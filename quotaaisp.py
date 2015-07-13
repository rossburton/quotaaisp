#! /usr/bin/env python

USERNAME="USER"
PASSWORD="PASSWORD"

import datetime, time, monthdelta, urllib
import xml.etree.ElementTree as ET

def parseTime(s):
    # TODO add unit test for this
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))


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
    assert(isinstance(data['left'], int))
    assert(isinstance(data['monthly'], int))
    assert(isinstance(data['expiry'], float))
    assert(isinstance(data['time'], float))

    data['percent_remaining'] = data['left']*100 / data['monthly']

    last_month = time.mktime((datetime.datetime.fromtimestamp(data['expiry']) - monthdelta.MonthDelta(1)).timetuple())

    data['percent_time'] = int((data['time'] - last_month) * 100 / (data['expiry'] - last_month))



if __name__ == "__main__":
    result = urllib.urlopen("https://%s:%s@chaos.aa.net.uk/info" % (USERNAME, PASSWORD))
    tree = ET.parse(result)
    ET.dump(tree)

    for broadband in tree.iter("{https://chaos.aa.net.uk/}broadband"):
        data = parse(broadband)
        analyse(data)


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
