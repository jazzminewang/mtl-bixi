"""
used to grab and store current station status
"""
import time
from launch_webpage import load_latest_bixi
import pandas as pd
stat, fn = load_latest_bixi()
stat.to_csv(fn.replace('json', 'csv'))
while True:
    stat, fn = load_latest_bixi(stat)
    stat.to_csv(fn.replace('json', 'csv'))
    time.sleep(60*10)

