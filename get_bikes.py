import urllib2
import xmltodict
import json

def load_latest_bixi(stations):
    url = "https://secure.bixi.com/data/stations.json"
    response = urllib2.urlopen(url)
    data = json.load(response)
    
    for station in data['stations'][:1]:
        #print(station['id'])
        lat = station['la']
        lon = station['lo']
        last_update_t = station['lu']
        num_bikes = station['ba']
        num_docks = station['da'] 
        name = station['s'] 

    
