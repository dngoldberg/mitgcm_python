#######################################################
# Calculation of integral timeseries
#######################################################

import numpy as np

from io import read_netcdf
from utils import convert_ismr
from diagnostics import total_melt


# Calculate total mass loss or area-averaged melt rate from FRIS in the given NetCDF file. The default behaviour is to calculate the melt at each time index in the file, but you can also select a subset of time indices, and/or time-average - see optional keyword arguments. You can also split into positive (melting) and negative (freezing) components.

# Arguments:
# file_path: path to NetCDF file containing 'SHIfwFlx' variable
# grid = Grid object

# Optional keyword arguments:
# result: 'massloss' (default) calculates the total mass loss in Gt/y. 'meltrate' calculates the area-averaged melt rate in m/y.
# time_index, t_start, t_end, time_average: as in function read_netcdf
# mass_balance: if True, split into positive (melting) and negative (freezing) terms. Default False.

# Output:
# If time_index is set, or time_average=True: single value containing mass loss or average melt rate
# Otherwise: 1D array containing timeseries of mass loss or average melt rate
# If mass_balance=True: two values/arrays will be returned, with the positive and negative components.

def fris_melt (file_path, grid, result='massloss', time_index=None, t_start=None, t_end=None, time_average=False, mass_balance=False):

    # Read ice shelf melt rate and convert to m/y
    ismr = convert_ismr(read_netcdf(file_path, 'SHIfwFlx', time_index=time_index, t_start=t_start, t_end=t_end, time_average=time_average))

    if mass_balance:
        # Split into melting and freezing
        ismr_positive = np.maximum(ismr, 0)
        ismr_negative = np.minimum(ismr, 0)
    
    if time_index is not None or time_average:
        # Just one timestep
        if mass_balance:
            melt = total_melt(ismr_positive, grid.fris_mask, result=result)
            freeze = total_melt(ismr_negative, grid.fris_mask, result=result)
            return melt, freeze
        else:
            return total_melt(ismr, grid.fris_mask, grid, result=result)
    else:
        # Loop over timesteps
        num_time = ismr.shape[0]
        if mass_balance:
            melt = np.zeros(num_time)
            freeze = np.zeros(num_time)
            for t in range(num_time):
                melt[t] = total_melt(ismr_positive[t,:], grid.fris_mask, grid, result=result)
                freeze[t] = total_melt(ismr_negative[t,:], grid.fris_mask, grid, result=result)
            return melt, freeze
        else:
            melt = np.zeros(num_time)
            for t in range(num_time):
                melt[t] = total_melt(ismr[t,:], grid.fris_mask, grid, result=result)
            return melt

    
