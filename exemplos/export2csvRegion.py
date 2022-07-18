import numpy as np
import xarray as xr
import pandas as pd
import time

"""
Exportando dados de todas as variaveis para uma regiao.
"""

# periodo para ser exportado
date_start, date_end = '1985-01-01', '2020-07-31'

# limits of the area
lat_min, lat_max = -12.64, -12.25
lon_min, lon_max = -38.96, -38.59

# variables names
var_names = ['Rs', 'u2','Tmax', 'Tmin', 'RH', 'pr', 'ETo']

# set correct path of the netcdf files
path_var = '/home/alexandre/Dropbox/grade_2020/data/netcdf_files/'

# latitude and longitude of GRID
var = xr.open_mfdataset(path_var + 'pr*.nc')
latitude = var.latitude.values
longitude = var.longitude.values

lat = latitude[np.array(np.nonzero((latitude >= lat_min) &
                                  (latitude <= lat_max))).flatten()]
lon = longitude[np.array(np.nonzero((longitude >= lon_min) &
                                  (longitude <= lon_max))).flatten()]

lon, lat = np.meshgrid(lon, lat)
lon, lat = lon.flatten(), lat.flatten()

# function to read the netcdf files
def rawData(var2get_xr, var_name2get):
    return var2get_xr[var_name2get].loc[dict(time=slice(date_start, date_end))].sel(longitude=xr.DataArray(lon, dims='z'),
                                          latitude=xr.DataArray(lat, dims='z'),
                                          method='nearest').values

# getting data from NetCDF files
for n, var_name2get in enumerate(var_names):
    print(n)
    var2get_xr = xr.open_mfdataset(path_var + var_name2get + '*.nc').chunk(chunks={"time": 400})
    if n == 0:
        var_ar = rawData(var2get_xr, var_name2get)
        n_lines = var_ar.shape[0]
        time = var2get_xr.loc[dict(time=slice(date_start, date_end))].time.values
    else:
        var_ar = np.c_[var_ar, rawData(var2get_xr, var_name2get)]

# saving
for n in range(len(lat)):
    print('arquivo {} de um total de {}'.format(n+1, len(lat)))
    name_file = 'lat{:.2f}_lon{:.2f}.csv'.format(lat[n], lon[n])
    print(name_file)
    if ~np.isnan(var_ar[0, n]):
        file = var_ar[:, n::len(lon)]
        pd.DataFrame(file, index=time, columns=var_names).to_csv(name_file, float_format='%.1f')