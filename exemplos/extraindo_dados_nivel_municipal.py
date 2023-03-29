import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import pandas as pd
import regionmask
import os
import geopandas as gpd
from joblib import Parallel, delayed
import rioxarray

# Extração dados MENSAIS de precipitação em nível municipal para o Brasil.
# Valor médio das células da grade que estão dentro do limite do município.
# Dependendo do computador, pode ser um pouco demorado,
# no meu demora ~15 min (Intel(R) Xeon(R) CPU E5-1650 v3 @ 3.50GHz; 12 processadores)
# Shape dos municípios obtidos em em:
# https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/15774-malhas.html?=&t=acesso-ao-produto
# Geometria dos municípios foi simplificada em: https://mapshaper.org/
# Arquivos shapes encontrados no diretório: /exemplos/shape_file/


def coletando_dados(n, mask, lon, lat, municipios_data_pandas):
    # print(n)
    sel_mask = mask.where(mask == n).values
    id_lon = lon[np.where(~np.all(np.isnan(sel_mask), axis=0))]
    if len(id_lon) >= 1:
        id_lat = lat[np.where(~np.all(np.isnan(sel_mask), axis=1))]
        out_sel = var_resample_extrapolado.sel(latitude=slice(id_lat[0], id_lat[-1]),
                                               longitude=slice(id_lon[0], id_lon[-1])).compute().where(mask == n)

        for k in range(out_sel.shape[0]):
            municipios_data_pandas[k] = np.nanmean(out_sel[k].values)

        # plt.figure(figsize=(12, 8))
        # ax = plt.axes()
        # out_sel.isel(time=0).plot(ax=ax)
        # municipios.plot(ax=ax, alpha=0.8, facecolor='none')
        # ax.axis(xmin=-64, xmax=-36, ymin=-32, ymax=-6)
        # plt.close("all")

    else:
        lon_municipios, lat_municipios = municipios_centroid_x[n], municipios_centroid_y[n]
        out_sel = var_resample_extrapolado.sel(latitude=lat_municipios,
                                               longitude=lon_municipios,
                                               method='nearest')
        municipios_data_pandas = out_sel.values

    return municipios_data_pandas


# escolhendo a variavel, neste caso precipitação ('Tmax', 'Tmin', 'Rs', 'RH', 'u2', 'pr')
nvar2get = 'pr'

# escala para amostragem "M" para mesal e "Y" para anual
time_scale = "M"

# caminho dos arquivos NetCDF da grade BR-DWGD
path_netcdf = '/home/alexandre/Dropbox/grade_2020/data/netcdf_files/'
var = xr.open_mfdataset(path_netcdf + nvar2get + '*.nc')[nvar2get]

# pegando o arquivo shape dos municipios
path = os.path.join(os.getcwd(), 'shape_file/BR_Municipios_2021.shp')
municipios = gpd.read_file(path)

# cetróides dos municípios para serem utilizados quando não há
# o município é muito pequeno e não tem célula da grade dentro.
# Vai pegar da célula mais próxima ao centroide do município
municipios_centroid_x = municipios.to_crs(epsg=5641).centroid.to_crs(municipios.crs).x.values
municipios_centroid_y = municipios.to_crs(epsg=5641).centroid.to_crs(municipios.crs).y.values

# mascara dos municípios
municipios_mask_poly = regionmask.Regions(name="municipios_mask",
                                          numbers=list(range(len(municipios))),
                                          names=list(municipios.CD_MUN),
                                          abbrevs=list(municipios.NM_MUN),
                                          outlines=list(municipios.geometry.values[i] for i in range(len(municipios))))

# mascara continente/mar
mask_ocean = 2 * np.ones(var.shape[1:]) * np.isnan(var.isel(time=0))
mask_land = 1 * np.ones(var.shape[1:]) * ~np.isnan(var.isel(time=0))
mask_array = (mask_ocean + mask_land).values

var.coords['mask'] = xr.DataArray(mask_array, dims=('latitude', 'longitude'))

# reamostrando para mensal (time="M"), para anual usar (time='Y')
var_resample = var.resample(time=time_scale).sum('time').where(var.mask == 1).compute()
# var_resample = var.resample(time=time_scale).mean('time').where(var.mask == 1).compute()

# Extrapolando, para que municípios que estão no limite do Brasil tenham dados.
var_resample.rio.write_nodata(np.nan, inplace=True)
var_resample.rio.write_crs("epsg:4326", inplace=True)
var_resample_extrapolado = var_resample.rio.interpolate_na()


mask_munic = municipios_mask_poly.mask(var_resample_extrapolado.isel(time=0),
                                       lat_name='latitude',
                                       lon_name='longitude')

municipios_data_pandas = np.empty((len(var_resample_extrapolado.time)))
lat = mask_munic.latitude.values
lon = mask_munic.longitude.values

# start = time.time()
# c = coletando_dados(n, mask_munic, lon, lat, municipios_data_pandas)
# print(time.time() - start)

saida = Parallel(n_jobs=-1, verbose=4)(delayed(coletando_dados)(n, mask_munic, lon, lat, municipios_data_pandas)
                                       for n in range(len(municipios.CD_MUN)))  # municipios_data_pandas.shape[0]

year = var_resample_extrapolado.time.dt.year.values
month = var_resample_extrapolado.time.dt.month.values
year_month = [f'{year[n]}-{month[n]}' for n in range(len(year))]
municipios_data = pd.DataFrame(np.empty((len(municipios.CD_MUN),
                                         len(var_resample_extrapolado.time)), dtype="int"),
                               columns=year_month,
                               index=municipios.index)

for n in range(len(municipios.CD_MUN)):
    municipios_data.iloc[n, :] = saida[n].astype("int")

# concatenado dados shape com dados da grade
municipios_data.set_index(municipios.index)
municipios = pd.concat((municipios, municipios_data), axis=1)

# gravando.Para shapefile: 'preci_muni_mensal.shp'
name2save = 'preci_muni_mensal.geojson'
municipios.to_file(name2save)

# plotando o mês de janeiro de 1961, extrapolado, e em nível municipal
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
time = '1961-01-31'
var_resample.sel(time=time).plot(ax=axes[0])
axes[0].set_title(f"prec ({time[:7]})")
var_resample_extrapolado.sel(time=time).plot(ax=axes[1])
axes[1].set_title(f"prec_extrap ({time[:7]})")
municipios.plot(ax=axes[2], column="1961-1")
axes[2].set_title("Prec municipal em " + "1961-1")
print("acabou")
