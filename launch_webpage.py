import pandas as pd
import webbrowser
import os
import sys
import LatLon 
import urllib2
import json
import time
myapikey="AIzaSyA3gkwI5NRxt_m4vfQW6CZd5qpna0SaRyw"

def load_latest_bixi(stations=pd.DataFrame(columns={'name', 'new', 'moved', 'lat', 'lon', 'num_bikes', 'num_docks', 'last_update', 'll'})):
    url = "https://secure.bixi.com/data/stations.json"
    response = urllib2.urlopen(url)
    data = json.load(response)
    existing_station_codes = list(stations.index)
    for station in data['stations']:
        station_code = station['n']
        lat = station['la']
        lon = station['lo']
        num_bikes = station['ba']
        num_docks = station['da']
        last_update = station['lu']
        if station_code in existing_station_codes:
            station.loc[station_code, 'new'] = False
            cols = ['new', 'num_bikes', 'num_docks', 'last_update', 'll']
            
            vals = [False, num_bikes, num_docks, last_update, ll]
            # check if lat/lon changed
            if not ((stations.loc[station_code,'lat']==lat) and
                    (stations.loc[station_code,'lon']==lon)):
                ll = LatLon.LatLon(LatLon.Latitude(lat), LatLon.Longitude(lon))
                lcols = ['moved', 'lat', 'lon', 'll']
                lvals = [True, lat, lon, ll]
                stations.loc[station_code,lcols] = lvals
            else:
                stations.loc[station_code,'moved'] = False            
        else:
            # create new station
            ll = LatLon.LatLon(LatLon.Latitude(lat), LatLon.Longitude(lon))
            cols = ['name', 'new', 'moved', 'lon', 
                    'lat', 'num_bikes', 'num_docks', 'last_update', 'll']
            vals = [station['s'], True, True, lon, 
                    lat, num_bikes, num_docks, last_update, ll]
            
            stations.loc[station_code, cols] = vals
                    
    return stations
        

def find_distance_to_stations(ulat, ulon, lspd):
    uu = LatLon.LatLon(LatLon.Latitude(ulat), LatLon.Longitude(ulon))
    lls = lspd.loc[:,'ll']
    
    ds = []
    for l in lls:
        ds.append(uu.distance(l))
    return ds

def get_latlon(userloc):
    loc = userloc.replace(" ", "+")
    url="https://maps.googleapis.com/maps/api/geocode/json?address=%s&key=%s"
    url=url%(loc,myapikey)
    response = urllib2.urlopen(url)
    data = json.load(response)
    ll = data['results'][0]['geometry']['location']
    return ll['lat'], ll['lng']


def find_nearest_checkin_station(userloc, spd):
    userlat, userlon = get_latlon(userloc)
    dists = find_distance_to_stations(userlat, userlon, spd)
    spd['dist'] = dists
    spds = spd.sort_values(axis=0, by='dist') 
    spds = spds.loc[spds['num_docks']>1]
    spdsn = spds.index[0]
    spds.loc[spdsn,['lat', 'lon']].values.tolist()
    lls = spds.loc[spdsn,['lat', 'lon']].values.tolist()
    nearest_dest_bixi = ','.join([str(a) for a in lls])
    return nearest_dest_bixi, spds.loc[spdsn,:]

def find_nearest_checkout_station(userloc, spd):
    userlat, userlon = get_latlon(userloc)
    dists = find_distance_to_stations(userlat, userlon, spd)
    spd['dist'] = dists
    spds = spd.sort_values(axis=0, by='dist') 
    spds = spds.loc[spds['num_bikes']>1]
    spdsn = spds.index[0]
    spds.loc[spdsn,['lat', 'lon']].values.tolist()
    lls = spds.loc[spdsn,['lat', 'lon']].values.tolist()
    nearest_org_bixi = ','.join([str(a) for a in lls])
    return nearest_org_bixi, spds.loc[spdsn,:]


def calc_route(origin, dest, how='walking'):

    dirmyapikey = "AIzaSyDBfClCWLI7ruwY-79sakIAKEiin2FNKUc"
    call = "https://maps.googleapis.com/maps/api/directions/json?origin=%s&destination=%s&departure_time=%s&mode=%s&traffic_model=best_guess&key=%s" 
    dtt = int(time.time())
    call = call%(origin.replace(' ', '+'), dest.replace(' ','+'), 
                 dtt, how, dirmyapikey)
    r = urllib2.urlopen(call)
    data = json.load(r)
    dis_meters = data['routes'][0]['legs'][0]['distance']['value']
    duration_secs = data['routes'][0]['legs'][0]['duration']['value']
    return dis_meters, duration_secs

def calc_walk_calories(meters, weight=80.):
    calories_per_meter = 0.0006421232876712328
    return meters*weight*calories_per_meter

def open_google(user_origin, user_dest, spd):
    nearest_origin_bixi, ospd = find_nearest_checkout_station(user_origin, spd)
    nearest_dest_bixi, dspd = find_nearest_checkin_station(user_dest, spd)


    mapcall = "https://www.google.com/maps/dir/?api=1&origin=origin=%s&waypoints=%s|%s&destination=%s&travelmode=bicycling" %(
          user_origin, nearest_origin_bixi, nearest_dest_bixi, user_dest)
    webbrowser.open(mapcall)
    #bike_dist, bike_secs = calc_route(nearest_origin_bixi, nearest_dest_bixi, 'biking')
    #org_walk_dist, org_walk_secs = calc_route(user_origin, nearest_origin_bixi, 'walking')
    #dest_walk_dist, dest_walk_secs = calc_route(nearest_dest_bixi, user_dest, 'walking')
    #total_walked_m = dest_walk_dist + org_walk_dist
    #walk_calories = calc_walk_calories(total_walked_m)
    
def test_launch():
    user_origin = "Musee Redpath"
    user_dest = "Desjardins Lab, Rene-Levesque Boulevard West, Montreal, QC, Canada"

    spd = load_latest_bixi()
    open_google(user_origin, user_dest, spd)


if __name__ == '__main__':
    test_launch()
