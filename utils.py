import numpy as np
import pandas as pd
from glob import glob
import os

def load_loc(name):
    l = pd.read_csv(name, encoding='utf-8')
    l['filename'] = os.path.split(name)[1]
    l['year'] = int((os.path.split(name)[1].split('.csv')[0].split('_'))[1])
    l.index = l['code']
    print('loaded %s station locations from:%s' %(name, l.shape[0]))
    return l

def load_stats(station_location_files=[], sfile='stations.csv', shp_file='../geo/limadmin-shp/LIMADMIN.shp'):
    if os.path.exists(sfile):
        print("Loading station infromation from saved file")
        blocs = pd.read_csv(sfile)
    else:
        print("Creating station information file with relevant information")
        import geocoder
        import geopandas as gpd
        import LatLon
        from unidecode import unidecode
        from shapely.geometry import Point
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
            t=unidecode(bl)
            t.encode("ascii")  #works fine, because all non-ASCII from s are replaced with their equivalents
            nbl.append(t) 
        blocs['name fmt'] = nbl
        # remove names which are not easily written to file
        del blocs['name']
        blocs.index = blocs['code']
        # read shape file of region
        mtlbr = gpd.read_file(shp_file)

        pps = [Point(pt) for pt in zip(blocs['longitude'], blocs['latitude'])]
        nns = []
        for pp in pps:
            shp_indx = np.argmax(mtlbr['geometry'].contains(pp))
            nns.append(shp_indx)
            
        blocs['neighborhood code'] = nns
        nnames = np.array(mtlbr.loc[nns,'NOM'].map(lambda x: unidecode(x).encode('ascii')))
        blocs['neighborhood'] = nnames

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
    month = '*' #'05'
    data_base_path = 'data'
    bicycle_files = glob(os.path.join(data_base_path, 'bikes', "BixiMontrealRentals%s/OD_%s-%s.csv"%(year,year,month)))
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

def load_bike_files(blocs, weather, bfile='bike_all.csv', sfile='stations.csv', bike_files=[]):
    if os.path.exists(bfile):
        print("Loading bikes with weather from saved file")
        wbdata = pd.read_csv(bfile)
    else:
        print("Creating merged bike file with weather, this may take some time")
        from workalendar import canada
        from workalendar import usa
        blist = []
        for bb in bike_files:
            blist.append(load_bike(bb))
        bdata = pd.concat(blist)
        bdata['all index'] = np.arange(bdata.shape[0])
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
        print("Adding start/end station information")
        codes = blocs['code'].unique()
        blocs.index = blocs['code']
        bdata['start_lat'] = np.zeros(bdata.shape[0])
        bdata['start_lon'] = np.zeros(bdata.shape[0])
        bdata['end_lat'] = np.zeros(bdata.shape[0])
        bdata['end_lon'] = np.zeros(bdata.shape[0])
        bdata['end_station_name'] = np.zeros(bdata.shape[0])
        bdata['start_station_name'] = np.zeros(bdata.shape[0])
        bdata['start_station_elev'] = np.zeros(bdata.shape[0])
        bdata['end_station_elev'] = np.zeros(bdata.shape[0])
        # init location with count data
        blocs['start_events_member'] = np.zeros(blocs.shape[0])
        blocs['start_events_casual'] = np.zeros(blocs.shape[0])
        blocs['end_events_member'] = np.zeros(blocs.shape[0])
        blocs['end_events_casual'] = np.zeros(blocs.shape[0])
        blocs['start_events'] = np.zeros(blocs.shape[0])
        blocs['end_events'] = np.zeros(blocs.shape[0])

        for code in codes:
            station_name = str(blocs[blocs.loc[:,'code']==code]['name fmt'])
            station_lat =  float(blocs[blocs.loc[:,'code']==code]['latitude'])
            station_lon = float(blocs[blocs.loc[:,'code']==code]['longitude'])
            station_elev = float(blocs[blocs.loc[:,'code']==code]['elev'])
            print('working on code: %s: %s, (%s, %s, %s)' %(code, station_name, 
                                      station_lat, station_lon, station_elev))
            _start = bdata['start_station_code']==code
            num_start_stat = np.sum(_start)
            if num_start_stat:
                num_start_mem = np.sum(bdata.loc[_start,'is_member'])
                bdata.loc[_start, 'start_station_name'] = station_name 
                bdata.loc[_start, 'start_station_elev'] = station_elev
                bdata.loc[_start, 'start_lat'] = station_lat
                bdata.loc[_start, 'start_lon'] = station_lon
                blocs.loc[code, 'start_events'] = num_start_stat
                blocs.loc[code, 'start_events_member'] = num_start_mem
                blocs.loc[code, 'start_events_casual'] = num_start_stat-num_start_mem
            _end = bdata['end_station_code']==code
            num_end_stat = np.sum(_end)
            if num_end_stat:
                num_end_mem = np.sum(bdata.loc[_end,'is_member'])
                bdata.loc[_end,  'end_station_name'] = station_name
                bdata.loc[_end, 'end_station_elev'] = station_elev
                bdata.loc[_end, 'end_lat'] = station_lat
                bdata.loc[_end, 'end_lon'] = station_lon
                blocs.loc[code, 'end_events'] = num_end_stat
                blocs.loc[code, 'end_events_member'] = num_end_mem
                blocs.loc[code, 'end_events_casual'] = num_end_stat-num_end_mem
            #from IPython import embed; embed()
     
        blocs.to_csv(sfile)
        bdata['elev change'] = bdata['start_station_elev'] - bdata['end_station_elev']
        print("merging weather information")
        # for simplicity, find nearest hour of rack event
        bdata['start hour'] = pd.to_datetime(pd.DatetimeIndex(bdata['start_date']).round("1h"))#.dt.hour
        bdata['start hour'] = bdata['start hour'].dt.hour
        bdata['start datehour'] = pd.DatetimeIndex(bdata['start_date']).round("1h")
        bdata['end hour'] = pd.to_datetime(pd.DatetimeIndex(bdata['end_date']).round("1h"))#.dt.hour
        bdata['end hour'] = bdata['end hour'].dt.hour
        weather['weather start datehour'] = pd.DatetimeIndex(weather['dt']).round("1h")
        wbdata = pd.merge(bdata, weather, left_on='start datehour', right_on='weather start datehour', how='left')
        print("Writing bike data to file")
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
        weather.loc[weather['Weather Fill'].str.contains('Rain'),'Weather Code'] = 2 
        weather.loc[weather['Weather Fill'].str.contains('Snow'),'Weather Code'] =3 
        weather.loc[weather['Weather Fill'].str.contains('Thunderstrom'),'Weather Code'] = 4
        weather.loc[weather['Weather Fill'].str.contains('Freezing'),'Weather Code'] = 5
        weather.loc[weather['Weather Fill'].str.contains('Ice'),'Weather Code'] = 6
        weather.to_csv(wfile)
    return weather, weather_code_names
if __name__ == '__main__':
    load_default()
