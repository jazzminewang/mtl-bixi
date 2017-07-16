import numpy as np
import pandas as pd
from glob import glob
import os
from workalendar import canada
from workalendar import usa
import LatLon
from kitchen.text.converters import to_unicode
from unidecode import unidecode
import geocoder

def load_loc(name):
    l = pd.read_csv(name, encoding='utf-8')
    l['filename'] = os.path.split(name)[1]
    l['year'] = int((os.path.split(name)[1].split('.csv')[0].split('_'))[1])
    l.index = l['code']
    print('loaded %s station locations from:%s' %(name, l.shape[0]))
    return l

def format_station_print(l):
    l = to_unicode(l)
    if to_unicode("Metro") in l:
        return ' '.join(l.split(' ')[:2])
    # remove helpers
    for dd in ['de ', 'du ', "(Sud)"]:
        if dd in l:
            l = l.replace(dd, '')
    if ' / ' in l:
        l = l.replace(' / ', '/')
    return l.strip()

def load_stats(station_location_files=[], sfile='stations.csv'):
    if os.path.exists(sfile):
        print("Loading station infromation from saved file")
        blocs = pd.read_csv(sfile)
    else:
        print("Creating station information file with relevant information")
        loc_files = station_location_files
        loclist = []
        for ll in loc_files:
            loclist.append(load_loc(ll))
        blocs = pd.concat(loclist)
        blocs.drop_duplicates(subset=['code'], keep='last', inplace=True)
        downtown = LatLon.LatLon(LatLon.Latitude(45.504045), LatLon.Longitude(-73.569101))
        stat_loc = [LatLon.LatLon(
                        LatLon.Latitude(blocs.loc[stat,'latitude']), 
                        LatLon.Latitude(blocs.loc[stat,'longitude']))
                        for stat in blocs.index]
        
        print("finding elevation for each station")
        ggs = [geocoder.elevation("%s, %s" %(
                              blocs.loc[stat,'latitude'],
                              blocs.loc[stat,'longitude']))
                              for stat in blocs.index]
        elevs = [g.meters for g in ggs]
        dist_dt = [downtown.distance(sl) for sl in stat_loc]
        blocs['distance_to_downtown'] = dist_dt
        blocs['LatLon'] = stat_loc
        blocs['elev'] = elevs
    
        nbl = []
        for bl in blocs['name']:
            #nbl.append(format_station_print(bl))
            t=unidecode(bl)
            t.encode("ascii")  #works fine, because all non-ASCII from s are replaced with their equivalents
            nbl.append(t) 
        blocs['name fmt'] = nbl
        # remove names which are not easily written to file
        del blocs['name']
        blocs.to_csv(sfile)
    return blocs

def load_bike(bb):
    print("loading bike file %s"  %bb)
    b = pd.read_csv(bb)
    b['start_date'] = pd.to_datetime(b['start_date'])
    b['end_date'] = pd.to_datetime(b['end_date'])
    b['filename'] = os.path.split(bb)[1]
    b['orig index'] = b.index
    return b
 
def load_default():
    year = '2016' #* for all
    data_base_path = 'data'
    bicycle_files = glob(os.path.join(data_base_path, 'bikes', "BixiMontrealRentals%s"%year, "OD*.csv"))
    loc_files = glob(os.path.join(data_base_path, 'bikes', "BixiMontrealRentals%s"%year, "Station*.csv"))
    # historical weather gathered from http://climate.weather.gc.ca
    weather_files = glob(os.path.join(data_base_path, 'airport-weather', '*.csv'))
    blocs = load_stats(station_location_files=loc_files)
    weather, weather_codes = load_weather(weather_files=weather_files)
    bdata = load_bike_files(blocs, weather, bike_files=bicycle_files)
    return blocs, weather, weather_codes, bdata

def load_all(sfile='station.csv', bfile='bike_all.csv',  wfile='weather.csv', bike_files=[], station_location_files=[], weather_files=[]):
    blocs = load_stats(station_location_files=station_location_files, sfile=sfile)
    weather, weather_code_names = load_weather(wfile=wfile, weather_files=weather_files)
    wbdata = load_bike_files(blocs, weather, bfile=bfile, bike_files=bike_files)
    return blocs, weather, weather_code_names, wbdata

def load_bike_files(blocs, weather, bfile='bike_all.csv', bike_files=[]):
    if os.path.exists(bfile):
        print("Loading bikes with weather from saved file")
        wbdata = pd.read_csv(bfile)
    else:
        print("Creating merged bike file with weather, this may take some time")

        blist = []
        for bb in bike_files:
            blist.append(load_bike(bb))
        bdata = pd.concat(blist)
        bdata['all index'] = np.arange(bdata.shape[0])
        # o inclume data for members of bixi and throw out occassional users
        #bdata = bdata[bdata['is_member']>0]
        bdata['duration_min'] = bdata['duration_sec']/60.0
        # get day of week of each start of bike ride
        print("Adding date/time information")
        bdata.loc[:,'dt'] = pd.to_datetime(bdata['start_date'])
        dtt = bdata['dt'].dt
        bdata.loc[:,'weekday'] = dtt.dayofweek
        bdata.loc[:,'year'] = dtt.year
        bdata.loc[:,'date'] = dtt.date
        bdata.loc[:,'hour'] = dtt.hour
        bdata.loc[:,'time'] = dtt.time
        bdata.loc[:,'day of year'] = dtt.dayofyear
        bdata.loc[:, 'isweekday'] = bdata['weekday']<5
        bdata['instance'] = np.ones(bdata.shape[0])
        
        # determine if day is a holiday
        print("calculating holidays")
        holidays = []
        ca = canada.Canada()
        qc = canada.Quebec()
        on = canada.Ontario()
        us = usa.UnitedStates()
        for y in bdata['year'].unique():
            # add neighboring jurisdiction holidays
            for holiday in ca.holidays(y)+qc.holidays(y)+on.holidays(y)+us.holidays(y):
                holidays.append(pd.to_datetime(holiday[0]))
        holidays = pd.Series(holidays).dt.date
        bdata.loc[:,'isholiday'] = bdata['date'].isin(holidays).astype(np.int) 
        # dd lat lon information to data
        codes = blocs['code'].unique()
        bdata['start_lat'] = np.zeros(bdata.shape[0])
        bdata['start_lon'] = np.zeros(bdata.shape[0])
        bdata['end_lat'] = np.zeros(bdata.shape[0])
        bdata['end_lon'] = np.zeros(bdata.shape[0])
        for code in codes:
            station_name = blocs[blocs.loc[:,'code']==code]['name fmt']
            station_lat = blocs[blocs.loc[:,'code']==code]['latitude']
            station_lon = blocs[blocs.loc[:,'code']==code]['longitude']
            station_elev = blocs[blocs.loc[:,'code']==code]['elev']
            _start = bdata['start_station_code']==code
            bdata.loc[_start, 'start_station_name'] = station_name 
            bdata.loc[_start, 'start_station_elev'] = station_elev
            bdata.loc[_start, 'start_lat'] = station_lat
            bdata.loc[_start, 'start_lon'] = station_lon
            _end = bdata['end_station_code']==code
            bdata.loc[_end,  'end_station_name'] = station_name
            bdata.loc[_end, 'end_station_elev'] = station_elev
            bdata.loc[_end, 'end_lat'] = station_lat
            bdata.loc[_end, 'end_lon'] = station_lon
     
        # for simplicity, find nearest hour of rack event
        bdata['start hour'] = pd.to_datetime(pd.DatetimeIndex(bdata['start_date']).round("1h"))#.dt.hour
        bdata['start hour'] = bdata['start hour'].dt.hour
        bdata['start datehour'] = pd.DatetimeIndex(bdata['start_date']).round("1h")
        bdata['end hour'] = pd.to_datetime(pd.DatetimeIndex(bdata['end_date']).round("1h"))#.dt.hour
        bdata['end hour'] = bdata['end hour'].dt.hour
        wbdata = pd.merge(bdata, weather, left_on='start datehour', right_on='dt', how='left')
        wbdata.to_csv(bfile)
    return wbdata


def load_weather(wfile='weather.csv', weather_files=[]):
    # Time is in local standard time, so not adjusted for DST
    #weather_cols = ['Temp', 'dt', 'Wind Dir (10s deg)', "Rel Hum (%)", "Weather"]

    weather_code_names = ['Clear/Cloudy', 'Drizzle/Fog', 'Rain', 'Snow', 'Thunderstorm', 'Freezing', "Ice"]
    if os.path.exists(wfile):
        print("Loading weather from saved file")
        weather = pd.read_csv(wfile)
    else:
        print("Creating Weather File")
        weather_cols = [u'dt', u'Year', u'Month', u'Day', u'Time', u'Data Quality',
           u'Temp', u'Temp Flag', u'Dew Point Temp (C)',
           u'Dew Point Temp Flag', u'Rel Hum (%)', u'Rel Hum Flag',
           u'Wind Dir (10s deg)', u'Wind Dir Flag', u'Wind Spd (km/h)',
           u'Wind Spd Flag', u'Visibility (km)', u'Visibility Flag',
           u'Stn Press (kPa)', u'Stn Press Flag', u'Hmdx', u'Hmdx Flag',
           u'Wind Chill', u'Wind Chill Flag', u'Weather', u'filename',
           u'w orig index']
        wlist = []
        for ww in weather_files:
            w = pd.read_csv(ww, skiprows=17, names=weather_cols)
            w['filename'] = os.path.split(ww)[1]
            w['w orig index'] = w.index
            wlist.append(w)
        weather = pd.concat(wlist)
        # Fill in where no observations were made
        weather["Weather Fill"] = weather["Weather"].fillna(method='ffill')
        weather["Weather Fill"] = weather["Weather Fill"].fillna(method='backfill')
        
        #weather.index = weather['dt']
        weather = weather[weather['Weather Fill']!='NaN']
        weather['dt'] = pd.to_datetime(weather['dt'])
        weather['Weather Date'] = weather['dt'].dt.date
        weather['Weather Time'] = weather['dt'].dt.time
        weather['Weather Hour'] = pd.DatetimeIndex(weather['dt']).round("1h")
        weather['Weather Hour'] = weather['Weather Hour'].dt.time
        weather['Weather Code'] = np.zeros(weather.shape[0])
        
        weather.loc[weather['Weather Fill'].str.contains('Drizzle'),'Weather Code'] = 1 
        weather.loc[weather['Weather Fill'].str.contains('Fog'),'Weather Code'] = 1
        weather.loc[weather['Weather Fill'].str.contains('Rain'),'Weather Code'] = 3
        weather.loc[weather['Weather Fill'].str.contains('Snow'),'Weather Code'] = 4
        weather.loc[weather['Weather Fill'].str.contains('Thunderstrom'),'Weather Code'] = 5
        weather.loc[weather['Weather Fill'].str.contains('Freezing'),'Weather Code'] = 6
        weather.loc[weather['Weather Fill'].str.contains('Ice'),'Weather Code'] = 6
        weather.to_csv(wfile)
    return weather, weather_code_names
  
