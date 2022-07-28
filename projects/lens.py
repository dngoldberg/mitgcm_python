##################################################################
# JSPS Amundsen Sea simulations forced with LENS
##################################################################

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import os
from scipy.stats import linregress, ttest_1samp
from scipy.ndimage.filters import gaussian_filter
import datetime

from ..plot_1d import read_plot_timeseries_ensemble
from ..plot_latlon import latlon_plot
from ..plot_slices import make_slice_plot
from ..utils import real_dir, fix_lon_range, add_time_dim, days_per_month, xy_to_xyz, z_to_xyz, index_year_start, var_min_max, polar_stereo
from ..grid import Grid, read_pop_grid, read_cice_grid
from ..ics_obcs import find_obcs_boundary, trim_slice_to_grid, trim_slice, get_hfac_bdry, read_correct_cesm_ts_space
from ..file_io import read_netcdf, read_binary, netcdf_time, write_binary, find_cesm_file
from ..constants import deg_string, months_per_year, Tf_ref, region_names, Cp_sw, rhoConst
from ..plot_utils.windows import set_panels, finished_plot
from ..plot_utils.colours import set_colours, get_extend
from ..plot_utils.labels import reduce_cbar_labels, lon_label
from ..plot_utils.slices import slice_patches, slice_values
from ..plot_utils.latlon import overlay_vectors, shade_land, contour_iceshelf_front
from ..plot_misc import ts_binning, hovmoller_plot
from ..interpolation import interp_slice_helper, interp_slice_helper_nonreg, extract_slice_nonreg, interp_bdry, fill_into_mask, distance_weighted_nearest_neighbours, interp_to_depth, interp_grid
from ..postprocess import precompute_timeseries_coupled, make_trend_file
from ..diagnostics import potential_density
from ..make_domain import latlon_points


# Update the timeseries calculations from wherever they left off before.
def update_lens_timeseries (num_ens=5, base_dir='./', sim_dir=None):

    timeseries_types = ['amundsen_shelf_break_uwind_avg', 'all_massloss', 'amundsen_shelf_temp_btw_200_700m', 'amundsen_shelf_salt_btw_200_700m', 'amundsen_shelf_sst_avg', 'amundsen_shelf_sss_avg', 'dotson_to_cosgrove_massloss', 'amundsen_shelf_isotherm_0.5C_below_100m']
    base_dir = real_dir(base_dir)
    if sim_dir is None:
        sim_dir = [base_dir + 'PAS_LENS' + str(n+1).zfill(3) + '_O/output/' for n in range(num_ens)]
    else:
        num_ens = len(sim_dir)
    timeseries_file = 'timeseries.nc'

    for n in range(num_ens):
        if not os.path.isfile(sim_dir[n]+timeseries_file):
            # Start fresh
            segment_dir = None
        else:
            # Work out the first year based on where the timeseries file left off
            start_year = netcdf_time(sim_dir[n]+timeseries_file, monthly=False)[-1].year+1
            # Work on the last year based on the contents of the output directory
            sim_years = []
            for fname in os.listdir(sim_dir[n]):
                if os.path.isdir(sim_dir[n]+fname) and fname.endswith('01'):
                    sim_years.append(int(fname))
            sim_years.sort()
            end_year = sim_years[-1]//100
            print('Processing years '+str(start_year)+'-'+str(end_year))
            segment_dir = [str(year)+'01' for year in range(start_year, end_year+1)]
        precompute_timeseries_coupled(output_dir=sim_dir[n], segment_dir=segment_dir, timeseries_types=timeseries_types, hovmoller_loc=[], timeseries_file=timeseries_file, key='PAS')        


# Plot a bunch of precomputed timeseries from ongoing LENS-forced test simulations (ensemble of 5 to start), compared to the PACE-forced ensemble mean.
def check_lens_timeseries (num_ens=5, base_dir='./', fig_dir=None, sim_dir=None, finished=False):

    var_names = ['amundsen_shelf_break_uwind_avg', 'all_massloss', 'amundsen_shelf_temp_btw_200_700m', 'amundsen_shelf_salt_btw_200_700m', 'amundsen_shelf_sst_avg', 'amundsen_shelf_sss_avg', 'dotson_to_cosgrove_massloss', 'amundsen_shelf_isotherm_0.5C_below_100m']
    base_dir = real_dir(base_dir)
    pace_file = base_dir+'timeseries_pace_mean.nc'
    if sim_dir is None:
        sim_dir = ['PAS_LENS'+str(n+1).zfill(3)+'_O/output/' for n in range(num_ens)]
    else:
        num_ens = len(sim_dir)
    file_paths = [pace_file] + [sd+'timeseries.nc' for sd in sim_dir]
    sim_names = ['PACE mean'] + ['LENS ensemble'] + [None for n in range(num_ens-1)]
    colours = ['blue'] + ['DarkGrey' for n in range(num_ens)]
    smooth = 24
    start_year = 1920

    for var in var_names:
        if fig_dir is not None:
            fig_name = real_dir(fig_dir) + 'timeseries_LENS_' + var + '.png'
        else:
            fig_name=None
        read_plot_timeseries_ensemble(var, file_paths, sim_names=sim_names, precomputed=True, colours=colours, smooth=smooth, vline=start_year, time_use=None, fig_name=fig_name, plot_mean=finished, first_in_mean=False)


# As above, but multiple ensembles for different scenarios.
def check_scenario_timeseries (base_dir='./', num_LENS=5, num_MENS=1, num_LW2=1, num_LW1=1, fig_dir=None):

    var_names = ['amundsen_shelf_break_uwind_avg', 'all_massloss', 'amundsen_shelf_temp_btw_200_700m', 'amundsen_shelf_salt_btw_200_700m', 'amundsen_shelf_sst_avg', 'amundsen_shelf_sss_avg', 'dotson_to_cosgrove_massloss', 'amundsen_shelf_isotherm_0.5C_below_100m']
    base_dir = real_dir(base_dir)
    pace_file = base_dir+'timeseries_pace_mean.nc'
    smooth = 24
    start_year = 1920

    sim_dir = ['PAS_LENS'+str(n+1).zfill(3)+'_O/' for n in range(num_LENS)] + ['PAS_MENS_'+str(n+1).zfill(3)+'_O/' for n in range(num_MENS)] + ['PAS_LW2.0_'+str(n+1).zfill(3)+'_O/' for n in range(num_LW2)] + ['PAS_LW1.5_'+str(n+1).zfill(3)+'_O/' for n in range(num_LW1)]
    file_paths = [sd+'output/timeseries.nc' for sd in sim_dir] + [pace_file]
    sim_names = []
    for scenario, num_scenario in zip(['LENS', 'MENS', 'LW2.0', 'LW1.5'], [num_LENS, num_MENS, num_LW2, num_LW1]):
        if num_scenario > 0:
            sim_names += [scenario]
            if num_scenario > 1:
                sim_names += [None for n in range(num_scenario-1)]
    sim_names += ['PACE mean']
    colours = ['black' for n in range(num_LENS)] + ['red' for n in range(num_MENS)] + ['green' for n in range(num_LW2)] + ['blue' for n in range(num_LW1)] + ['magenta']

    for var in var_names:
        if fig_dir is not None:
            fig_name = real_dir(fig_dir) + 'timeseries_scenario_' + var + '.png'
        else:
            fig_name = None
        read_plot_timeseries_ensemble(var, file_paths, sim_names=sim_names, precomputed=True, colours=colours, smooth=smooth, vline=start_year, time_use=None, fig_name=fig_name)

    
 

# Compare time-averaged temperature and salinity boundary conditions from PACE over 2006-2013 (equivalent to the first 20 ensemble members of LENS actually!) to the WOA boundary conditions used for the original simulations.
def compare_bcs_ts_mean (fig_dir='./'):

    # Bunch of file paths
    base_dir = '/data/oceans_output/shelf/kaight/'
    grid_dir = base_dir + 'mitgcm/PAS_grid/'
    obcs_dir = base_dir + 'ics_obcs/PAS/'
    obcs_file_head = 'OB'
    obcs_file_tail = '_woa_mon.bin'
    obcs_var = ['theta', 'salt']
    obcs_bdry = ['N', 'W', 'E']
    pace_dir = '/data/oceans_input/raw_input_data/CESM/PPACE/monthly/'
    pace_var = ['TEMP', 'SALT']
    num_ens = 20
    pace_file_head = '/b.e11.BRCP85LENS.f09_g16.SST.restoring.ens'
    pace_file_mid = '.pop.h.'
    pace_file_tail = '.200601-201312.nc'
    num_var = len(pace_var)
    var_titles = ['Temperature ('+deg_string+'C)', 'Salinity (psu)']
    fig_dir = real_dir(fig_dir)
    
    # Build the grids
    mit_grid = Grid(grid_dir)    
    pace_grid_file = pace_dir + pace_var[0] + pace_file_head + '01' + pace_file_mid + pace_var[0] + pace_file_tail
    pace_lon, pace_lat, pace_z, pace_nx, pace_ny, pace_nz = read_pop_grid(pace_grid_file)

    # Read the PACE output to create a time-mean, ensemble-mean (no seasonal cycle for now)
    pace_data_mean_3d = np.ma.zeros([num_var, pace_nz, pace_ny, pace_nx])
    for v in range(num_var):
        for n in range(num_ens):
            pace_file = pace_dir + pace_var[v] + pace_file_head + str(n+1).zfill(2) + pace_file_mid + pace_var[v] + pace_file_tail
            print('Reading ' + pace_file)
            pace_data_mean_3d[v,:] += read_netcdf(pace_file, pace_var[v], time_average=True)
    # Convert from ensemble-integral to ensemble-mean
    pace_data_mean_3d /= num_ens

    # Now loop over boundaries
    for bdry in obcs_bdry:
        # Find the location of this boundary (lat/lon)
        loc0 = find_obcs_boundary(mit_grid, bdry)[0]
        # Find interpolation coefficients to the PACE grid - unfortunately not a regular grid in POP
        if bdry in ['N', 'S']:
            direction = 'lat'
            mit_h = mit_grid.lon_1d
            pace_h_2d = pace_lon
        elif bdry in ['E', 'W']:
            direction = 'lon'
            mit_h = mit_grid.lat_1d
            pace_h_2d = pace_lat
        i1, i2, c1, c2 = interp_slice_helper_nonreg(pace_lon, pace_lat, loc0, direction)
        for v in range(num_var):
            # Read and time-average the existing (WOA) boundary condition file
            obcs_file = obcs_dir + obcs_file_head + bdry + obcs_var[v] + obcs_file_tail
            if bdry in ['N', 'S']:
                dimensions = 'xzt'
            elif bdry in ['E', 'W']:
                dimensions = 'yzt'
            obcs_data_mean = np.mean(read_binary(obcs_file, [mit_grid.nx, mit_grid.ny, mit_grid.nz], dimensions), axis=0)
            # Apply land mask
            bdry_hfac = get_hfac_bdry(mit_grid, bdry)
            obcs_data_mean = np.ma.masked_where(bdry_hfac==0, obcs_data_mean)
            # Interpolate to the PACE grid
            pace_data_mean = extract_slice_nonreg(pace_data_mean_3d, direction, i1, i2, c1, c2)
            pace_h = extract_slice_nonreg(pace_h_2d, direction, i1, i2, c1, c2)
            # Trim
            pace_data_mean, pace_h = trim_slice_to_grid(pace_data_mean, pace_h, mit_grid, direction)
            # Find bounds for colour scale
            vmin = min(np.amin(obcs_data_mean), np.amin(pace_data_mean))
            vmax = max(np.amax(obcs_data_mean), np.amax(pace_data_mean))
            # Plot
            fig, gs, cax = set_panels('1x2C1')
            # WOA OBCS
            ax = plt.subplot(gs[0,0])
            ax.pcolormesh(mit_h, mit_grid.z*1e-3, obcs_data_mean, cmap='jet', vmin=vmin, vmax=vmax)
            ax.set_title('WOA 2018', fontsize=14)
            # PACE
            ax = plt.subplot(gs[0,1])
            img = plt.pcolormesh(pace_h, pace_z*1e-3, pace_data_mean, cmap='jet', vmin=vmin, vmax=vmax)
            ax.set_title('LENS 20-member mean', fontsize=14)
            plt.colorbar(img, cax=cax, orientation='horizontal')
            plt.suptitle(var_titles[v]+', '+bdry+' boundary', fontsize=16)
            finished_plot(fig, fig_name=fig_dir+'pace_obcs_'+pace_var[v]+'_'+str(bdry)+'.png')


# Calculate a monthly climatology of each variable from the LENS simulations of CESM over each boundary.
def calc_lens_climatology (out_dir='./'):

    out_dir = real_dir(out_dir)
    var_names = ['TEMP', 'SALT', 'UVEL', 'VVEL', 'aice', 'hi', 'hs', 'uvel', 'vvel']
    gtype = ['t', 't', 'u', 'v', 't', 't', 't', 'u', 'v']
    domain = ['oce', 'oce', 'oce', 'oce', 'ice', 'ice', 'ice', 'ice', 'ice']
    num_var = len(var_names)
    start_year = 1998
    end_year = 2017
    num_years = end_year - start_year + 1
    num_ens = 40
    mit_grid_dir = '/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/'
    bdry_loc = ['N', 'W', 'E']
    num_var = len(var_names)
    out_file_head = 'LENS_climatology_'
    out_file_tail = '_'+str(start_year)+'-'+str(end_year)

    # Read/generate grids
    pop_grid_file = find_cesm_file('LENS', var_names[0], 'oce', 'monthly', 1, start_year)[0]
    pop_tlon, pop_tlat, pop_ulon, pop_ulat, pop_z_1d, pop_nx, pop_ny, nz = read_pop_grid(pop_grid_file, return_ugrid=True)
    cice_grid_file = find_cesm_file('LENS', var_names[-1], 'ice', 'monthly', 1, start_year)[0]
    cice_tlon, cice_tlat, cice_ulon, cice_ulat, cice_nx, cice_ny = read_cice_grid(cice_grid_file, return_ugrid=True)
    mit_grid = Grid(mit_grid_dir)

    for bdry in bdry_loc:
        for v in range(2, num_var):  # Skip T and S for now because calculated those earlier
            print('Processing '+var_names[v]+' on '+bdry+' boundary')
            loc0_centre, loc0_edge = find_obcs_boundary(mit_grid, bdry)
            if (bdry in ['N', 'S'] and gtype[v] == 'v') or (bdry in ['E', 'W'] and gtype[v] == 'u'):
                loc0 = loc0_edge
            else:
                loc0 = loc0_centre
            if domain[v] == 'oce':
                if gtype[v] == 't':
                    lon = pop_tlon
                    lat = pop_tlat
                else:
                    lon = pop_ulon
                    lat = pop_ulat
            else:
                if gtype[v] == 't':
                    lon = cice_tlon
                    lat = cice_tlat
                else:
                    lon = cice_ulon
                    lat = cice_tlat
            if bdry in ['N', 'S']:
                direction = 'lat'
                h_2d = lon
            elif bdry in ['E', 'W']:
                direction = 'lon'
                h_2d = lat
            i1, i2, c1, c2 = interp_slice_helper_nonreg(lon, lat, loc0, direction)
            h_full = extract_slice_nonreg(h_2d, direction, i1, i2, c1, c2)
            h = trim_slice_to_grid(h_full, h_full, mit_grid, direction)[0]
            nh = h.size
            # Set up array for monthly climatology
            if domain[v] == 'oce':
                shape = [months_per_year, nz, nh]
            else:
                shape = [months_per_year, nh]
            lens_clim = np.ma.zeros(shape)
            # Loop over ensemble members and time indices
            for n in range(num_ens):
                print('Processing ensemble member '+str(n+1))
                for year in range(start_year, end_year+1):
                    print('...'+str(year))
                    for month in range(months_per_year):
                        file_path, t0_year, tf_year = find_cesm_file('LENS', var_names[v], domain[v], 'monthly', n+1, year)
                        t0 = t0_year+month
                        data_3d = read_netcdf(file_path, var_names[v], t_start=t0, t_end=t0+1)
                        if var_names[v] in ['UVEL', 'VVEL', 'uvel', 'vvel', 'aice']:
                            # Convert from cm/s to m/s, or percent to fraction
                            data_3d *= 1e-2
                        data_slice = extract_slice_nonreg(data_3d, direction, i1, i2, c1, c2)
                        data_slice = trim_slice_to_grid(data_slice, h_full, mit_grid, direction, warn=False)[0]
                        lens_clim[month,:] += data_slice
            # Convert from integral to average
            lens_clim /= (num_ens*num_years)
            # Save to binary file
            write_binary(lens_clim, out_dir+out_file_head+var_names[v]+'_'+bdry+out_file_tail)


# Calculate bias correction files for each boundary condition, based on the LENS ensemble mean climatology compared to the WOA/SOSE fields we used previously.
def make_lens_bias_correction_files (out_dir='./'):

    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'mitgcm/PAS_grid/'
    lens_dir = base_dir + 'CESM_bias_correction/obcs/'
    obcs_dir = base_dir + 'ics_obcs/PAS/'
    bdry_loc = ['N', 'W', 'E']
    var_obcs_oce = ['theta_woa_mon', 'salt_woa_mon', 'uvel_sose', 'vvel_sose']
    var_obcs_ice = ['area_sose', 'heff_sose', 'hsnow_sose', 'uice_sose', 'vice_sose']
    obcs_gtype_oce = ['t', 't', 'u', 'v']
    obcs_gtype_ice = ['t', 't', 't', 'u', 'v']
    obcs_file_head = obcs_dir + 'OB'
    obcs_file_tail = '.bin'
    var_lens_oce = ['TEMP', 'SALT', 'UVEL', 'VVEL']
    var_lens_ice = ['aice', 'hi', 'hs', 'uvel', 'vvel']
    num_var_oce = len(var_lens_oce)
    num_var_ice = len(var_lens_ice)
    lens_gtype_oce = ['t', 't', 'u', 'u']
    lens_gtype_ice = ['t', 't', 't', 'u', 'u']
    lens_file_head = lens_dir + 'LENS_climatology_'
    lens_file_tail = '_2013-2017.nc'
    out_dir = real_dir(out_dir)

    # Read the grids
    mit_grid = Grid(mit_grid_dir)
    oce_grid_file = lens_file_head + var_lens_oce[0] + lens_file_tail
    oce_tlat = read_netcdf(oce_grid_file, 'TLAT')
    oce_tlon = fix_lon_range(read_netcdf(oce_grid_file, 'TLONG'))
    oce_ulat = read_netcdf(oce_grid_file, 'ULAT')
    oce_ulon = fix_lon_range(read_netcdf(oce_grid_file, 'ULONG'))
    oce_z = -1*read_netcdf(oce_grid_file, 'z_t')*1e-2
    oce_nx = oce_tlon.shape[1]
    oce_ny = oce_tlat.shape[0]
    oce_nz = oce_z.size
    ice_grid_file = lens_file_head + var_lens_ice[0] + lens_file_tail
    ice_tlat = read_netcdf(ice_grid_file, 'TLAT')
    ice_tlon = fix_lon_range(read_netcdf(ice_grid_file, 'TLON'))
    ice_ulat = read_netcdf(ice_grid_file, 'ULAT')
    ice_ulon = fix_lon_range(read_netcdf(ice_grid_file, 'ULON'))
    ice_nx = ice_tlon.shape[1]
    ice_ny = ice_tlat.shape[0]

    # Loop over boundaries
    for bdry in bdry_loc:
        # Find the location of this boundary (lat/lon)
        loc0_centre, loc0_edge = find_obcs_boundary(mit_grid, bdry)
        # Loop over domains (ocean + ice)
        for var_obcs, obcs_gtype, var_lens, lens_gtype, tlat, tlon, ulat, ulon, nx, ny, num_var, oce in zip([var_obcs_oce, var_obcs_ice], [obcs_gtype_oce, obcs_gtype_ice], [var_lens_oce, var_lens_ice], [lens_gtype_oce, lens_gtype_ice], [oce_tlat, ice_tlat], [oce_tlon, ice_tlon], [oce_ulat, ice_ulat], [oce_ulon, ice_ulon], [oce_nx, ice_nx], [oce_ny, ice_ny], [num_var_oce, num_var_ice], [True, False]):
            # Loop over variables
            for v in range(num_var):
                print('Processing ' + var_lens[v] + ' on ' + bdry + ' boundary')
                
                # Read the data from LENS and OBCS
                lens_file = lens_file_head + var_lens[v] + lens_file_tail
                lens_clim = read_netcdf(lens_file, var_lens[v])
                obcs_file = obcs_file_head + bdry + var_obcs[v] + obcs_file_tail
                if bdry in ['N', 'S']:
                    dimensions = 'x'
                elif bdry in ['E', 'W']:
                    dimensions = 'y'
                if oce:
                    dimensions += 'z'
                dimensions += 't'
                obcs_clim_bdry = read_binary(obcs_file, [mit_grid.nx, mit_grid.ny, mit_grid.nz], dimensions)
                    
                # Select the correct grid type in LENS
                if lens_gtype[v] == 't':
                    lens_lat = tlat
                    lens_lon = tlon
                elif lens_gtype[v] == 'u':
                    lens_lat = ulat
                    lens_lon = ulon
                # Select the correct boundary location in MITgcm
                if bdry in ['N', 'S'] and obcs_gtype[v] == 'v':
                    loc0 = loc0_edge
                elif bdry in ['E', 'W'] and obcs_gtype[v] == 'u':
                    loc0 = loc0_edge
                else:
                    loc0 = loc0_centre
                mit_lon, mit_lat = mit_grid.get_lon_lat(gtype=obcs_gtype[v], dim=1)
                mit_hfac = get_hfac_bdry(mit_grid, bdry, gtype=obcs_gtype[v])
                if not oce:
                    mit_hfac = mit_hfac[0,:]
                if bdry in ['N', 'S']:
                    lens_h_2d = lens_lon
                    mit_n = mit_grid.nx
                    mit_h = mit_lon
                    direction = 'lat'
                elif bdry in ['E', 'W']:
                    lens_h_2d = lens_lat
                    mit_n = mit_grid.ny
                    mit_h = mit_lat
                    direction = 'lon'
                
                # Calculate interpolation coefficients to select this boundary in LENS
                i1, i2, c1, c2 = interp_slice_helper_nonreg(lens_lon, lens_lat, loc0, direction)
                # Now select the boundary in LENS
                lens_clim_bdry = extract_slice_nonreg(lens_clim, direction, i1, i2, c1, c2)
                lens_h = extract_slice_nonreg(lens_h_2d, direction, i1, i2, c1, c2)
                if direction == 'lon' and oce:
                    # Throw away the northern hemisphere because the tripolar? grid causes interpolation issues
                    lens_clim_bdry, lens_h = trim_slice(lens_clim_bdry, lens_h, hmax=0, lon=True)

                # Now interpolate this slice of LENS data to the MITgcm grid on the boundary, one month at a time.
                shape = [months_per_year]
                if oce:
                    shape += [mit_grid.nz]
                shape += [mit_n]
                lens_clim_bdry_interp = np.zeros(shape)
                for t in range(months_per_year):
                    print('...interpolating month '+str(t+1)+' of '+str(months_per_year))
                    lens_clim_bdry_interp[t,:] = interp_bdry(lens_h, oce_z, lens_clim_bdry[t,:], np.invert(lens_clim_bdry[t,:].mask).astype(float), mit_h, mit_grid.z, mit_hfac, lon=(bdry in ['N', 'S']), depth_dependent=oce)
                    
                # Now get the bias correction
                lens_offset = obcs_clim_bdry - lens_clim_bdry_interp
                # Save to file
                out_file = out_dir + 'LENS_offset_' + var_lens[v] + '_' + bdry
                write_binary(lens_offset, out_file)


# Plot the LENS bias corrections for OBCS at all three boundaries with annual mean, for each variable.
def plot_lens_obcs_bias_corrections_annual (fig_dir=None):

    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'mitgcm/PAS_grid/'
    in_dir = base_dir + 'CESM_bias_correction/obcs/'
    bdry_loc = ['N', 'W', 'E']
    oce_var = ['TEMP', 'SALT', 'UVEL', 'VVEL']
    ice_var = ['aice', 'hi', 'hs', 'uvel', 'vvel']
    gtype_oce = ['t', 't', 'u', 'v']
    gtype_ice = ['t', 't', 't', 'u', 'v']
    oce_titles = ['Temperature ('+deg_string+'C)', 'Salinity (psu)', 'Zonal velocity (m/s)', 'Meridional velocity (m/s)']
    ice_titles = ['Sea ice concentration', 'Sea ice thickness (m)', 'Snow thickness (m)', 'Sea ice zonal velocity (m/s)', 'Sea ice meridional velocity (m/s)']
    file_head = in_dir + 'LENS_offset_'
    bdry_patches = [None, None, None]
    num_bdry = len(bdry_loc)

    grid = Grid(mit_grid_dir)

    # Loop over ocean and ice variables
    for var_names, gtype, titles, oce in zip([oce_var, ice_var], [gtype_oce, gtype_ice], [oce_titles, ice_titles], [True, False]):
        for v in range(len(var_names)):
            data = []
            h = []
            vmin = 0
            vmax = 0
            lon, lat = grid.get_lon_lat(gtype=gtype[v], dim=1)
            hfac = grid.get_hfac(gtype=gtype[v])
            for n in range(num_bdry):
                # Read and time-average the file (don't worry about different month lengths for plotting purposes)
                file_path = file_head + var_names[v] + '_' + bdry_loc[n]
                if bdry_loc[n] in ['N', 'S']:
                    dimensions = 'x'
                    h.append(lon)
                    h_label = 'Longitude'
                elif bdry_loc[n] in ['E', 'W']:
                    dimensions = 'y'
                    h.append(lat)
                    h_label = 'Latitude'
                if oce:
                    dimensions += 'z'
                dimensions += 't'
                data_tmp = read_binary(file_path, [grid.nx, grid.ny, grid.nz], dimensions)
                data_tmp = np.mean(data_tmp, axis=0)
                # Mask
                if bdry_loc[n] == 'N':
                    hfac_bdry = hfac[:,-1,:]
                elif bdry_loc[n] == 'S':
                    hfac_bdry = hfac[:,0,:]
                elif bdry_loc[n] == 'E':
                    hfac_bdry = hfac[:,:,-1]
                elif bdry_loc[n] == 'W':
                    hfac_bdry = hfac[:,:,0]
                if not oce:
                    hfac_bdry = hfac_bdry[0,:]
                data_tmp = np.ma.masked_where(hfac_bdry==0, data_tmp)
                data.append(data_tmp)
                # Keep track of min and max across all boundaries
                vmin = min(vmin, np.amin(data_tmp))
                vmax = max(vmax, np.amax(data_tmp))
            # Now plot each boundary
            if oce:
                fig, gs, cax = set_panels('1x3C1')
            else:
                fig, gs = set_panels('1x3C0')
                gs.update(left=0.05, wspace=0.1, bottom=0.1)
            cmap = set_colours(data[0], ctype='plusminus', vmin=vmin, vmax=vmax)[0]
            for n in range(num_bdry):
                ax = plt.subplot(gs[0,n])
                if oce:
                    # Simple slice plot (don't worry about partial cells or lat/lon edges vs centres)
                    img = plt.pcolormesh(h[n], grid.z*1e-3, data[n], cmap=cmap, vmin=vmin, vmax=vmax)
                    if n==0:
                        ax.set_ylabel('Depth (km)')
                    if n==num_bdry-1:
                        plt.colorbar(img, cax=cax, orientation='horizontal')
                else:
                    # Line plot
                    plt.plot(h[n], data[n])
                    ax.grid(linestyle='dotted')
                    ax.set_ylim([vmin, vmax])
                    ax.axhline(color='black')
                if n==0:
                    ax.set_xlabel(h_label)
                ax.set_title(bdry_loc[n], fontsize=12)
                plt.suptitle(titles[v], fontsize=16)
                if fig_dir is not None:
                    fig_name = real_dir(fig_dir) + 'obcs_offset_' + var_names[v] + '.png'
                else:
                    fig_name = None
                finished_plot(fig, fig_name=fig_name)


# Now plot all months and the annual mean, for one variable and one boundary at a time.
def plot_lens_obcs_bias_corrections_monthly (fig_dir=None):

    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'mitgcm/PAS_grid/'
    in_dir = base_dir + 'CESM_bias_correction/obcs/'
    bdry_loc = ['N', 'W', 'E']
    oce_var = ['TEMP', 'SALT', 'UVEL', 'VVEL']
    ice_var = ['aice', 'hi', 'hs', 'uvel', 'vvel']
    gtype_oce = ['t', 't', 'u', 'v']
    gtype_ice = ['t', 't', 't', 'u', 'v']
    oce_titles = ['Temperature ('+deg_string+'C)', 'Salinity (psu)', 'Zonal velocity (m/s)', 'Meridional velocity (m/s)']
    ice_titles = ['Sea ice concentration', 'Sea ice thickness (m)', 'Snow thickness (m)', 'Sea ice zonal velocity (m/s)', 'Sea ice meridional velocity (m/s)']
    file_head = in_dir + 'LENS_offset_'
    bdry_patches = [None, None, None]
    num_bdry = len(bdry_loc)
    month_names = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

    grid = Grid(mit_grid_dir)

    # Loop over ocean and ice variables
    for var_names, gtype, titles, oce in zip([oce_var, ice_var], [gtype_oce, gtype_ice], [oce_titles, ice_titles], [True, False]):
        for v in range(len(var_names)):
            lon, lat = grid.get_lon_lat(gtype=gtype[v], dim=1)
            hfac = grid.get_hfac(gtype=gtype[v])
            for n in range(num_bdry):
                # Read the file but no time-averaging
                file_path = file_head + var_names[v] + '_' + bdry_loc[n]
                if bdry_loc[n] in ['N', 'S']:
                    dimensions = 'x'
                    h = lon
                elif bdry_loc[n] in ['E', 'W']:
                    dimensions = 'y'
                    h = lat
                if oce:
                    dimensions += 'z'
                dimensions += 't'
                data = read_binary(file_path, [grid.nx, grid.ny, grid.nz], dimensions)
                # Mask
                if bdry_loc[n] == 'N':
                    hfac_bdry = hfac[:,-1,:]
                elif bdry_loc[n] == 'S':
                    hfac_bdry = hfac[:,0,:]
                elif bdry_loc[n] == 'E':
                    hfac_bdry = hfac[:,:,-1]
                elif bdry_loc[n] == 'W':
                    hfac_bdry = hfac[:,:,0]
                if not oce:
                    hfac_bdry = hfac_bdry[0,:]
                hfac_bdry = add_time_dim(hfac_bdry, months_per_year)
                data = np.ma.masked_where(hfac_bdry==0, data)
                # Now plot each month
                if oce:
                    fig, gs, cax = set_panels('3x4+1C1')
                else:
                    fig, gs = set_panels('3x4+1C0')
                cmap, vmin, vmax = set_colours(data, ctype='plusminus')
                for t in range(months_per_year):
                    ax = plt.subplot(gs[t//4+1, t%4])
                    if oce:
                        ax.pcolormesh(h, grid.z*1e-3, data[t,:], cmap=cmap, vmin=vmin, vmax=vmax)
                    else:
                        ax.plot(h, data[t,:])
                        ax.set_ylim([vmin, vmax])
                        ax.grid(linestyle='dotted')
                        ax.axhline(color='black')
                    ax.set_title(month_names[t], fontsize=10)
                    ax.set_xticklabels([])
                    ax.set_yticklabels([])
                # Now plot annual mean
                ax = plt.subplot(gs[0,3])
                if oce:
                    img = ax.pcolormesh(h, grid.z*1e-3, np.mean(data, axis=0), cmap=cmap, vmin=vmin, vmax=vmax)
                    cbar = plt.colorbar(img, cax=cax, orientation='horizontal')
                    reduce_cbar_labels(cbar)
                    ax.set_yticklabels([])
                else:
                    ax.plot(h, np.mean(data, axis=0))
                    ax.set_ylim([vmin, vmax])
                    ax.grid(linestyle='dotted')
                    ax.axhline(color='black')
                ax.set_xticklabels([])
                ax.set_title('Annual', fontsize=10)
                plt.suptitle(titles[v] + ', ' + bdry_loc[n] + ' boundary', fontsize=14)
                if fig_dir is not None:
                    fig_name = real_dir(fig_dir) + 'obcs_offset_monthly_' + var_names[v] + '_' + bdry_loc[n] + '.png'
                else:
                    fig_name = None
                finished_plot(fig, fig_name=fig_name)


# Calculate and plot the ensemble mean trends in the LENS ocean for the given boundary and given variable.
def calc_obcs_trends_lens (var_name, bdry, tmp_file, fig_name=None):

    mit_grid_dir = '/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/'
    num_ens = 40
    start_year = 2006
    end_year = 2100
    num_years = end_year - start_year + 1
    p0 = 0.05
    if var_name == 'TEMP':
        units = deg_string+'C'
    elif var_name == 'SALT':
        units = 'psu'
    else:
        print('Error (calc_obcs_trends_lens): unknown variable ' + var_name)
        sys.exit()

    # Read POP grid
    grid_file = find_cesm_file('LENS', var_name, 'oce', 'monthly', 1, start_year)[0]
    lon, lat, z, nx, ny, nz = read_pop_grid(grid_file)

    # Read MITgcm grid and get boundary location
    mit_grid = Grid(mit_grid_dir)
    loc0 = find_obcs_boundary(mit_grid, bdry)[0]
    # Find interpolation coefficients to the POP grid
    if bdry in ['N', 'S']:
        direction = 'lat'
        h_2d = lon
    elif bdry in ['E', 'W']:
        direction = 'lon'
        h_2d = lat
    i1, i2, c1, c2 = interp_slice_helper_nonreg(lon, lat, loc0, direction)
    # Interpolate the horizontal axis to this boundary
    h = extract_slice_nonreg(h_2d, direction, i1, i2, c1, c2)
    nh = h.size
    # Trim to MITgcm grid
    h_trim = trim_slice_to_grid(h, h, mit_grid, direction)[0]
    nh_trim = h_trim.size

    if not os.path.isfile(tmp_file):
        # Calculate the trends
        trends = np.ma.zeros([num_ens, nz, nh_trim])
        # Loop over ensemble members
        for n in range(num_ens):
            print('Processing ensemble member ' + str(n+1))
            data_ens = np.ma.empty([num_years, nz, nh])
            for year in range(start_year, end_year+1):
                file_path, t0, tf = find_cesm_file('LENS', var_name, 'oce', 'monthly', n+1, year)
                print('...processing indices '+str(t0)+'-'+str(tf-1)+' from '+file_path)
                # Read just this year
                data_tmp = read_netcdf(file_path, var_name, t_start=t0, t_end=tf)
                # Annually average
                ndays = np.array([days_per_month(month+1, year) for month in range(12)])
                data_tmp = np.average(data_tmp, axis=0, weights=ndays)
                # Interpolate to the boundary
                data_ens[year-start_year,:] = extract_slice_nonreg(data_tmp, direction, i1, i2, c1, c2)
            # Now trim to the other boundaries
            data_ens = trim_slice_to_grid(data_ens, h, mit_grid, direction)[0]
            # Loop over each point and calculate trends
            print('...calculating trends')
            for k in range(nz):
                for j in range(nh_trim):
                    trends[n,k,j] = linregress(np.arange(num_years), data_ens[:,k,j])[0]
        # Save results in temporary binary file
        write_binary(trends, tmp_file)
    else:
        # Trends have been precomputed; read them (hack to assume nx=ny=nh)
        trends = read_binary(tmp_file, [nh_trim, nh_trim, nz], 'yzt')

    # Calculate the mean trend and significance
    mean_trend = np.mean(trends, axis=0)*1e2  # Per century
    p_val = ttest_1samp(trends, 0, axis=0)[1]
    # For any trends which aren't significant, fill with zeros
    mean_trend[p_val > p0] = 0

    # Plot
    fig, ax = plt.subplots()
    cmap, vmin, vmax = set_colours(mean_trend, ctype='plusminus')
    img = ax.pcolormesh(h_trim, z, mean_trend, cmap=cmap, vmin=vmin, vmax=vmax)
    cbar = plt.colorbar(img)
    plt.title(var_name+' trend at '+bdry+' boundary ('+units+'/century)', fontsize=14)
    finished_plot(fig, fig_name=fig_name)


# Calculate a monthly climatology of T, S, and z from LENS in normalised potential density space: ensemble mean over 40 members, climatology over 1998-2017 for comparison with WOA at each boundary.
def calc_lens_climatology_density_space (out_dir='./'):

    out_dir = real_dir(out_dir)
    var_names = ['TEMP', 'SALT', 'z']
    start_year = 1998  # for climatology
    end_year = 2017
    num_years = end_year-start_year+1
    num_ens = 40
    mit_grid_dir = '/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/'
    nrho = 100
    bdry_loc = ['N', 'W', 'E']
    num_bdry = len(bdry_loc)
    num_var = len(var_names)
    out_file_head = 'LENS_climatology_density_space_'
    out_file_tail = '_'+str(start_year)+'-'+str(end_year)

    # Read/generate grids
    grid_file = find_cesm_file('LENS', var_names[0], 'oce', 'monthly', 1, start_year)[0]
    lon, lat, z_1d, nx, ny, nz = read_pop_grid(grid_file)
    mit_grid = Grid(mit_grid_dir)
    loc0 = [find_obcs_boundary(mit_grid, bdry)[0] for bdry in bdry_loc]
    rho_axis = np.linspace(0, 1, num=nrho)

    for b in range(num_bdry):
        print('Processing '+bdry_loc[b]+' boundary')
        if bdry_loc[b] in ['N', 'S']:
            direction = 'lat'
            h_2d = lon
            mit_h = mit_grid.lon_1d
        elif bdry_loc[b] in ['E', 'W']:
            direction = 'lon'
            h_2d = lat
            mit_h = mit_grid.lat_1d
        # Get interpolation coefficients to extract the slice at this boundary
        i1, i2, c1, c2 = interp_slice_helper_nonreg(lon, lat, loc0[b], direction)
        # Interpolate the horizontal axis to this boundary
        h_full = extract_slice_nonreg(h_2d, direction, i1, i2, c1, c2)
        h = trim_slice_to_grid(h_full, h_full, mit_grid, direction)[0]
        nh = h.size
        # Tile h and z over the slice to make them 2D
        h = np.tile(h, (nz, 1))
        z = np.tile(np.expand_dims(z_1d, 1), (1, nh))
        # Set up array for monthly climatology of T, S, z in density space
        lens_clim = np.ma.zeros([num_var, months_per_year, nrho, mit_h.size])
        # Loop over ensemble members and time indices
        for n in range(num_ens):
            print('Processing ensemble member '+str(n+1))
            for year in range(start_year, end_year+1):
                print('...'+str(year))
                for month in range(months_per_year):
                    # Read temperature and salinity and slice to boundary
                    ts_slice = np.ma.empty([num_var-1, nz, nh])
                    for v in range(num_var-1):
                        file_path, t0_year, tf_year = find_cesm_file('LENS', var_names[v], 'oce', 'monthly', n+1, year)
                        t0 = t0_year+month
                        data_3d = read_netcdf(file_path, var_names[v], t_start=t0, t_end=t0+1)
                        data_slice = extract_slice_nonreg(data_3d, direction, i1, i2, c1, c2)
                        data_slice = trim_slice_to_grid(data_slice, h_full, mit_grid, direction, warn=False)[0]
                        ts_slice[v,:] = data_slice
                    # Calculate potential density at this slice
                    rho = potential_density('MDJWF', ts_slice[1,:], ts_slice[0,:])
                    # Apply land mask
                    rho = np.ma.masked_where(ts_slice[1,:].mask, rho)
                    # Normalise to the range 0-1
                    rho_min = np.amin(rho)
                    rho_max = np.amax(rho)
                    rho_norm = (rho - rho_min)/(rho_max - rho_min)
                    # Now fill the land mask with something higher than the highest density
                    rho_norm[ts_slice[1,:].mask] = 1.1
                    # Regrid each variable to the new density axis, at the same time as to the MITgcm horizontal axis, and accumulate climatology
                    for data, v in zip([ts_slice[0,:], ts_slice[1,:], z], np.arange(num_var)):
                        lens_clim[v,month,:] += interp_nonreg_xy(h, rho_norm, data, mit_h, rho_axis, fill_mask=True)
        # Convert from integral to average
        lens_clim /= (num_ens*num_years)
        # Save to binary file
        for v in range(num_var):
            write_binary(lens_clim[v,:], out_dir+out_file_head+var_names[v]+'_'+bdry_loc[b]+out_file_tail)


# Calculate the WOA climatology of T, S, and z in normalised potential density space, as above.
def calc_woa_density_space (out_dir='./'):

    out_dir = real_dir(out_dir)
    base_dir = '/data/oceans_output/shelf/kaight/'
    in_dir = base_dir + 'ics_obcs/PAS/'
    grid_dir = base_dir + 'mitgcm/PAS_grid/'
    bdry_loc = ['N', 'W', 'E']
    var_names_in = ['theta', 'salt']
    var_names_out = ['TEMP', 'SALT', 'z']
    file_head_in = in_dir + 'OB'
    file_tail_in = '_woa_mon.bin'
    file_head_out = out_dir + 'WOA_density_space_'
    num_var = len(var_names_out)
    num_bdry = len(bdry_loc)
    nrho = 100

    grid = Grid(grid_dir)
    rho_axis = np.linspace(0, 1, num=nrho)

    for b in range(num_bdry):
        print('Processing '+bdry_loc[b]+' boundary')
        if bdry_loc[b] in ['N', 'S']:
            h = grid.lon_1d
            nh = grid.nx
            dimensions = 'xzt'
        elif bdry_loc[b] in ['E', 'W']:
            h = grid.lat_1d
            nh = grid.ny
            dimensions = 'yzt'
        h_2d = np.tile(h, (grid.nz, 1))
        z = np.tile(np.expand_dims(grid.z, 1), (1, nh))
        if bdry_loc[b] == 'N':
            hfac = grid.hfac[:,-1,:]
        elif bdry_loc[b] == 'S':
            hfac = grid.hfac[:,0,:]
        elif bdry_loc[b] == 'E':
            hfac = grid.hfac[:,:,-1]
        elif bdry_loc[b] == 'W':
            hfac = grid.hfac[:,:,0]
        # Read temperature and salinity at this boundary
        ts_bdry = np.ma.empty([num_var-1, months_per_year, grid.nz, nh])
        for v in range(num_var-1):
            file_path = file_head_in + bdry_loc[b] + var_names_in[v] + file_tail_in
            ts_bdry[v,:] = read_binary(file_path, [grid.nx, grid.ny, grid.nz], dimensions)
        woa_clim = np.ma.zeros([num_var, months_per_year, nrho, nh])            
        for month in range(months_per_year):
            # Calculate potential density at this boundary for this month
            rho = potential_density('MDJWF', ts_bdry[1,month,:], ts_bdry[0,month,:])
            # Apply land mask
            rho = np.ma.masked_where(hfac==0, rho)
            # Normalise to the range 0-1
            rho_min = np.amin(rho)
            rho_max = np.amax(rho)
            rho_norm = (rho - rho_min)/(rho_max - rho_min)
            # Now fill the land mask with something even higher than the highest density (shouldn't mess up the interpolation that way)
            rho_norm[hfac==0] = 1.1
            # Regrid to the new density axis
            for data, v in zip([ts_bdry[0,month,:], ts_bdry[1,month,:], z], np.arange(num_var)):
                woa_clim[v,month,:] = interp_nonreg_xy(h_2d, rho_norm, data, h, rho_axis, fill_mask=True)
        # Save to binary file
        for v in range(num_var):
            write_binary(woa_clim[v,:], file_head_out+var_names_out[v]+'_'+bdry_loc[b])


# Calculate offsets for LENS with respect to WOA
def calc_lens_offsets_density_space (in_dir='./', out_dir='./'):

    in_dir = real_dir(in_dir)
    out_dir = real_dir(out_dir)    
    var_names = ['TEMP', 'SALT', 'z']
    bdry_loc = ['N', 'W', 'E']
    lens_file_head = in_dir+'LENS_climatology_density_space_'
    lens_file_tail = '_1998-2017'
    woa_file_head = in_dir+'WOA_density_space_'
    out_file_head = out_dir+'LENS_offset_density_space_'
    mit_grid_dir = '/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/'
    nrho = 100
    
    grid = Grid(mit_grid_dir)

    for bdry in bdry_loc:
        if bdry in ['N', 'S']:
            nh = grid.nx
            dimensions = 'xzt'
        elif bdry in ['E', 'W']:
            nh = grid.ny
            dimensions = 'yzt'
        for var in var_names:
            woa_data = read_binary(woa_file_head+var+'_'+bdry, [grid.nx, grid.ny, nrho], dimensions)
            lens_data = read_binary(lens_file_head+var+'_'+bdry+lens_file_tail, [grid.nx, grid.ny, nrho], dimensions)
            lens_offset = woa_data - lens_data
            write_binary(lens_offset, out_file_head+var+'_'+bdry)


# Helper function to read and correct the LENS temperature and salinity for a given year, month, boundary, and ensemble member. Both month and ens are 1-indexed.
def read_correct_lens_density_space (bdry, ens, year, month, in_dir='/data/oceans_output/shelf/kaight/CESM_bias_correction/obcs/', mit_grid_dir='/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/', return_raw=False):

    in_dir = real_dir(in_dir)
    file_head = in_dir+'LENS_offset_density_space_'
    var_names = ['TEMP', 'SALT', 'z']
    num_var = len(var_names)
    nrho = 100

    # Read the grids and slice to boundary
    grid = Grid(mit_grid_dir)
    lens_grid_file = find_cesm_file('LENS', var_names[0], 'oce', 'monthly', 1, year)[0]
    lens_lon, lens_lat, lens_z, lens_nx, lens_ny, lens_nz = read_pop_grid(lens_grid_file)
    loc0 = find_obcs_boundary(grid, bdry)[0]
    if bdry in ['N', 'S']:
        direction = 'lat'
        dimensions = 'xzt'
        lens_h_2d = lens_lon
        mit_h = grid.lon_1d
    elif bdry in ['E', 'W']:
        direction = 'lon'
        dimensions = 'yzt'
        lens_h_2d = lens_lat
        mit_h = grid.lat_1d
    hfac = get_hfac_bdry(grid, bdry)
    i1, i2, c1, c2 = interp_slice_helper_nonreg(lens_lon, lens_lat, loc0, direction)
    lens_h_full = extract_slice_nonreg(lens_h_2d, direction, i1, i2, c1, c2)
    lens_h = trim_slice_to_grid(lens_h_full, lens_h_full, grid, direction)[0]
    lens_nh = lens_h.size
    lens_h = np.tile(lens_h, (lens_nz, 1))
    lens_z = np.tile(np.expand_dims(lens_z, 1), (1, lens_nh))
    rho_axis = np.linspace(0, 1, num=nrho)
    mit_h_2d = np.tile(mit_h, (nrho, 1))

    # Read and slice temperature and salinity for this month
    lens_ts_z = np.ma.empty([num_var-1, lens_nz, lens_nh])
    for v in range(num_var-1):
        file_path, t0_year, tf_year = find_cesm_file('LENS', var_names[v], 'oce', 'monthly', ens, year)
        t0 = t0_year + month-1
        data_3d = read_netcdf(file_path, var_names[v], t_start=t0, t_end=t0+1)
        data_slice = extract_slice_nonreg(data_3d, direction, i1, i2, c1, c2)
        data_slice = trim_slice_to_grid(data_slice, lens_h_full, grid, direction, warn=False)[0]
        lens_ts_z[v,:] = data_slice
    # Calculate potential density, mask, normalise, and fill as before
    lens_rho_z = potential_density('MDJWF', lens_ts_z[1,:], lens_ts_z[0,:])
    lens_mask = lens_ts_z[1,:].mask
    lens_rho_z = np.ma.masked_where(lens_mask, lens_rho_z)
    rho_min = np.amin(lens_rho_z, axis=0)
    rho_max = np.amax(lens_rho_z, axis=0)
    lens_rho_norm = (lens_rho_z - rho_min[None,:])/(rho_max[None,:] - rho_min[None,:])
    lens_rho_norm[lens_mask] = 1.1
    # Regrid each variable to the new density axis and the MITgcm horizontal axis, then apply corrections
    lens_corrected_density = np.ma.empty([num_var, nrho, mit_h.size])
    for data, v in zip([lens_ts_z[0,:], lens_ts_z[1,:], lens_z], np.arange(num_var)):
        data_interp_density = interp_nonreg_xy(lens_h, lens_rho_norm, data, mit_h, rho_axis, fill_mask=True)
        file_path_corr = file_head + var_names[v] + '_' + bdry
        corr = read_binary(file_path_corr, [mit_h.size, mit_h.size, nrho], dimensions)[month-1,:]
        lens_corrected_density[v,:] = data_interp_density + corr
    # Now regrid back to z-space on the MITgcm grid and apply the land mask
    lens_corrected_z = np.ma.empty([num_var, grid.nz, mit_h.size])
    for v in range(num_var-1):
        data_interp_z = interp_nonreg_xy(mit_h_2d, lens_corrected_density[-1,:], lens_corrected_density[v,:], mit_h, grid.z, fill_mask=True)
        lens_corrected_z[v,:] = np.ma.masked_where(hfac==0, data_interp_z)

    if return_raw:
        return lens_corrected_z[0,:], lens_corrected_z[1,:], lens_ts_z[0,:], lens_ts_z[1,:], lens_h, lens_z
    else:
        return lens_corrected_z[0,:], lens_corrected_z[1,:]
    
        
# Plot the LENS and WOA density space climatologies and the offset, for the given variable, boundary, and month (1-indexed)
def plot_lens_offsets_density_space (var, bdry, month, in_dir='./', fig_name=None):

    in_dir = real_dir(in_dir)
    mit_grid_dir = '/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/'
    nrho = 100
    lens_file = in_dir+'LENS_climatology_density_space_'+var+'_'+bdry+'_1998-2017'
    woa_file = in_dir+'WOA_density_space_'+var+'_'+bdry
    offset_file = in_dir+'LENS_offset_density_space_'+var+'_'+bdry
    file_paths = [lens_file, woa_file, offset_file]
    titles = ['LENS climatology', 'WOA climatology', 'LENS offset']
    num_panels = len(titles)

    grid = Grid(mit_grid_dir)
    rho_axis = np.linspace(0, 1, num=nrho)
    if bdry in ['N', 'S']:
        h = grid.lon_1d
        nh = grid.nx
        dimensions = 'xzt'
    elif bdry in ['E', 'W']:
        h = grid.lat_1d
        nh = grid.ny
        dimensions = 'yzt'
    hfac = get_hfac_bdry(grid, bdry)
    hfac_sum = np.tile(np.sum(hfac, axis=0), (nrho, 1))

    data = np.ma.empty([num_panels, nrho, nh])
    for n in range(num_panels):
        data_tmp = read_binary(file_paths[n], [grid.nx, grid.ny, nrho], dimensions)[month-1,:]
        data[n,:] = np.ma.masked_where(hfac_sum==0, data_tmp)
    fig, gs, cax1, cax2 = set_panels('1x3C2')
    cax = [cax1, None, cax2]
    for n in range(num_panels):
        ax = plt.subplot(gs[0,n])
        if n < 2:
            cmap, vmin, vmax = set_colours(data[:2,:])
        else:
            cmap, vmin, vmax = set_colours(data[n,:], ctype='plusminus')
        if n > 0:
            ax.set_yticklabels([])
        img = ax.pcolormesh(h, rho_axis, data[n,:], cmap=cmap, vmin=vmin, vmax=vmax)
        if cax[n] is not None:
            plt.colorbar(img, cax=cax[n])
        ax.set_ylim([1, 0])  # Highest density at bottom
        ax.set_title(titles[n], fontsize=14)
    plt.suptitle(var+' at '+bdry+' boundary, month '+str(month), fontsize=18)
    finished_plot(fig, fig_name=fig_name)


def plot_all_offsets_density_space (in_dir='./'):

    for bdry in ['N', 'W', 'E']:
        for var in ['TEMP', 'SALT', 'z']:
            for month in range(12):
                plot_lens_offsets_density_space(var, bdry, month+1, in_dir=in_dir)
                

# Scale temperature and salinity in the LENS climatology for each boundary, so the given min and max annual mean T and S over each boundary become the same as WOA.
def scale_lens_climatology (out_dir='./'):

    out_dir = real_dir(out_dir)
    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'mitgcm/PAS_grid/'
    lens_dir = base_dir + 'CESM_bias_correction/obcs/'
    woa_dir = base_dir + 'ics_obcs/PAS/'
    var_lens = ['TEMP', 'SALT']
    var_woa = ['theta', 'salt']
    file_head_woa = woa_dir + 'OB'
    file_tail_woa = '_woa_mon.bin'
    file_head_lens = lens_dir + 'LENS_climatology_'
    file_tail_lens = '_1998-2017'
    file_head_lens_out = lens_dir + 'LENS_climatology_scaled_'
    sources = ['WOA', 'LENS']
    num_sources = 2
    num_var = len(var_lens)
    ndays = np.array([days_per_month(t+1, 1998) for t in range(12)])
    bdry_loc = ['N', 'W', 'E']
    num_bdry = len(bdry_loc)

    grid = Grid(mit_grid_dir)

    # Loop over boundaries
    for bdry in bdry_loc:
        print(bdry + ' boundary:')
        hfac = get_hfac_bdry(grid, bdry)
        if bdry in ['N', 'S']:
            nh = grid.nx
            dimensions = 'xzt'
        elif bdry in ['E', 'W']:
            nh = grid.ny
            dimensions = 'yzt'
        if bdry == 'N':
            dV_bdry = grid.dV[:,-1,:]
        elif bdry == 'S':
            dV_bdry = grid.dV[:,0,:]
        elif bdry == 'E':
            dV_bdry = grid.dV[:,:,-1]
        elif bdry == 'W':
            dV_bdry = grid.dV[:,:,0]
        hfac_time = add_time_dim(hfac, months_per_year)
        # Read the data
        ts_data = np.ma.empty([num_sources, num_var, months_per_year, grid.nz, nh])
        for n in range(num_sources):
            for v in range(num_var):
                if n == 0:
                    # WOA
                    file_path = file_head_woa + bdry + var_woa[v] + file_tail_woa
                else:
                    # LENS
                    file_path = file_head_lens + var_lens[v] + '_' + bdry + file_tail_lens
                data_tmp = read_binary(file_path, [grid.nx, grid.ny, grid.nz], dimensions)
                ts_data[n,v,:] = np.ma.masked_where(hfac_time==0, data_tmp)
        # Correct based on annual mean
        ts_annual_mean = np.average(ts_data, axis=2, weights=ndays)
        ts_min = np.amin(ts_annual_mean, axis=(-2,-1))
        ts_max = np.amax(ts_annual_mean, axis=(-2,-1))
        for v in range(num_var):
            # Normalise the full LENS data
            lens_data = ts_data[1,v,:]
            lens_data_norm = (lens_data - ts_min[1,v])/(ts_max[1,v] - ts_min[1,v])
            # Invert the normalisation using the WOA limits
            lens_data_scaled_final = lens_data_norm*(ts_max[0,v] - ts_min[0,v]) + ts_min[0,v]
            # Write to file
            file_path = file_head_lens_out + var_lens[v] + '_' + bdry
            write_binary(lens_data_scaled_final, file_path)
        '''# Correct one month at a time
        for v in range(num_var):                 
            # Correct one month at a time
            lens_data_scaled_final = np.ma.empty(ts_data.shape[2:])
            for t in range(months_per_year):
                # Calculate min, max, and volume-mean for each source
                vmin = np.amin(ts_data[:,v,t,:,:], axis=(-2,-1))
                vmax = np.amax(ts_data[:,v,t,:,:], axis=(-2,-1))
                vmean = np.empty([num_sources])
                for n in range(num_sources):
                    vmean[n] = np.sum(ts_data[n,v,t,:,:]*hfac*dV_bdry)/np.sum(hfac*dV_bdry)
                # Piecewise-normalise the LENS data
                lens_data = ts_data[1,v,t,:]
                lens_data_scaled_full = np.ma.empty(lens_data.shape)
                # Start with everything below the mean
                index = lens_data < vmean[1]
                lens_data_norm = (lens_data - vmin[1])/(vmean[1] - vmin[1])
                lens_data_scaled = lens_data_norm*(vmean[0] - vmin[0]) + vmin[0]
                lens_data_scaled_full[index] = lens_data_scaled[index]
                # Now everything above the mean
                index = lens_data >= vmean[1]
                lens_data_norm = (lens_data - vmean[1])/(vmax[1] - vmean[1])
                lens_data_scaled = lens_data_norm*(vmax[0] - vmean[0]) + vmean[0]
                lens_data_scaled_full[index] = lens_data_scaled[index]
                lens_data_scaled_final[t,:] = lens_data_scaled_full
            # Write to file
            file_path = file_head_lens_out + var_lens[v] + '_' + bdry
            write_binary(lens_data_scaled_final, file_path)'''


# As above but using scaling instead of density correction
def read_correct_lens_scaled (bdry, ens, year, month, in_dir='/data/oceans_output/shelf/kaight/CESM_bias_correction/obcs/', mit_grid_dir='/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/', return_raw=False):

    in_dir = real_dir(in_dir)
    file_head = 'LENS_climatology_'
    file_head_corr = 'LENS_climatology_scaled_'
    file_tail = '_1998-2017'
    var_names = ['TEMP', 'SALT']
    num_var = len(var_names)

    # Read the grids and slice to boundary
    grid = Grid(mit_grid_dir)
    lens_grid_file = find_cesm_file('LENS', var_names[0], 'oce', 'monthly', 1, year)[0]
    lens_lon, lens_lat, lens_z, lens_nx, lens_ny, lens_nz = read_pop_grid(lens_grid_file)
    loc0 = find_obcs_boundary(grid, bdry)[0]
    if bdry in ['N', 'S']:
        direction = 'lat'
        dimensions = 'xzt'
        lens_h_2d = lens_lon
        mit_h = grid.lon_1d
    elif bdry in ['E', 'W']:
        direction = 'lon'
        dimensions = 'yzt'
        lens_h_2d = lens_lat
        mit_h = grid.lat_1d
    hfac = get_hfac_bdry(grid, bdry)
    i1, i2, c1, c2 = interp_slice_helper_nonreg(lens_lon, lens_lat, loc0, direction)
    lens_h_full = extract_slice_nonreg(lens_h_2d, direction, i1, i2, c1, c2)
    lens_h = trim_slice_to_grid(lens_h_full, lens_h_full, grid, direction)[0]
    lens_nh = lens_h.size
    lens_h = np.tile(lens_h, (lens_nz, 1))
    lens_z = np.tile(np.expand_dims(lens_z, 1), (1, lens_nh))

    # Loop over variables
    lens_raw = np.ma.empty([num_var, lens_nz, lens_nh])
    lens_corrected = np.ma.empty([num_var, grid.nz, mit_h.size])
    for v in range(num_var):
        file_path, t0_year, tf_year = find_cesm_file('LENS', var_names[v], 'oce', 'monthly', ens, year)
        t0 = t0_year + month-1
        data_3d = read_netcdf(file_path, var_names[v], t_start=t0, t_end=t0+1)
        data_slice = extract_slice_nonreg(data_3d, direction, i1, i2, c1, c2)
        data_slice = trim_slice_to_grid(data_slice, lens_h_full, grid, direction, warn=False)[0]
        lens_raw[v,:] = data_slice
        # Interpolate to the MITgcm grid
        data_interp = interp_nonreg_xy(lens_h, lens_z, data_slice, mit_h, grid.z, fill_mask=True)
        # Now read baseline climatology and scaled climatology
        lens_clim = read_binary(in_dir + file_head + var_names[v] + '_' + bdry + file_tail, [grid.nx, grid.ny, grid.nz], dimensions)[month-1,:]
        lens_clim_corr = read_binary(in_dir + file_head_corr + var_names[v] + '_' + bdry, [grid.nx, grid.ny, grid.nz], dimensions)[month-1,:]
        lens_corrected[v,:] = np.ma.masked_where(hfac==0, data_interp - lens_clim + lens_clim_corr)
    if return_raw:
        return lens_corrected[0,:], lens_corrected[1,:], lens_raw[0,:], lens_raw[1,:], lens_h, lens_z
    else:
        return lens_corrected[0,:], lens_corrected[1,:]


# Plot T/S diagrams of the WOA and LENS climatologies at the given boundary and month (set month=None for annual mean), and the difference in volumes between the two.
def plot_obcs_ts_lens_woa (bdry, month=None, num_bins=100, fig_name=None, corr=False):

    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'mitgcm/PAS_grid/'
    lens_dir = base_dir + 'CESM_bias_correction/obcs/'
    woa_dir = base_dir + 'ics_obcs/PAS/'
    var_lens = ['TEMP', 'SALT']
    var_woa = ['theta', 'salt']
    file_head_woa = woa_dir + 'OB'
    file_tail_woa = '_woa_mon.bin'
    if corr:
        file_head_lens = lens_dir + 'LENS_climatology_scaled_'
        file_tail_lens = ''
    else:
        file_head_lens = lens_dir + 'LENS_climatology_'
        file_tail_lens = '_1998-2017'
    num_sources = 2
    num_var = len(var_lens)
    ndays = np.array([days_per_month(t+1, 1998) for t in range(12)])

    # Build the grids
    grid = Grid(mit_grid_dir)
    hfac = get_hfac_bdry(grid, bdry)
    mask = np.invert(hfac==0)
    if bdry == 'N':
        dV_bdry = grid.dV[:,-1,:]
    elif bdry == 'S':
        dV_bdry = grid.dV[:,0,:]
    elif bdry == 'E':
        dV_bdry = grid.dV[:,:,-1]
    elif bdry == 'W':
        dV_bdry = grid.dV[:,:,0]
    if bdry in ['N', 'S']:
        nh = grid.nx
        dimensions = 'xzt'
    elif bdry in ['E', 'W']:
        nh = grid.ny
        dimensions = 'yzt'
    lens_grid_file = find_cesm_file('LENS', var_lens[0], 'oce', 'monthly', 1, 1998)[0]
    lens_lon, lens_lat, lens_z, lens_nx, lens_ny, lens_nz = read_pop_grid(lens_grid_file)
    # Need a few more fields to get the volume integrand
    lens_dA = read_netcdf(lens_grid_file, 'TAREA')*1e-4
    lens_dz = read_netcdf(lens_grid_file, 'dz')*1e-2
    lens_dV = xy_to_xyz(lens_dA, [lens_nx, lens_ny, lens_nz])*z_to_xyz(lens_dz, [lens_nx, lens_ny, lens_z])
    loc0 = find_obcs_boundary(grid, bdry)[0]
    if bdry in ['N', 'S']:
        direction = 'lat'
        dimensions = 'xzt'
        lens_h_2d = lens_lon
    elif bdry in ['E', 'W']:
        direction = 'lon'
        dimensions = 'yzt'
        lens_h_2d = lens_lat
    hfac = get_hfac_bdry(grid, bdry)
    i1, i2, c1, c2 = interp_slice_helper_nonreg(lens_lon, lens_lat, loc0, direction)
    lens_h_full = extract_slice_nonreg(lens_h_2d, direction, i1, i2, c1, c2)
    lens_h = trim_slice_to_grid(lens_h_full, lens_h_full, grid, direction, warn=False)[0]
    lens_nh = lens_h.size
    lens_dV_bdry = extract_slice_nonreg(lens_dV, direction, i1, i2, c1, c2)
    lens_dV_bdry = trim_slice_to_grid(lens_dV_bdry, lens_h_full, grid, direction, warn=False)[0]
        
    # Read the data
    ts_data_woa = np.ma.empty([num_var, grid.nz, nh])
    ts_data_lens = np.ma.empty([num_var, lens_nz, lens_nh])
    for v in range(num_var):
        woa_file = file_head_woa + bdry + var_woa[v] + file_tail_woa
        woa_data = read_binary(woa_file, [grid.nx, grid.ny, grid.nz], dimensions)
        lens_file = file_head_lens + var_lens[v] + '_' + bdry + file_tail_lens
        lens_data = read_binary(lens_file, [lens_nh, lens_nh, lens_nz], dimensions)
        lens_data = np.ma.masked_where(lens_data==0, lens_data)
        if month is None:
            # Annual mean
            ts_data_woa[v,:] = np.average(woa_data, axis=0, weights=ndays)
            ts_data_lens[v,:] = np.average(lens_data, axis=0, weights=ndays)
            month_str = ', annual mean'
        else:
            ts_data_woa[v,:] = woa_data[month-1,:]
            ts_data_lens[v,:] = lens_data[month-1,:]
            month_str = ', month '+str(month)
    mask_lens = np.invert(ts_data_lens[0,:].mask)

    # Bin T and S
    tmin = min(np.amin(ts_data_woa[0,:]), np.amin(ts_data_lens[0,:]))
    tmax = max(np.amax(ts_data_woa[0,:]), np.amax(ts_data_lens[0,:]))
    smin = min(np.amin(ts_data_woa[1,:]), np.amin(ts_data_lens[1,:]))
    smax = max(np.amax(ts_data_woa[1,:]), np.amax(ts_data_lens[1,:]))
    volume_woa, temp_centres, salt_centres, temp_edges, salt_edges = ts_binning(ts_data_woa[0,:], ts_data_woa[1,:], grid, mask, num_bins=num_bins, tmin=tmin, tmax=tmax, smin=smin, smax=smax, bdry=True, dV_bdry=dV_bdry)
    volume_lens = ts_binning(ts_data_lens[0,:], ts_data_lens[1,:], None, mask_lens, num_bins=num_bins, tmin=tmin, tmax=tmax, smin=smin, smax=smax, bdry=True, dV_bdry=lens_dV_bdry)[0]
    volume = [volume_woa, volume_lens]
    # Get difference in volume
    volume_diff = volume[1].data - volume[0].data
    volume.append(np.ma.masked_where(volume_diff==0, volume_diff))
    vmin_abs = min(np.amin(volume[0]), np.amin(volume[1]))
    vmax_abs = max(np.amax(volume[0]), np.amax(volume[1]))
    # Prepare to plot density
    salt_2d, temp_2d = np.meshgrid(np.linspace(smin, smax), np.linspace(tmin, tmax))
    density = potential_density('MDJWF', salt_2d, temp_2d)

    # Plot
    fig, gs, cax1, cax2 = set_panels('1x3C2')
    cax = [cax1, None, cax2]
    cmap_abs = set_colours(volume[0], vmin=vmin_abs, vmax=vmax_abs)[0]
    cmap_diff, vmin_diff, vmax_diff = set_colours(volume[2], ctype='plusminus')
    cmap = [cmap_abs, cmap_abs, cmap_diff]
    vmin = [vmin_abs, vmin_abs, vmin_diff]
    vmax = [vmax_abs, vmax_abs, vmax_diff]
    titles = ['WOA', 'LENS', 'Difference']
    for n in range(num_sources+1):
        ax = plt.subplot(gs[0,n])
        plt.contour(salt_2d, temp_2d, density, colors='DarkGrey', linestyles='dotted')
        img = plt.pcolor(salt_centres, temp_centres, volume[n], vmin=vmin[n], vmax=vmax[n], cmap=cmap[n])
        ax.set_xlim([smin, smax])
        ax.set_ylim([tmin, tmax])
        if n == 0:
            plt.xlabel('Salinity (psu)')
            plt.ylabel('Temperature ('+deg_string+'C)')
        if cax[n] is not None:
            plt.colorbar(img, cax=cax[n])
        ax.set_title(titles[n])
    plt.suptitle('Log of volumes at '+bdry+' boundary' + month_str)
    finished_plot(fig, fig_name=fig_name)


# For a given year, month, variable, boundary, and ensemble member, plot the uncorrected and corrected LENS fields as well as the WOA climatology.
def plot_obcs_corrected (var, bdry, ens, year, month, fig_name=None, option='ts'):

    base_dir = '/data/oceans_output/shelf/kaight/'
    obcs_dir = base_dir + 'ics_obcs/PAS/'
    grid_dir = base_dir + 'mitgcm/PAS_grid/'
    woa_file_head = obcs_dir + 'OB'
    woa_file_tail = '_woa_mon.bin'
    if var == 'TEMP':
        woa_var = 'theta'
        var_title = 'Temperature ('+deg_string+'C)'
    elif var == 'SALT':
        woa_var = 'salt'
        var_title = 'Salinity (psu)'
    titles = ['WOA', 'LENS', 'LENS corrected']
    num_panels = len(titles)

    grid = Grid(grid_dir)
    if bdry in ['N', 'S']:
        mit_h = grid.lon_1d
        dimensions = 'xzt'
    elif bdry in ['E', 'W']:
        mit_h = grid.lat_1d
        dimensions = 'yzt'
    hfac = get_hfac_bdry(grid, bdry)

    # Read the corrected and uncorrected LENS fields
    if option == 'density':
        lens_temp_corr, lens_salt_corr, lens_temp_raw, lens_salt_raw, lens_h, lens_z = read_correct_lens_density_space(bdry, ens, year, month, return_raw=True)
    elif option == 'scaled':
        lens_temp_corr, lens_salt_corr, lens_temp_raw, lens_salt_raw, lens_h, lens_z = read_correct_lens_scaled(bdry, ens, year, month, return_raw=True)
    elif option == 'ts':
        lens_temp_corr, lens_salt_corr, lens_temp_raw, lens_salt_raw, lens_h, lens_z = read_correct_lens_ts_space(bdry, ens, year, month, return_raw=True)
    if var == 'TEMP':
        lens_data_corr = lens_temp_corr
        lens_data_raw = lens_temp_raw
    elif var == 'SALT':
        lens_data_corr = lens_salt_corr
        lens_data_raw = lens_salt_raw
    # Read the WOA fields
    woa_file = woa_file_head + bdry + woa_var + woa_file_tail
    woa_data = read_binary(woa_file, [grid.nx, grid.ny, grid.nz], dimensions)[month-1,:]
    woa_data = np.ma.masked_where(hfac==0, woa_data)

    # Wrap up for plotting
    data = [woa_data, lens_data_raw, lens_data_corr]
    h = [mit_h, lens_h, mit_h]
    z = [grid.z, lens_z, grid.z]
    vmin = min(min(np.amin(woa_data), np.amin(lens_data_raw)), np.amin(lens_data_corr))
    vmax = max(max(np.amax(woa_data), np.amax(lens_data_raw)), np.amax(lens_data_corr))
    cmap = set_colours(data[0], vmin=vmin, vmax=vmax)[0]
    fig, gs, cax = set_panels('1x3C1')
    for n in range(num_panels):
        ax = plt.subplot(gs[0,n])
        img = ax.pcolormesh(h[n], z[n], data[n], cmap=cmap, vmin=vmin, vmax=vmax)
        if n==2:
            plt.colorbar(img, cax=cax, orientation='horizontal')
        if n > 0:
            ax.set_yticklabels([])
        ax.set_title(titles[n], fontsize=14)
    plt.suptitle(var_title+' at '+bdry+' boundary, '+str(year)+'/'+str(month), fontsize=18)
    finished_plot(fig, fig_name=fig_name)


# Plot T/S profiles horizontally averaged over the eastern boundary from 70S to the coastline, for a given month (1-indexed) and year. Show the original WOA climatology, the LENS climatology, the uncorrected LENS field from the first ensemble member, and the corrected LENS field.
def plot_obcs_profiles (year, month, fig_name=None):

    base_dir = '/data/oceans_output/shelf/kaight/'
    obcs_dir = base_dir + 'ics_obcs/PAS/'
    clim_dir = base_dir + 'CESM_bias_correction/obcs/'
    grid_dir = base_dir + 'mitgcm/PAS_grid/'
    woa_file_head = obcs_dir + 'OB'
    woa_file_tail = '_woa_mon.bin'
    lens_file_head = clim_dir + 'LENS_climatology_'
    lens_file_tail = '_1998-2017'
    bdry = 'E'
    woa_var = ['theta', 'salt']
    lens_var = ['TEMP', 'SALT']
    units = [deg_string+'C', 'psu']
    ymax = -70
    num_var = len(woa_var)
    direction = 'lon'
    ndays = np.array([days_per_month(t+1, year) for t in range(12)])
    titles = ['WOA', 'LENS climatology', 'LENS uncorrected', 'LENS corrected']
    colours = ['blue', 'black', 'green', 'red']
    num_profiles = len(titles)

    # Build the grids
    grid = Grid(grid_dir)    
    lon0 = find_obcs_boundary(grid, bdry)[0]
    hfac_slice = get_hfac_bdry(grid, bdry)
    # Mask out dA north of 70S, tile in the z direction, and select the boundary
    dA = np.ma.masked_where(grid.lat_2d > ymax, grid.dA)
    dA = xy_to_xyz(dA, grid)
    dA_slice = dA[:,:,-1]

    # Read the corrected and uncorrected LENS fields
    lens_temp_corr, lens_salt_corr, lens_temp_raw, lens_salt_raw, lens_h, lens_z = read_correct_lens_ts_space(bdry, 1, year, month, return_raw=True) 
    
    profiles = np.ma.empty([num_var, num_profiles, grid.nz])
    # Loop over variables
    for v in range(num_var):
        
        # Read WOA climatology
        woa_data = read_binary(woa_file_head+bdry+woa_var[v]+woa_file_tail, [grid.nx, grid.ny, grid.nz], 'yzt')
        # Extract the right month
        woa_data = woa_data[month-1,:]

        # Choose LENS data
        if lens_var[v] == 'TEMP':
            lens_data_uncorrected = lens_temp_raw
            lens_data_corrected = lens_temp_corr
        elif lens_var[v] == 'SALT':
            lens_data_uncorrected = lens_salt_raw
            lens_data_corrected = lens_salt_corr
        lens_mask = np.invert(lens_data_uncorrected.mask).astype(float)
        # Interpolate the LENS slice to the MITgcm grid
        lens_data_uncorrected = interp_bdry(lens_h, lens_z, lens_data_uncorrected, lens_mask, grid.lat_1d, grid.z, hfac_slice, lon=False, depth_dependent=True)

        # Read LENS climatology
        lens_clim_raw = read_binary(lens_file_head+lens_var[v]+'_'+bdry+lens_file_tail, [lens_h.size, lens_h.size, lens_z.size], 'yzt')
        lens_clim_raw = lens_clim_raw[month-1,:]
        # Interpolate to the MITgcm grid
        lens_clim = interp_bdry(lens_h, lens_z, lens_clim_raw, lens_mask, grid.lat_1d, grid.z, hfac_slice, lon=False, depth_dependent=True)

        # Horizontally average everything south of 70S
        for data_slice, n in zip([woa_data, lens_clim, lens_data_uncorrected, lens_data_corrected], range(num_profiles)):
            profiles[v,n,:] = np.sum(data_slice*hfac_slice*dA_slice, axis=-1)/np.sum(hfac_slice*dA_slice, axis=-1)

    # Plot
    fig, gs = set_panels('1x2C0')
    gs.update(left=0.08, bottom=0.18, top=0.87)
    for v in range(num_var):
        ax = plt.subplot(gs[0,v])
        for n in range(num_profiles):
            ax.plot(profiles[v,n,:], grid.z, color=colours[n], label=titles[n])
        ax.grid(linestyle='dotted')
        ax.set_title(lens_var[v], fontsize=16)
        ax.set_xlabel(units[v])
        if v==0:
            ax.set_ylabel('Depth (m)')
            ax.legend(loc='lower right', bbox_to_anchor=(1.7, -0.2), ncol=num_profiles)
        else:
            ax.set_yticklabels([])
    plt.suptitle(bdry + ' boundary, '+str(year)+'/'+str(month).zfill(2), fontsize=16)
    finished_plot(fig, fig_name=fig_name)


# Plot Hovmollers of temp or salt in the given region for all 5 ensemble members, LENS average, and PACE average.
def plot_hovmoller_lens_ensemble (var, region, num_ens=5, base_dir='./', fig_name=None):

    base_dir = real_dir(base_dir)
    grid_dir = base_dir + 'PAS_grid/'
    lens_mean_file = base_dir + 'hovmoller_lens_mean.nc'
    pace_mean_file = base_dir + 'hovmoller_pace_mean.nc'
    file_paths = ['PAS_LENS'+str(n+1).zfill(3)+'/output/hovmoller.nc' for n in range(num_ens)] + [lens_mean_file, pace_mean_file]
    var_name = region + '_' + var
    if var == 'temp':
        var_title = 'Temperature ('+deg_string+'C)'
        vmin = -1.6
        vmax = 1.4
    elif var == 'salt':
        var_title = 'Salinity (psu)'
        vmin = 34
        vmax = 34.8
    suptitle = var_title + ' in ' + region_names[region]
    smooth = 12
    start_year = 1920
    end_year = 2100
    titles = ['LENS '+str(n+1).zfill(3) for n in range(num_ens)] + ['LENS\nmean', 'PACE\nmean']
    
    grid = Grid('PAS_grid/')
    all_data = []
    all_time = []
    for n in range(num_ens+2):
        data = read_netcdf(file_paths[n], var_name)
        time = netcdf_time(file_paths[n], monthly=False)
        t_start = index_year_start(time, start_year)
        data = data[t_start:]
        time = time[t_start:]
        if n == 0:
            mask = data[0,:].mask
        else:
            if not isinstance(data, np.ma.MaskedArray):
                mask_full = add_time_dim(mask, data.shape[0])
                data = np.ma.masked_where(mask_full, data)
        all_data.append(data)
        all_time.append(time)

    fig = plt.figure(figsize=(6,12))
    gs = plt.GridSpec(num_ens+2,1)
    gs.update(left=0.07, right=0.85, bottom=0.04, top=0.95, hspace=0.08)
    cax = fig.add_axes([0.75, 0.96, 0.24, 0.012])
    for n in range(num_ens+2):
        ax = plt.subplot(gs[n,0])
        img = hovmoller_plot(all_data[n], all_time[n], grid, smooth=smooth, ax=ax, make_cbar=False, vmin=vmin, vmax=vmax)
        ax.set_xlim([datetime.date(start_year, 1, 1), datetime.date(end_year, 12, 31)])
        ax.set_xticks([datetime.date(year, 1, 1) for year in np.arange(start_year, end_year, 20)])
        if n == 0:
            ax.set_yticks([0, -500, -1000])
            ax.set_yticklabels(['0', '0.5', '1'])
            ax.set_ylabel('')
        else:
            ax.set_yticks([])
            ax.set_ylabel('')
        if n == 1:
            ax.set_ylabel('Depth (km)', fontsize=10)
        if n != num_ens+1:
            ax.set_xticklabels([])
        ax.set_xlabel('')
        plt.text(1.01, 0.5, titles[n], ha='left', va='center', transform=ax.transAxes, fontsize=11)
    plt.suptitle(suptitle, fontsize=16, x=0.05, ha='left')
    cbar = plt.colorbar(img, cax=cax, orientation='horizontal', extend='both')
    cax.xaxis.set_ticks_position('top')
    reduce_cbar_labels(cbar)
    finished_plot(fig, fig_name=fig_name)


# For a given year, month, boundary, and ensemble member, plot the raw anomalies in LENS and the corrected anomalies as applied to WOA, for both temperature and salinity.
def plot_obcs_anomalies (bdry, ens, year, month, fig_name=None, zmin=None):

    base_dir = '/data/oceans_output/shelf/kaight/'
    in_dir = '/data/oceans_output/shelf/kaight/CESM_bias_correction/obcs/'
    obcs_dir = base_dir + 'ics_obcs/PAS/'
    grid_dir = base_dir + 'mitgcm/PAS_grid/'
    woa_file_head = obcs_dir + 'OB'
    woa_file_tail = '_woa_mon.bin'
    lens_file_head = in_dir + 'LENS_climatology_'
    lens_file_tail = '_1998-2017'
    lens_var = ['TEMP', 'SALT']
    woa_var = ['theta', 'salt']
    var_titles = ['Temperature anomaly ('+deg_string+'C)', 'Salinity anomaly (psu)']
    source_titles = ['Uncorrected', 'Corrected']
    num_var = len(lens_var)
    num_sources = len(source_titles)

    grid = Grid(grid_dir)
    if bdry in ['N', 'S']:
        mit_h = grid.lon_1d
        dimensions = 'xzt'
    elif bdry in ['E', 'W']:
        mit_h = grid.lat_1d
        dimensions = 'yzt'
    hfac = get_hfac_bdry(grid, bdry)

    # Read the corrected and uncorrected LENS fields
    temp_corr, salt_corr, lens_temp_raw, lens_salt_raw, lens_h, lens_z = read_correct_lens_ts_space(bdry, ens, year, month, return_raw=True)
    lens_nh = lens_h.size
    lens_nz = lens_z.size

    # Read the LENS climatology
    lens_clim = np.ma.empty([num_var, lens_nz, lens_nh])
    for v in range(num_var):
        file_path = lens_file_head + lens_var[v] + '_' + bdry + lens_file_tail
        lens_clim[v,:] = read_binary(file_path, [lens_nh, lens_nh, lens_nz], dimensions)[month-1,:]
    # Calculate uncorrected anomalies
    dtemp_uncorr = lens_temp_raw - lens_clim[0,:]
    dsalt_uncorr = lens_salt_raw - lens_clim[1,:]

    # Read the WOA climatology
    woa_clim = np.ma.empty([num_var, grid.nz, mit_h.size])
    for v in range(num_var):
        file_path = woa_file_head + bdry + woa_var[v] + woa_file_tail
        woa_clim[v,:] = read_binary(file_path, [grid.nx, grid.ny, grid.nz], dimensions)[month-1,:]
    # Calculate corrected anomalies
    dtemp_corr = temp_corr - woa_clim[0,:]
    dsalt_corr = salt_corr - woa_clim[1,:]

    # Wrap up for plotting
    data = [[dtemp_uncorr, dtemp_corr], [dsalt_uncorr, dsalt_corr]]
    h = [lens_h, mit_h]
    z = [lens_z, grid.z]
    vmin = [min(np.amin(dtemp_uncorr), np.amin(dtemp_corr)), min(np.amin(dsalt_uncorr), np.amin(dsalt_corr))]
    vmax = [max(np.amax(dtemp_uncorr), np.amax(dtemp_corr)), max(np.amax(dsalt_uncorr), np.amax(dsalt_corr))]
    cmap = [set_colours(dtemp_uncorr, vmin=vmin[0], vmax=vmax[0], ctype='plusminus')[0], set_colours(dsalt_uncorr, vmin=vmin[1], vmax=vmax[1], ctype='plusminus')[0]]
    fig, gs, cax1, cax2 = set_panels('2x2C2')
    cax = [cax1, cax2]
    for v in range(num_var):
        for n in range(num_sources):
            ax = plt.subplot(gs[v,n])
            img = ax.pcolormesh(h[n], z[n], data[v][n], cmap=cmap[v], vmin=vmin[v], vmax=vmax[v])                
            if n == num_sources-1:
                plt.colorbar(img, cax=cax[v])
                ax.set_yticks([])
            if v == 0:
                ax.set_xticklabels([])
            ax.set_title(source_titles[n], fontsize=14)
            if zmin is not None:
                ax.set_ylim([zmin, 0])
        plt.text(0.45, 0.97-0.49*v, var_titles[v]+' on '+bdry+' boundary, '+str(year)+'/'+str(month), fontsize=16, ha='center', va='center', transform=fig.transFigure)
    finished_plot(fig, fig_name=fig_name)
    

# Precompute the trend at every point in every ensemble member, for a bunch of variables. Split it into historical (1920-2005) and future (2006-2100).
def precompute_ensemble_trends (num_ens=5, base_dir='./', sim_dir=None, out_dir='precomputed_trends/', grid_dir='PAS_grid/'):

    var_names = ['UVEL', 'VVEL'] #['ismr', 'THETA', 'SALT', 'sst', 'sss', 'temp_btw_200_700m', 'salt_btw_200_700m', 'temp_below_700m', 'salt_below_700m', 'speed', 'SIfwfrz', 'SIfwmelt', 'SIarea', 'SIheff', 'EXFatemp', 'EXFaqh', 'EXFpreci', 'EXFuwind', 'EXFvwind', 'wind_speed', 'oceFWflx', 'thermocline', 'ADVx_TH', 'ADVy_TH']
    base_dir = real_dir(base_dir)
    out_dir = real_dir(out_dir)
    if sim_dir is None:
        sim_dir = [base_dir + 'PAS_LENS' + str(n+1).zfill(3) for n in range(num_ens)]
    else:
        num_ens = len(sim_dir)
    start_years = [1920, 2006]
    end_years = [2005, 2100]
    periods = ['historical', 'future']
    num_periods = len(periods)

    for var in var_names:
        if var == 'ismr':
            region = 'ice'
        else:
            region = 'all'
        if var in ['THETA', 'SALT', 'speed', 'ADVx_TH', 'ADVy_TH', 'UVEL', 'VVEL']:
            dim = 3
        else:
            dim = 2
        for t in range(num_periods):
            print('Calculating '+periods[t]+' trends in '+var)
            out_file = out_dir + var + '_trend_' + periods[t] + '.nc'
            make_trend_file(var, region, sim_dir, grid_dir, out_file, dim=dim, start_year=start_years[t], end_year=end_years[t])


# Plot the historical and future trends in each lat-lon variable.
def plot_trend_maps (trend_dir='precomputed_trends/', grid_dir='PAS_grid/', fig_dir='./'):

    var_names = ['ismr', 'sst', 'sss', 'temp_btw_200_700m', 'salt_btw_200_700m', 'temp_below_700m', 'salt_below_700m', 'SIfwfrz', 'SIfwmelt', 'SIarea', 'SIheff', 'EXFatemp', 'EXFaqh', 'EXFpreci', 'EXFuwind', 'EXFvwind', 'wind_speed', 'oceFWflx', 'thermocline']
    trend_dir = real_dir(trend_dir)
    fig_dir = real_dir(fig_dir)
    grid = Grid(grid_dir)
    start_years = [1920, 2006]
    end_years = [2005, 2100]
    periods = ['historical', 'future']
    num_periods = len(periods)
    p0 = 0.05

    for var in var_names:
        for zoom in [True, False]:
            if zoom:
                ymax = -70
                file_tail = '_zoom.png'
                if var in ['sst', 'sss', 'SIfwfrz', 'SIfwmelt', 'SIarea', 'SIheff', 'EXFatemp', 'EXFaqh', 'EXFpreci', 'EXFuwind', 'EXFvwind', 'wind_speed']:
                    # No need to zoom in
                    continue
            else:
                ymax = None
                file_tail = '.png'
                if var in ['ismr', 'temp_btw_200_700m', 'salt_btw_200_700m', 'temp_below_700m', 'salt_below_700m', 'thermocline']:
                    # No need to zoom out
                    continue
            if var in ['SIfwmelt', 'oceFWflx']:
                xmin = -138
                xmax = -82
            else:
                xmin = None
                xmax = None
            data_plot = np.ma.empty([num_periods, grid.ny, grid.nx])
            for t in range(num_periods):
                file_path = trend_dir + var + '_trend_' + periods[t] + '.nc'
                trends, long_name, units = read_netcdf(file_path, var +'_trend', return_info=True)
                mean_trend = np.mean(trends, axis=0)
                t_val, p_val = ttest_1samp(trends, 0, axis=0)
                mean_trend[p_val > p0] = 0
                data_plot[t,:] = mean_trend*1e2
            vmin = np.amin([var_min_max(data_plot[t,:], grid, xmin=xmin, xmax=xmax, ymax=ymax)[0] for t in range(num_periods)])
            vmax = np.amax([var_min_max(data_plot[t,:], grid, xmin=xmin, xmax=xmax, ymax=ymax)[1] for t in range(num_periods)])
            fig, gs, cax = set_panels('1x2C1')
            for t in range(num_periods):
                ax = plt.subplot(gs[0,t])
                img = latlon_plot(data_plot[t,:], grid, ax=ax, make_cbar=False, ctype='plusminus', vmin=vmin, vmax=vmax, ymax=ymax, xmin=xmin, xmax=xmax, title=periods[t], titlesize=14)
                if t != 0:
                    ax.set_xticklabels([])
                    ax.set_yticklabels([])
            plt.colorbar(img, cax=cax, orientation='horizontal')
            plt.suptitle(long_name+' ('+units[:-2]+'/century)', fontsize=20)
            fig_name = fig_dir + var + '_trends' + file_tail
            finished_plot(fig, fig_name=fig_name)


# Plot historical and future temperature and salinity trends as a slice through any longitude.
def plot_ts_trend_slice (lon0, ymax=None, tmin=None, tmax=None, smin=None, smax=None, trend_dir='precomputed_trends/', grid_dir='PAS_grid/', fig_name=None):

    trend_dir = real_dir(trend_dir)
    grid = Grid(grid_dir)
    periods = ['historical', 'future']
    num_periods = len(periods)
    p0 = 0.05
    var_names = ['THETA_trend', 'SALT_trend']
    var_titles = [' temperature ('+deg_string+'C)', ' salinity (psu)']
    num_var = len(var_names)

    # Read dat and calculate significant mean trends
    mean_trends = np.ma.empty([num_var, num_periods, grid.nz, grid.ny, grid.nx])
    for v in range(num_var):
        for t in range(num_periods):
            file_path = trend_dir + var_names[v] + '_' + periods[t] + '.nc'
            trends = read_netcdf(file_path, var_names[v])*1e2
            mean_trend_tmp = np.mean(trends, axis=0)
            t_val, p_val = ttest_1samp(trends, 0, axis=0)
            mean_trend_tmp[p_val > p0] = 0
            mean_trends[v,t,:] = mean_trend_tmp
    # Prepare patches and values for slice plots
    values = []
    vmin = [tmin, smin]
    vmax = [tmax, smax]
    for v in range(num_var):
        for t in range(num_periods):
            if v==0 and t==0:
                patches, values_tmp, lon0, ymin, ymax, zmin, zmax, vmin_tmp, vmax_tmp, left, right, below, above = slice_patches(mean_trends[v,t,:], grid, lon0=lon0, hmax=ymax, return_bdry=True)
            else:
                values_tmp, vmin_tmp, vmax_tmp = slice_values(mean_trends[v,t,:], grid, left, right, below, above, ymin, ymax, zmin, zmax, lon0=lon0)
            values.append(values_tmp)
            if vmin[v] is None:
                vmin[v] = vmin_tmp
            elif (v==0 and tmin is None) or (v==1 and smin is None):
                vmin[v] = min(vmin[v], vmin_tmp)
            if vmax[v] is None:
                vmax[v] = vmax_tmp
            elif (v==0 and tmax is None) or (v==1 and smax is None):
                vmax[v] = max(vmax[v], vmax_tmp)

    # Plot
    fig, gs, cax1, cax2 = set_panels('2x2C2')
    cax = [cax1, cax2]
    extend = [get_extend(vmin=tmin, vmax=tmax), get_extend(vmin=smin, vmax=smax)]
    for v in range(num_var):
        for t in range(num_periods):
            ax = plt.subplot(gs[v,t])
            img = make_slice_plot(patches, values[v*num_periods+t], lon0, ymin, ymax, zmin, zmax, vmin[v], vmax[v], lon0=lon0, ax=ax, make_cbar=False, ctype='plusminus', title=None)
            if v==0 and t==0:
                ax.set_ylabel('Depth (m)', fontsize=10)
            else:
                ax.set_xticklabels([])
                ax.set_yticklabels([])
                ax.set_xlabel('')
                ax.set_ylabel('')
            ax.set_title(periods[t] + var_titles[v], fontsize=14)
        plt.colorbar(img, cax=cax[v], extend=extend[v])
    plt.suptitle('Trends per century through '+lon_label(lon0), fontsize=16)
    finished_plot(fig, fig_name=fig_name)


# Recreate the PACE advection trend map for the historical and future trends in LENS, side by side - now using velocity not advection
def plot_velocity_trend_maps (z0=-400, trend_dir='precomputed_trends/', grid_dir='PAS_grid/', fig_name=None):

    trend_dir = real_dir(trend_dir)
    grid = Grid(grid_dir)
    p0 = 0.05
    threshold = [0, 0]
    z_shelf = -1000
    periods = ['historical', 'future']
    num_periods = len(periods)
    ymax = -70
    vmax = 1000

    dV = interp_to_depth(grid.dV, z0, grid)
    bathy = grid.bathy
    bathy[grid.lat_2d < -74.2] = 0
    bathy[(grid.lon_2d > -125)*(grid.lat_2d < -73)] = 0
    bathy[(grid.lon_2d > -110)*(grid.lat_2d < -72)] = 0
    
    def read_component (key, period):
        var_name = key+'VEL' 
        trends_3d = read_netcdf(trend_dir+var_name+'_'+period+'.nc', var_name)
        trends = interp_to_depth(trends_3d, z0, grid, time_dependent=True)
        mean_trend = np.mean(trends, axis=0)
        t_val, p_val = ttest_1samp(trends, 0, axis=0)
        mean_trend[p_val > p0] = 0
        if key == 'U': 
            gtype = 'u'
            dh = grid.dx_s
        elif key == 'V':
            gtype = 'v'
            dh = grid.dy_w
        trend_interp = interp_grid(mean_trend, grid, gtype, 't')
        #trend_convert = trend_interp*Cp_sw*rhoConst*dh/dV*1e2*1e-3
        return trend_interp  #trend_convert
    magnitude_trend = np.ma.empty([num_periods, grid.ny, grid.nx])
    uvel_trend = np.ma.empty([num_periods, grid.ny, grid.nx])
    vvel_trend = np.ma.empty([num_periods, grid.ny, grid.nx])
    for t in range(num_periods):
        uvel_trend_tmp = read_component('U', periods[t])
        vvel_trend_tmp = read_component('V', periods[t])
        magnitude_trend[t,:] = np.sqrt(uvel_trend_tmp**2 + vvel_trend_tmp**2)
        index = magnitude_trend[t,:] < threshold[t]
        uvel_trend[t,:] = np.ma.masked_where(index, uvel_trend_tmp)
        vvel_trend[t,:] = np.ma.masked_where(index, vvel_trend_tmp)

    fig, gs, cax = set_panels('1x2C1')
    for t in range(num_periods):
        ax = plt.subplot(gs[0,t])
        img = latlon_plot(magnitude_trend[t,:], grid, ax=ax, make_cbar=False, ctype='plusminus', ymax=ymax, title=periods[t], titlesize=14, vmax=vmax)
        ax.contour(grid.lon_2d, grid.lat_2d, bathy, levels=[z_shelf], colors=('blue'), linewidths=1)
        overlay_vectors(ax, uvel_trend[t,:], vvel_trend[t,:], grid, chunk_x=9, chunk_y=6, scale=1e4, headwidth=4, headlength=5)
        if t > 0:
            ax.set_xticklabels([])
            ax.set_yticklabels([])
    plt.colorbar(img, cax=cax, extend='max', orientation='horizontal')
    plt.suptitle('Trends in ocean velocity at '+str(-z0)+r'm (m/s/century)', fontsize=18)
    finished_plot(fig, fig_name=fig_name)


# Helper function to read and correct the LENS velocity variables (ocean or sea ice) for OBCS: correction in polar coordinates with respect to SOSE climatology
def read_correct_lens_vel_polar_coordinates (domain, bdry, ens, year, in_dir='/data/oceans_output/shelf/kaight/CESM_bias_correction/obcs/', obcs_dir='/data/oceans_output/shelf/kaight/ics_obcs/PAS/', mit_grid_dir='/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/', return_raw=False, return_clim=False, return_sose_clim=False):

    if domain == 'oce':
        var_names = ['UVEL', 'VVEL']
        var_sose = ['uvel', 'vvel']
    elif domain == 'ice':
        var_names = ['uvel', 'vvel']
        var_sose = ['uice', 'vice']
    num_cmp = len(var_names)
    lens_file_head = real_dir(in_dir) + 'LENS_climatology_'
    lens_file_tail = '_1998-2017'
    sose_file_head = real_dir(obcs_dir) + 'OB' + bdry
    sose_file_tail = '_sose.bin'
    sose_file_tail_alt = '_sose_corr.bin'
    scale_cap = 3

    # Read grids
    # Will do almost everything on the MITgcm tracer grid - introduces negligible errors
    mit_grid = Grid(mit_grid_dir)
    hfac = []  # Get on all 3 grids
    for gtype in ['t', 'u', 'v']:
        hfac_tmp = get_hfac_bdry(mit_grid, bdry)
        if domain == 'ice':
            hfac_tmp = hfac_tmp[0,:]
        hfac_tmp = add_time_dim(hfac_tmp, months_per_year)
        hfac.append(hfac_tmp)
    loc0 = find_obcs_boundary(mit_grid, bdry)[0]
    lens_grid_file = find_cesm_file('LENS', var_names[0], domain, 'monthly', ens, year)[0]
    if domain == 'oce':
        lens_lon, lens_lat, lens_z, lens_nx, lens_ny, lens_nz = read_pop_grid(lens_grid_file, return_ugrid=True)[2:]
    elif domain == 'ice':
        lens_lon, lens_lat, lens_nx, lens_ny = read_cice_grid(lens_grid_file, return_ugrid=True)[2:]
        lens_z = None
        lens_nz = 1
    if bdry in ['N', 'S']:
        direction = 'lat'
        dimensions = 'x'
        lens_h_2d = lens_lon
        mit_h = mit_grid.lon_1d
    elif bdry in ['E', 'W']:
        direction = 'lon'
        dimensions = 'y'
        lens_h_2d = lens_lat
        mit_h = mit_grid.lat_1d
    if domain == 'oce':
        dimensions += 'z'
    dimensions += 't'
    i1, i2, c1, c2 = interp_slice_helper_nonreg(lens_lon, lens_lat, loc0, direction)
    lens_h_full = extract_slice_nonreg(lens_h_2d, direction, i1, i2, c1, c2)
    lens_h = trim_slice_to_grid(lens_h_full, lens_h_full, mit_grid, direction, warn=False)[0]
    lens_nh = lens_h.size

    # Read LENS u and v components and slice to boundary
    data_slice = []
    for v in range(num_cmp):
        file_path, t_start, t_end = find_cesm_file('LENS', var_names[v], domain, 'monthly', ens, year)
        data_full_cmp = read_netcdf(file_path, var_names[v], t_start=t_start, t_end=t_end)*1e-2
        data_slice_cmp = extract_slice_nonreg(data_full_cmp, direction, i1, i2, c1, c2)
        data_slice_cmp = trim_slice_to_grid(data_slice_cmp, lens_h_full, mit_grid, direction, warn=False)[0]
        data_slice.append(data_slice_cmp)
    try:
        lens_mask = np.invert(data_slice[0].mask[0,:])
    except(IndexError):
        lens_mask = np.ones(data_slice[0][0,:].shape)
    # Calculate magnitude and angle
    lens_magnitude = np.sqrt(data_slice[0]**2 + data_slice[1]**2)
    lens_angle = np.arctan2(data_slice[1], data_slice[0])

    # Read LENS climatology and calculate magnitude and angle
    data_clim = []
    for v in range(num_cmp):
        file_path = lens_file_head + var_names[v] + '_' + bdry + lens_file_tail
        data_clim.append(read_binary(file_path, [lens_nh, lens_nh, lens_nz], dimensions))
    lens_clim_magnitude = np.sqrt(data_clim[0]**2 + data_clim[1]**2)
    lens_clim_angle = np.arctan2(data_clim[1], data_clim[0])

    # Calculate scaling factor (subject to cap) and rotation angle (take mod 2pi when necessary)
    scale = np.minimum(lens_magnitude/lens_clim_magnitude, scale_cap)
    rotate = lens_angle - lens_clim_angle
    rotate[rotate < -np.pi] += 2*np.pi
    rotate[rotate > np.pi] -= 2*np.pi

    # Interpolate to MITgcm tracer grid
    shape = [months_per_year]
    if domain == 'oce':
        shape += [mit_grid.nz]
    shape += [mit_h.size]
    scale_interp = np.ma.zeros(shape)
    rotate_interp = np.ma.zeros(shape)
    for month in range(months_per_year):
        for in_data, out_data in zip([scale, rotate], [scale_interp, rotate_interp]):
            out_data[month,:] = interp_bdry(lens_h, lens_z, in_data[month,:], lens_mask, mit_h, mit_grid.z, hfac[0][0,:], lon=(direction=='lat'), depth_dependent=(domain=='oce'))

    # Read SOSE climatology and calculate magnitude and angle
    sose_clim = []
    for v in range(num_cmp):
        file_path = sose_file_head + var_sose[v]
        if (bdry=='N' and var_names[v]=='VVEL') or (bdry in ['E','W'] and var_names[v]=='UVEL'):
            file_path += sose_file_tail_alt
        else:
            file_path += sose_file_tail
        sose_clim_tmp = read_binary(file_path, [mit_grid.nx, mit_grid.ny, mit_grid.nz], dimensions)
        # Fill land mask on correct grid with zeros
        sose_clim_tmp[hfac[v+1]==0] = 0
        sose_clim.append(sose_clim_tmp)
    sose_magnitude = np.sqrt(sose_clim[0]**2 + sose_clim[1]**2)
    sose_angle = np.arctan2(sose_clim[1], sose_clim[0])

    # Now scale magnitude and rotate angle
    new_magnitude = sose_magnitude*scale_interp
    new_angle = sose_angle + rotate_interp
    # Convert back to u and v components
    new_u = new_magnitude*np.cos(new_angle)
    new_v = new_magnitude*np.sin(new_angle)

    return_vars = [new_u, new_v]
    if return_raw:
        return_vars += [data_slice[0], data_slice[1]]
    if return_clim:
        return_vars += [data_clim[0], data_clim[1]]
    if return_raw or return_clim:
        return_vars += [lens_h, lens_z]
    if return_sose_clim:
        return_vars += [sose_clim[0], sose_clim[1]]
    return return_vars


# For the given variable, boundary, ensemble member, year, and month: plot the uncorrected and corrected LENS fields as well as the SOSE climatology.
def plot_obcs_corrected_non_ts (var, bdry, ens, year, month, polar_coordinates=True, fig_name=None):

    if var == 'UVEL':
        var_title = 'Zonal velocity (m/s)'
    elif var == 'VVEL':
        var_title = 'Meridional velocity (m/s)'
    elif var == 'aice':
        var_title = 'Sea ice area (fraction)'
    elif var == 'hi':
        var_title = 'Sea ice thickness (m)'
    elif var == 'hs':
        var_title = 'Snow thickness (m)'
    elif var == 'uvel':
        var_title = 'Sea ice zonal velocity (m/s)'
    elif var == 'vvel':
        var_title = 'Sea ice meridional velocity (m/s)'
    if var in ['UVEL', 'VVEL']:
        domain = 'oce'
    else:
        domain = 'ice'
    if var in ['aice', 'hi', 'hs']:
        ctype = 'basic'
    else:
        ctype = 'plusminus'
    titles = ['SOSE climatology', 'LENS', 'LENS corrected']
    colours = ['blue', 'green', 'red']
    num_sources = len(titles)
    main_title = var_title+' at '+bdry+' boundary, '+str(year)+'/'+str(month)
    
    mit_grid_dir = '/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/'
    grid = Grid(mit_grid_dir)

    if polar_coordinates and var in ['UVEL', 'VVEL', 'uvel', 'vvel']:
        lens_corr_u, lens_corr_v, lens_uncorr_u, lens_uncorr_v, lens_h, lens_z, sose_clim_u, sose_clim_v = read_correct_lens_vel_polar_coordinates(domain, bdry, ens, year, return_raw=True, return_sose_clim=True)
        if var in ['UVEL', 'uvel']:
            lens_corr = lens_corr_u
            lens_uncorr = lens_uncorr_u
            sose_clim = sose_clim_u
        elif var in ['VVEL', 'vvel']:
            lens_corr = lens_corr_v
            lens_uncorr = lens_uncorr_v
            sose_clim = sose_clim_v
        if bdry in ['N', 'S']:
            mit_h = grid.lon_1d
        else:
            mit_h = grid.lat_1d
        mit_z = grid.z
    else:
        lens_corr, lens_uncorr, lens_h, lens_z, sose_clim, mit_h, mit_z = read_correct_lens_non_ts(var, bdry, ens, year, return_raw=True, return_sose_clim=True)
    data = [sose_clim, lens_uncorr, lens_corr]
    h = [mit_h, lens_h, mit_h]
    if domain == 'oce':               
        z = [mit_z, lens_z, mit_z]
        vmin = min(min(np.amin(sose_clim), np.amin(lens_uncorr)), np.amin(lens_corr))
        vmax = max(max(np.amax(sose_clim), np.amax(lens_uncorr)), np.amax(lens_corr))
        cmap = set_colours(data[0], vmin=vmin, vmax=vmax, ctype=ctype)[0]
        fig, gs, cax = set_panels('1x3C1')
        for n in range(num_sources):
            ax = plt.subplot(gs[0,n])
            img = ax.pcolormesh(h[n], z[n], data[n][month-1,:], cmap=cmap, vmin=vmin, vmax=vmax)
            if n==2:
                plt.colorbar(img, cax=cax, orientation='horizontal')
            if n>0:
                ax.set_yticklabels([])
            ax.set_title(titles[n], fontsize=14)
        plt.suptitle(main_title, fontsize=18)
    elif domain == 'ice':
        fig, ax = plt.subplots()
        for n in range(num_sources):
            ax.plot(h[n], data[n][month-1,:], color=colours[n], label=titles[n])
        ax.set_title(main_title, fontsize=16)
        ax.grid(linestyle='dotted')
        ax.legend()        
    finished_plot(fig, fig_name=fig_name)


def compare_bedmachine_mask (grid_dir, bedmachine_file='/data/oceans_input/raw_input_data/BedMachine/v2.0/BedMachineAntarctica_2020-07-15_v02.nc', fig_name=None):

    grid = Grid(grid_dir)
    x_mit, y_mit = polar_stereo(grid.lon_2d, grid.lat_2d, lat_c=-70)
    x_bm = read_netcdf(bedmachine_file, 'x')
    y_bm = read_netcdf(bedmachine_file, 'y')
    mask_bm = read_netcdf(bedmachine_file, 'mask')

    fig, ax = plt.subplots()
    ax.contourf(x_bm, y_bm, mask_bm)
    ax.set_xlim([-2e6, -1.25e6])
    ax.set_ylim([-7e5, -8e4])
    ax.scatter(x_mit, y_mit, grid.ice_mask, color='red')
    finished_plot(fig, fig_name=fig_name)


# Generate new XC, YC, XG, YG points for use in Ua base mesh generation.
def new_grid_points (nc_file, delY_file):

    import netCDF4 as nc

    lon_g, lat_g = latlon_points(-140, -80, -76, -62.3, 0.1, delY_file)
    lon_c = 0.5*(lon_g[:-1] + lon_g[1:])
    lat_c = 0.5*(lat_g[:-1] + lat_g[1:])
    lon_g = lon_g[:-1]
    lat_g = lat_g[:-1]
    nx = lon_c.size
    ny = lat_c.size

    id = nc.Dataset(nc_file, 'w')
    id.createDimension('YC', ny)
    id.createVariable('YC', 'f8', ('YC'))
    id.variables['YC'].long_name = 'latitude at cell center'
    id.variables['YC'].units = 'degrees_north'
    id.variables['YC'][:] = lat_c
    id.createDimension('YG', ny)
    id.createVariable('YG', 'f8', ('YG'))
    id.variables['YG'].long_name = 'latitude at SW corner'
    id.variables['YG'].units = 'degrees_north'
    id.variables['YG'][:] = lat_g
    id.createDimension('XC', nx)
    id.createVariable('XC', 'f8', ('XC'))
    id.variables['XC'].long_name = 'longitude at cell center'
    id.variables['XC'].units = 'degrees_east'
    id.variables['XC'][:] = lon_c
    id.createDimension('XG', nx)
    id.createVariable('XG', 'f8', ('XG'))
    id.variables['XG'].long_name = 'longitude at SW corner'
    id.variables['XG'].units = 'degrees_east'
    id.variables['XG'][:] = lon_g
    id.close()
    
    
    

            
        

    
    

    
