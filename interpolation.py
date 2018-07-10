#######################################################
# All things interpolation
#######################################################

import numpy as np
import sys
from scipy.interpolate import RectBivariateSpline, RegularGridInterpolator, interp2d, interp1d

from utils import mask_land, mask_land_zice, mask_3d, xy_to_xyz, z_to_xyz


# Interpolate from one grid type to another. Currently only u-grid to t-grid and v-grid to t-grid are supported.

# Arguments:
# data: array of dimension (maybe time) x (maybe depth) x lat x lon
# grid: Grid object
# gtype_in: grid type of "data". As in function Grid.get_lon_lat.
# gtype_out: grid type to interpolate to

# Optional keyword arguments:
# time_dependent: as in function apply_mask
# mask_shelf: indicates to mask the ice shelves as well as land. Only valid if "data" isn't depth-dependent.

# Output: array of the same dimension as "data", interpolated to the new grid type

def interp_grid (data, grid, gtype_in, gtype_out, time_dependent=False, mask_shelf=False):

    # Figure out if the field is depth-dependent
    if (time_dependent and len(data.shape)==4) or (not time_dependent and len(data.shape)==3):
        depth_dependent=True
    else:
        depth_dependent=False
    # Make sure we're not trying to mask the ice shelf from a depth-dependent field
    if mask_shelf and depth_dependent:
        print "Error (interp_grid): can't set mask_shelf=True for a depth-dependent field."
        sys.exit()

    if gtype_in in ['u', 'v', 'psi', 'w']:
        # Fill the mask with zeros (okay because no-slip boundary condition)
        data_tmp = np.copy(data)
        data_tmp[data.mask] = 0.0
    else:
        # Tracer land mask is the least restrictive, so it doesn't matter what the masked values are - they will definitely get re-masked at the end.
        data_tmp = data

    # Interpolate
    data_interp = np.empty(data_tmp.shape)
    if gtype_in == 'u' and gtype_out == 't':
        # Midpoints in the x direction
        data_interp[...,:-1] = 0.5*(data_tmp[...,:-1] + data_tmp[...,1:])
        # Extend the easternmost column
        data_interp[...,-1] = data_tmp[...,-1]
    elif gtype_in == 'v' and gtype_out == 't':
        # Midpoints in the y direction
        data_interp[...,:-1,:] = 0.5*(data_tmp[...,:-1,:] + data_tmp[...,1:,:])
        # Extend the northernmost row
        data_interp[...,-1,:] = data_tmp[...,-1,:]
    else:
        print 'Error (interp_grid): interpolation from the ' + gtype_in + '-grid to the ' + gtype_out + '-grid is not yet supported'
        sys.exit()

    # Now apply the mask
    if depth_dependent:
        data_interp = mask_3d(data_interp, grid, gtype=gtype_out, time_dependent=time_dependent)
    else:
        if mask_shelf:
            data_interp = mask_land_zice(data_interp, grid, gtype=gtype_out, time_dependent=time_dependent)
        else:
            data_interp = mask_land(data_interp, grid, gtype=gtype_out, time_dependent=time_dependent)

    return data_interp


# Finds the value of the given array to the west, east, south, north of every point, as well as which neighbours are non-missing, and how many neighbours are non-missing.
def neighbours (data, missing_val=-9999):

    # Find the value to the west, east, south, north of every point
    # Just copy the boundaries
    data_w = np.empty(data.shape)
    data_w[...,1:] = data[...,:-1]
    data_w[...,0] = data[...,0]
    data_e = np.empty(data.shape)
    data_e[...,:-1] = data[...,1:]
    data_e[...,-1] = data[...,-1]
    data_s = np.empty(data.shape)
    data_s[...,1:,:] = data[...,:-1,:]
    data_s[...,0,:] = data[...,0,:]
    data_n = np.empty(data.shape)
    data_n[...,:-1,:] = data[...,1:,:]
    data_n[...,-1,:] = data[...,-1,:]     
    # Arrays of 1s and 0s indicating whether these neighbours are non-missing
    valid_w = (data_w != missing_val).astype(float)
    valid_e = (data_e != missing_val).astype(float)
    valid_s = (data_s != missing_val).astype(float)
    valid_n = (data_n != missing_val).astype(float)
    # Number of valid neighbours of each point
    num_valid_neighbours = valid_w + valid_e + valid_s + valid_n

    return data_w, data_e, data_s, data_n, valid_w, valid_e, valid_s, valid_n, num_valid_neighbours


# Like the neighbours function, but in the vertical dimension: neighbours above and below
def neighbours_z (data, missing_val=-9999):

    data_u = np.empty(data.shape)
    data_u[...,1:,:,:] = data[...,:-1,:,:]
    data_u[...,0,:,:] = data[...,0,:,:]
    data_d = np.empty(data.shape)
    data_d[...,:-1,:,:] = data[...,1:,:,:]
    data_d[...,-1,:,:] = data[...,-1,:,:]
    valid_u = (data_u != missing_val).astype(float)
    valid_d = (data_d != missing_val).astype(float)
    num_valid_neighbours_z = valid_u + valid_d
    return data_u, data_d, valid_u, valid_d, num_valid_neighbours_z

    
# Given an array with missing values, extend the data into the mask by setting missing values to the average of their non-missing neighbours, and repeating as many times as the user wants.
# If "data" is a regular array with specific missing values, set missing_val (default -9999). If "data" is a MaskedArray, set masked=True instead.
# Setting use_3d=True indicates this is a 3D array, and where there are no valid neighbours on the 2D plane, neighbours above and below should be used.
def extend_into_mask (data, missing_val=-9999, masked=False, use_3d=False, num_iters=1):

    if missing_val != -9999 and masked:
        print "Error (extend_into_mask): can't set a missing value for a masked array"
        sys.exit()

    if masked:
        # MaskedArrays will mess up the extending
        # Unmask the array and fill the mask with missing values
        data_unmasked = data.data
        data_unmasked[data.mask] = missing_val
        data = data_unmasked

    for iter in range(num_iters):
        # Find the neighbours of each point, whether or not they are missing, and how many non-missing neighbours there are
        data_w, data_e, data_s, data_n, valid_w, valid_e, valid_s, valid_n, num_valid_neighbours = neighbours(data, missing_val=missing_val)
        # Choose the points that can be filled
        index = (data == missing_val)*(num_valid_neighbours > 0)
        # Set them to the average of their non-missing neighbours
        data[index] = (data_w[index]*valid_w[index] + data_e[index]*valid_e[index] + data_s[index]*valid_s[index] + data_n[index]*valid_n[index])/num_valid_neighbours[index]
        if use_3d:
            # Consider vertical neighbours too
            data_d, data_u, valid_d, valid_u, num_valid_neighbours_z = neighbours_z(data, missing_val=missing_val)
            # Find the points that haven't already been filled based on 2D neighbours, but could be filled now
            index = (data == missing_val)*(num_valid_neighbours == 0)*(num_valid_neighbours_z > 0)
            data[index] = (data_u[index]*valid_u[index] + data_d[index]*valid_d[index])/num_valid_neighbours_z[index]

    if masked:
        # Remask the MaskedArray
        data = ma.masked_where(data==missing_val, data)

    return data


# Interpolate a topography field "data" (eg bathymetry, ice shelf draft, mask) to grid cells. We want the area-averaged value over each grid cell. So it's not enough to just interpolate to a point (because the source data might be much higher resolution than the new grid) or to average all points within the cell (because the source data might be lower or comparable resolution). Instead, interpolate to a finer grid within each grid cell (default 10x10) and then average over these points.

# Arguments:
# x, y: 1D arrays with x and y coordinates of source data (polar stereographic for BEDMAP2, lon and lat for GEBCO)
# data: 2D array of source data
# x_interp, y_interp: 2D arrays with x and y coordinates of the EDGES of grid cells - the output array will be 1 smaller in each dimension

# Optional keyword argument:
# n_subgrid: dimension of finer grid within each grid cell (default 10, i.e. 10 x 10 points per grid cell)

# Output: data on centres of new grid

def interp_topo (x, y, data, x_interp, y_interp, n_subgrid=10):

    # x_interp and y_interp are the edges of the grid cells, so the number of cells is 1 less
    num_j = y_interp.shape[0] -1
    num_i = x_interp.shape[1] - 1
    data_interp = np.empty([num_j, num_i])

    # RectBivariateSpline needs (y,x) not (x,y) - this can really mess you up when BEDMAP2 is square!!
    interpolant = RectBivariateSpline(y, x, data)

    # Loop over grid cells (can't find a vectorised way to do this without overflowing memory)
    for j in range(num_j):
        for i in range(num_i):
            # Make a finer grid within this grid cell (regular in x and y)
            # First identify the boundaries so that x and y are strictly increasing
            if x_interp[j,i] < x_interp[j,i+1]:
                x_start = x_interp[j,i]
                x_end = x_interp[j,i+1]
            else:
                x_start = x_interp[j,i+1]
                x_end = x_interp[j,i]
            if y_interp[j,i] < y_interp[j+1,i]:
                y_start = y_interp[j,i]
                y_end = y_interp[j+1,i]
            else:
                y_start = y_interp[j+1,i]
                y_end = y_interp[j,i]
            # Define edges of the sub-cells
            x_edges = np.linspace(x_start, x_end, num=n_subgrid+1)
            y_edges = np.linspace(y_start, y_end, num=n_subgrid+1)
            # Calculate centres of the sub-cells
            x_vals = 0.5*(x_edges[1:] + x_edges[:-1])
            y_vals = 0.5*(y_edges[1:] + y_edges[:-1])
            # Interpolate to the finer grid, then average over those points to estimate the mean value of the original field over the entire grid cell
            data_interp[j,i] = np.mean(interpolant(y_vals, x_vals))

    return data_interp


# Given an array representing a mask (e.g. ocean mask where 1 is ocean, 0 is land), identify any isolated cells (i.e. 1 cell of ocean with land on 4 sides) and remove them (i.e. recategorise them as land).
def remove_isolated_cells (data, mask_val=0):

    num_valid_neighbours = neighbours(data, missing_val=mask_val)[-1]
    index = (data!=mask_val)*(num_valid_neighbours==0)
    print '...' + str(np.count_nonzero(index)) + ' isolated cells'
    data[index] = mask_val
    return data


# Interpolate a field on a regular MITgcm grid, to another regular MITgcm grid. Anything outside the bounds of the source grid will be filled with fill_value.
# source_grid and target_grid can be either Grid or SOSEGrid objects.
# Set dim=3 for 3D fields (xyz), dim=2 for 2D fields (xy).
def interp_reg (source_grid, target_grid, source_data, dim=3, gtype='t', fill_value=-9999):

    # Get the correct lat and lon on the source grid
    source_lon, source_lat = source_grid.get_lon_lat(gtype=gtype, dim=1)
    # Build an interpolant
    if dim == 2:
        interpolant = RegularGridInterpolator((source_lat, source_lon), source_data, bounds_error=False, fill_value=fill_value)
    elif dim == 3:
        interpolant = RegularGridInterpolator((-source_grid.z, source_lat, source_lon), source_data, bounds_error=False, fill_value=fill_value)
    else:
        print 'Error (interp_reg): dim must be 2 or 3'
        sys.exit()

    # Get the correct lat and lon on the target grid
    target_lon, target_lat = target_grid.get_lon_lat(gtype=gtype, dim=1)
    # Make 1D axes 2D
    lon_2d, lat_2d = np.meshgrid(target_lon, target_lat)
    if dim == 2:        
        # Interpolate
        data_interp = interpolant((lat_2d, lon_2d))
    elif dim == 3:
        # Make all axes 3D
        lon_3d = xy_to_xyz(lon_2d, target_grid)
        lat_3d = xy_to_xyz(lat_2d, target_grid)
        z_3d = z_to_xyz(target_grid.z, target_grid)
        data_interp = interpolant((-z_3d, lat_3d, lon_3d))
    
    return data_interp


# Given data on a 3D grid (or 2D if you set use_3d=False), throw away any points indicated by the "discard" boolean mask (i.e. fill them with missing_val), and then extrapolate into any points indicated by the "fill" boolean mask (by calling extend_into_mask as many times as needed).
def discard_and_fill (data, discard, fill, missing_val=-9999, use_3d=True):

    # First throw away the points we don't trust
    data[discard] = missing_val
    # Now fill the values we need to fill
    num_missing = np.count_nonzero((data==missing_val)*fill)
    while num_missing > 0:
        print '......' + str(num_missing) + ' points to fill'
        data = extend_into_mask(data, missing_val=missing_val, use_3d=use_3d)
        num_missing_old = num_missing
        num_missing = np.count_nonzero((data==missing_val)*fill)
        if num_missing == num_missing_old:
            print 'Error (discard_and_fill): some missing values cannot be filled'
            sys.exit()
    return data


# Given a monotonically increasing 1D array "data", and a scalar value "val0", find the indicies i1, i2 and interpolation coefficients c1, c2 such that c1*data[i1] + c2*data[i2] = val0.
# If the array is longitude and there is the possibility of val0 in the gap between the periodic boundary, set lon=True.
def interp_slice_helper (data, val0, lon=False):

    # Find the first index greater than val0
    i2 = np.nonzero(data > val0)[0][0]
    # Find the last index less than val0
    if i2 > 0:
        # General case
        i1 = i2 - 1
    elif lon and i2==0 and data[-1]-360 < val0:
        # Longitude wraps around
        i1 = data.size - 1
        c2 = (val0 - (data[i1]-360))/(data[i2] - (data[i1]-360))
        c1 = 1 - c2
        return i1, i2, c1, c2
    else:
        print 'Error (interp_helper): ' + str(val0) + ' is out of bounds'
        sys.exit()
    # Calculate the weighting coefficients
    c2 = (val0 - data[i1])/(data[i2] - data[i1])
    c1 = 1 - c2
    return i1, i2, c1, c2


def interp_bdry (source_h, source_z, source_data, target_h, target_z, target_hfac, depth_dependent=False):

    if depth_dependent:
        # Mesh the source axes
        source_h, source_z = np.meshgrid(source_h, source_z)

    # Remove masked values
    source_h = source_h[~source_data.mask]
    source_data = source_data[~source_data.mask]
    if depth_dependent:
        source_z = source_z[~source_z.mask]

    # Interpolate
    if depth_dependent:
        interpolant = interp2d(source_h, source_z, source_data, kind='linear', bounds_error=False)
        data_interp = interpolant(target_h, target_z)
    else:
        data_interp = interpolant(target_h)

    # Fill the land mask with zeros
    data_interp[target_hfac==0] = 0

    return data_interp
        

        
        
    
    

    
