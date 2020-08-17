# Figures for IRF 2020 application

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from ..file_io import read_netcdf, netcdf_time
from ..timeseries import calc_annual_averages
from ..utils import moving_average, polar_stereo, select_bottom, bdry_from_hfac
from ..constants import deg_string
from ..plot_utils.windows import finished_plot, set_panels
from ..plot_utils.colours import set_colours
from ..interpolation import interp_reg_xy

def extract_geomip_westerlies ():

    directories = ['member1/', 'member4/', 'member8/']
    in_files = ['ssp245.nc', 'ssp585.nc', 'g6sulfur.nc', 'g6solar.nc']
    labels = ['low emissions', 'high emissions', 'high emissions + aerosol SRM', 'high emissions + space-based SRM']
    colours = ['black', 'red', 'blue', 'green']
    num_ens = len(directories)
    num_sim = len(in_files)

    times = []
    jet_lat_min = []
    jet_lat_max = []
    jet_lat_mean = []
    for fname in in_files:
        jet_lat_range = None
        for ens in range(num_ens):
            file_path = directories[ens] + fname
            time = netcdf_time(file_path)
            lat = read_netcdf(file_path, 'lat')        
            uas = np.mean(read_netcdf(file_path, 'uas'), axis=2)
            jet_jmax = np.argmax(uas, axis=1)
            jet_lat = np.empty(jet_jmax.shape)  
            for t in range(time.size):
                jet_lat[t] = lat[jet_jmax[t]]
            time, jet_lat = calc_annual_averages(time, jet_lat)
            jet_lat, time = moving_average(jet_lat, 5, time=time)
            if jet_lat_range is None:
                jet_lat_range = np.empty([num_ens, time.size])
            jet_lat_range[ens,:] = jet_lat
        times.append(np.array([t.year for t in time]))
        jet_lat_min.append(np.amin(jet_lat_range, axis=0))
        jet_lat_max.append(np.amax(jet_lat_range, axis=0))
        jet_lat_mean.append(np.mean(jet_lat_range, axis=0))

    fig, ax = plt.subplots()
    for n in range(num_sim):
        ax.fill_between(times[n], jet_lat_min[n], jet_lat_max[n], color=colours[n], alpha=0.15)
        ax.plot(times[n], jet_lat_mean[n], color=colours[n], label=labels[n], linewidth=1.5)
    plt.title('Impact of solar radiation management\non Southern Hemisphere westerly winds', fontsize=18)
    plt.xlabel('year', fontsize=14)
    plt.ylabel('jet latitude', fontsize=14)
    yticks = np.arange(-53, -50, 1)
    yticklabels = [np.str(-y)+deg_string+'S' for y in yticks]
    ax.set_yticks(yticks)
    ax.set_yticklabels(yticklabels)
    ax.set_xlim([times[-1][0], times[-1][-1]])
    ax.set_xticks(np.arange(2030, 2100, 20))
    #ax.legend()
    finished_plot(fig, fig_name='geo_winds.png', dpi=300)


# Plot Paul's SO bottom temps versus observations
def bottom_temp_vs_obs (model_file='stateBtemp_avg.nc', model_grid='grid.glob.nc', obs_file='schmidtko_data.txt'):

    # TODO
    # Continent shaded in grey

    # Set spatial bounds (60S at opposite corners)
    corner_lon = np.array([-45, 135])
    corner_lat = np.array([-60, -60])
    corner_x, corner_y = polar_stereo(corner_lon, corner_lat)
    [xmin, xmax, ymin, ymax] = [corner_x[0], corner_x[1], corner_y[1], corner_y[0]]
    # Set colour bounds
    vmin = -2
    vmax = 1.75
    lev = np.linspace(vmin, vmax, num=30)

    # Read model data
    model_lon = read_netcdf(model_file, 'LONGITUDE')
    model_lat = read_netcdf(model_file, 'LATITUDE')
    model_temp = read_netcdf(model_file, 'BTEMP')
    # Read other grid variables
    hfac = read_netcdf(model_grid, 'HFacC')
    z_edges = read_netcdf(model_grid, 'RF')
    bathy = bdry_from_hfac('bathy', hfac, z_edges)
    draft = bdry_from_hfac('draft', hfac, z_edges)
    # Mask out land, ice shelves, deep ocean
    mask = (bathy!=0)*(draft==0)*(bathy>-1500)
    model_temp = np.ma.masked_where(np.invert(mask), model_temp)
    # Convert coordinates to polar stereographic
    model_x, model_y = polar_stereo(model_lon, model_lat)

    # Read obs data
    obs = np.loadtxt(obs_file, dtype=np.str)
    obs_lon = obs[:,0].astype(float)
    obs_lat = obs[:,1].astype(float)
    obs_depth = obs[:,2].astype(float)
    obs_temp = obs[:,3].astype(float)
    # Interpolate to model grid
    obs_temp = interp_reg_xy(obs_lon, obs_lat, obs_temp, model_lon, model_lat)
    # Mask as before
    obs_temp = np.ma.masked_where(np.invert(mask), obs_temp)

    # Plot
    cmap = set_colours(model_temp, ctype='plusminus', vmin=vmin, vmax=vmax)[0]
    data = [model_temp, obs_temp]
    titles = ['a) Existing model', 'b) Observations']
    fig, gs = set_panels('1x2C0', figsize=(8,4))
    for n in range(2):
        ax = plt.subplot(gs[0,n])
        img = ax.contourf(model_x, model_y, data[n], lev, cmap=cmap, extend='both')
        ax.set_title(titles[n], fontsize=16)
        ax.axis('equal')
        ax.set_xlim([xmin, xmax])
        ax.set_ylim([ymin, ymax])
        ax.set_xticks([])
        ax.set_yticks([])
    cax = fig.add_axes([0.01, 0.3, 0.02, 0.4])
    cax.yaxis.set_label_position('left')
    cax.yaxis.set_ticks_position('left')
    cbar = plt.colorbar(img, cax=cax,ticks=np.arange(-2, 2, 1))
    cax.tick_params(length=2)
    plt.suptitle('Bottom temperatures ('+deg_string+'C)', fontsize=18)
    finished_plot(fig, fig_name='bwtemp_compare.png')
