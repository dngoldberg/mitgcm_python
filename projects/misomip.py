# Type "conda activate animations" before running the animation functions so you can access ffmpeg.
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os
import datetime

from ..grid import Grid
from ..plot_latlon import latlon_plot
from ..plot_1d import timeseries_multi_plot
from ..utils import str_is_int, real_dir, convert_ismr, mask_3d, mask_except_ice, mask_land, select_top, select_bottom
from ..constants import deg_string, sec_per_year
from ..file_io import read_netcdf
from ..plot_utils.windows import set_panels
from ..plot_utils.colours import get_extend
from ..postprocess import precompute_timeseries


# Helper function to get all the output directories, one per segment, in order.
def get_segment_dir (output_dir):

    segment_dir = []
    for name in os.listdir(output_dir):
        # Look for directories composed of numbers (date codes)
        if os.path.isdir(output_dir+name) and str_is_int(name):
            segment_dir.append(name)
    # Make sure in chronological order
    segment_dir.sort()
    return segment_dir


# Make animations of lat-lon variables (ismr, bwtemp, bwsalt, bdry_temp, bdry_salt, draft).
def animate_latlon (var, output_dir='./', file_name='output.nc', vmin=None, vmax=None, change_points=None, mov_name=None):

    output_dir = real_dir(output_dir)
    # Get all the directories, one per segment
    segment_dir = get_segment_dir(output_dir)

    # Inner function to read and process data from a single file
    def read_process_data (file_path, var_name, grid, mask_option='3d', gtype='t', lev_option=None, ismr=False):
        data = read_netcdf(file_path, var_name)
        if mask_option == '3d':
            data = mask_3d(data, grid, gtype=gtype, time_dependent=True)
        elif mask_option == 'except_ice':
            data = mask_except_ice(data, grid, gtype=gtype, time_dependent=True)
        elif mask_option == 'land':
            data = mask_land(data, grid, gtype=gtype, time_dependent=True)
        else:
            print 'Error (read_process_data): invalid mask_option ' + mask_option
            sys.exit()
        if lev_option is not None:
            if lev_option == 'top':
                data = select_top(data)
            elif lev_option == 'bottom':
                data = select_bottom(data)
            else:
                print 'Error (read_process_data): invalid lev_option ' + lev_option
                sys.exit()
        if ismr:
            data = convert_ismr(data)
        return data

    all_data = []
    all_grids = []
    # Loop over segments
    for sdir in segment_dir:
        # Construct the file name
        file_path = output_dir + sdir + '/MITgcm/' + file_name
        print 'Processing ' + file_path
        # Build the grid
        grid = Grid(file_path)
        # Read and process the variable we need
        ctype = 'basic'
        gtype = 't'
        if var == 'ismr':
            data = read_process_data(file_path, 'SHIfwFlx', grid, mask_option='except_ice', ismr=True)
            title = 'Ice shelf melt rate (m/y)'
            ctype = 'ismr'
        elif var == 'bwtemp':
            data = read_process_data(file_path, 'THETA', grid, lev_option='bottom')
            title = 'Bottom water temperature ('+deg_string+'C)'
        elif var == 'bwsalt':
            data = read_process_data(file_path, 'SALT', grid, lev_option='bottom')
            title = 'Bottom water salinity (psu)'
        elif var == 'bdry_temp':
            data = read_process_data(file_path, 'THETA', grid, lev_option='top')
            data = mask_except_ice(data, grid, time_dependent=True)
            title = 'Boundary layer temperature ('+deg_string+'C)'
        elif var == 'bdry_salt':
            data = read_process_data(file_path, 'SALT', grid, lev_option='top')
            data = mask_except_ice(data, grid, time_dependent=True)
            title = 'Boundary layer salinity (psu)'
        elif var == 'draft':
            data = mask_except_ice(grid.draft, grid)
            title = 'Ice shelf draft (m)'
        else:
            print 'Error (animate_latlon): invalid var ' + var
            sys.exit()
        # Loop over timesteps
        if var == 'draft':
            # Just one timestep
            all_data.append(data)
            all_grids.append(grid)
        else:
            for t in range(data.shape[0]):
                # Extract the data from this timestep
                # Save it and the grid to the long lists
                all_data.append(data[t,:])
                all_grids.append(grid)

    extend = get_extend(vmin=vmin, vmax=vmax)
    if vmin is None:
        vmin = np.amax(data)
        for elm in all_data:
            vmin = min(vmin, np.amin(elm))
    if vmax is None:
        vmax = np.amin(data)
        for elm in all_data:
            vmax = max(vmax, np.amax(elm))

    num_frames = len(all_data)

    # Make the initial figure
    fig, gs, cax = set_panels('MISO_C1')
    ax = plt.subplot(gs[0,0])
    img = latlon_plot(all_data[0], all_grids[0], ax=ax, gtype=gtype, ctype=ctype, vmin=vmin, vmax=vmax, change_points=change_points, title=title+', 1/'+str(num_frames), label_latlon=False, make_cbar=False)
    plt.colorbar(img, cax=cax, extend=extend)

    # Function to update figure with the given frame
    def animate(i):
        ax.cla()
        latlon_plot(all_data[i], all_grids[i], ax=ax, gtype=gtype, ctype=ctype, vmin=vmin, vmax=vmax, change_points=change_points, title=title+', '+str(i+1)+'/'+str(num_frames), label_latlon=False, make_cbar=False)

    # Call this for each frame
    anim = animation.FuncAnimation(fig, func=animate, frames=range(num_frames), interval=300)
    if mov_name is not None:
        print 'Saving ' + mov_name
        anim.save(mov_name)
    else:
        plt.show()


# Precompute timeseries for the given experiment.
def precompute_misomip_timeseries (output_dir='./', file_name='output.nc', timeseries_file='timeseries.nc', segment_dir=None):

    timeseries_types = ['avg_melt', 'all_massloss', 'ocean_vol', 'avg_temp', 'avg_salt']

    output_dir = real_dir(output_dir)
    if segment_dir is not None:
        # segment_dir is preset
        if isinstance(segment_dir, str):
            # Just one directory, so make it a list
            segment_dir = [segment_dir]
    else:
        # Get all the directories, one per segment
        segment_dir = get_segment_dir(output_dir)

    for sdir in segment_dir:
        file_path = output_dir+sdir+'/MITgcm/'+file_name
        print 'Processing ' + file_path
        precompute_timeseries(file_path, timeseries_file, timeseries_types=timeseries_types, monthly=False)


def compare_timeseries_jan (timeseries_file, jan_file, fig_dir='./'):

    fig_dir = real_dir(fig_dir)

    # Variable names in our files and in Jan's old file, plus titles, units, and conversion factors to apply to Jan's file to get the units we want
    var_names = ['avg_melt', 'all_massloss', 'ocean_vol', 'avg_temp', 'avg_salt']
    jan_names = ['meanMeltRate', 'totalMeltFlux', 'totalOceanVolume', 'meanTemperature', 'meanSalinity']
    titles = ['Mean ice shelf melte rate', 'Basal mass loss from all ice shelves', 'Volume of ocean in domain', 'Volume-averaged temperature', 'Volume-averaged salinity']
    units = ['m/y', 'Gt/y', r'm$^3$', deg_string+'C', 'psu']
    conversion = [sec_per_year, 1e-12*sec_per_year, 1, 1, 1]

    # Create the time array: first of each month for 100 years
    time = []
    for year in range(100):
        for month in range(12):
            time.append(datetime.date(year+1, month+1, 1))

    # Loop over variables
    for i in range(len(var_names)):
        data_new = read_netcdf(timeseries_file, var_names[i])
        data_old = read_netcdf(jan_file, jan_names[i])*conversion[i]
        timeseries_multi_plot(time, [data_old, data_new], ['MISOMIP_1r, old', 'MISOMIP_1r, new'], ['black', 'blue'], title=titles[i], units=units[i], fig_name=fig_dir+'jan_compare_'+var_names[i]+'.png')

    
