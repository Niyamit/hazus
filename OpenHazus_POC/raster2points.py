import ogr, gdal, osr
import numpy as np
import itertools,os
from scipy.interpolate import interp1d

def raster2array(rasterfn):
    raster = gdal.Open(rasterfn)
    band = raster.GetRasterBand(1)
    array = band.ReadAsArray()
    return array

def array2point(array,rasterfn):
    raster = gdal.Open(rasterfn)
    return array
  
def main(rasterfn):
    array = raster2array(rasterfn)
    return array2point(array,rasterfn)