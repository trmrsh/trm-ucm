#!/usr/bin/env python

"""
enables python access to ultracam ucm files

ULTRACAM stores frames in its own native binary format, which present a
high hurdle for one-off manipulations. This module allows you to read 
ULTRACAM frames into python where you can use standard python code to do 
what you want to the data and headers.

The headers are stored in an ordered dictionary keyed on the header parameter
name. Each parameter has a value, a comment and a type. The types refer to 
particular C++ data types and you are better off not changing them if possible.

example:

import trm.ucm

# read image
ucm = trm.ucm.rucm('image.ucm')

# subtract 10. from 2nd window of 3rd CCD
ucm[2][1] -= 10.

# dump result
ucm.write('image_new.ucm')


Classes
=======

Ucm     -- class to contain a ucm frame (multiple windows of multiple CCDs)

Functions
=========

rucm    -- read a ucm file and create a Ucm object

Dependencies
============

You must already have the trm.subs module.

"""

import sys
import struct
import numpy
import ppgplot
import trm.subs as subs
import trm.subs.cpp as cpp

class Ucm(subs.Odict):

    """
    Represents a Ucm file.

    Ucm is a sub-class of an Odict (ordered dictionary). The Odict is used to store
    the header while extra attributes store the data in numpy 2D arrays. The Odict is keyed
    on the header item name with '.' used to descend into directory hierarchys. So for instance,
    if you read a file as follows:

    flat = trm.ucm.rucm('flat.ucm')
    
    then

    flat['Site.Observatory'['value']

    will return the observatory name.

    Ucm objects have the following attributes:

    data  -- the data. data[nc][nw] is a 2D numpy array representing window nw of CCD nc (both starting
             from zero, C-style).
    off   -- window offsets. off[nc][nw] returns a tuple (llx,lly) representing the lower-left pixel position.
             of the respective window.
    xbin  -- X binning factor
    ybin  -- Y binning factor
    nxtot -- maximum X pixel
    nytot -- maximum Y pixel.
    """

    def __init__(self, head, data, off, xbin, ybin, nxtot, nytot):
        """
        Creates a Ucm file

        head  -- the header, a list with each entry a dictionary with the format
                 {'name' : name, 'value' : value, 'comment' : comment, 'type' : itype}
        data  -- list of list of numpy 2D arrays so that data[nc][nw] represents
                 window nw of CCD nc
        off   -- list of list of tuples such that off[nc][nw] has the form (llx,lly)
        xbin  -- x binning factor
        ybin  -- y binning factor
        nxtot -- maximum X dimension
        nytot -- maximum Y dimension
        """

        if head == None:
            super(Ucm, self)
        else:
            super(Ucm, self).__init__(head)

        self.data  = data
        self.off   = off
        self.xbin  = xbin
        self.ybin  = ybin
        self.nxtot = nxtot
        self.nytot = nytot

    def write(self, fname):
        """
        Writes out to disk in ucm format

        fname  -- file to write to.
        """    

        uf = open(fname, 'wb')
    
# write the format code
        magic = 47561009
        uf.write(struct.pack('i',magic))

# write the header, starting with the number of entries
        lmap = len(self)
        uf.write(struct.pack('i',lmap))

        for (key,val) in self.iteritems():

            cpp.write_string(uf, key)
            itype = val['type']
            uf.write(struct.pack('i',itype))
            cpp.write_string(uf, val['comment'])

            if itype == 0: # double
                uf.write(struct.pack('d', val['value']))
            elif itype == 1: # char
                raise Exception('Hitem: char not enabled')
            elif itype == 2: # int
                uf.write(struct.pack('i', val['value']))
            elif itype == 3: # uint
                raise Exception('Hitem: uint not enabled')
            elif itype == 4: # lint
                raise Exception('Hitem: linit not enabled')
            elif itype == 5: # ulint
                raise Exception('Hitem: ulint not enabled')
            elif itype == 6: # float
                uf.write(struct.pack('f', val['value']))
            elif itype == 7: # string
                cpp.write_string(uf, val['value'])
            elif itype == 8: # bool
                uf.write(struct.pack('B', val['value']))
            elif itype == 9: # directory
                pass
            elif itype == 10: # date
                raise Exception('Hitem: date not enabled')
            elif itype == 11: # time
                uf.write(struct.pack('i', val['value'][0]))
                uf.write(struct.pack('d', val['value'][1]))
            elif itype == 12: # position
                raise Exception('Hitem: position not enabled')
            elif itype == 13: # dvector
                raise Exception('Hitem: dvector not enabled')
            elif itype == 14: # uchar
                uf.write(struct.pack('c', val['value']))
            elif itype == 15: # telescope
                raise Exception('Hitem: telescope not enabled')

# number of CCDs
        nccd = len(self.data)
        uf.write(struct.pack('i', nccd))

        for nc in range(nccd):

# number of windows
            nwin = len(self.data[nc])
            uf.write(struct.pack('i', nwin))

            for nw in range(nwin):
                llx     = self.off[nc][nw][0]
                lly     = self.off[nc][nw][1]
                (ny,nx) = self.data[nc][nw].shape
                xbin    = self.xbin
                ybin    = self.ybin
                nxtot   = self.nxtot
                nytot   = self.nytot
                iout = 0
                uf.write(struct.pack('9i',llx,lly,nx,ny,xbin,ybin,nxtot,nytot,iout))
                numpy.cast['float32'](self.data[nc][nw]).tofile(uf)
        uf.close()

    def min(self, nccd):
        """
        Finds minimum value of CCD nccd (starts from 0)
        """
        if len(self.data[nccd]):
            mval = self.data[nccd][0].min()
            for nw in range(1,len(self.data[nccd])):
                mval = min(mval, self.data[nccd][nw].min())
        else:
            mval = 0.
        return mval

    def max(self, nccd):
        """
        Finds maximum value  of CCD nccd (starts from 0)
        """
        if len(self.data[nccd]):
            mval = self.data[nccd][0].max()
            for nw in range(1,len(self.data[nccd])):
                mval = max(mval, self.data[nccd][nw].max())
        else:
            mval = 0.
        return mval

    def pggray(self, nccd, imin, imax):
        """
        Plots a CCD using pgplot's pggray function.

        The plot should have been opened and setup.

        nccd   -- the CCD to plot (0,1,2 ...)
        imin   -- minimum intensity
        imax   -- maximum intensity
        """
        for nw in xrange(len(self.data[nccd])):
            (ny,nx) = self.data[nccd][nw].shape
            tr = numpy.empty((6),float)
            tr[0] = self.off[nccd][nw][0]-1
            tr[1] = self.xbin
            tr[2] = 0.
            tr[3] = self.off[nccd][nw][1]-1
            tr[4] = 0.
            tr[5] = self.ybin
            ppgplot.pggray(self.data[nccd][nw], nx, ny, 0, nx-1, 0, ny-1, imin, imax, tr)


def rucm(fname):
    """
    Read from disk in ucm format

    fname  -- file to write to.
    """    

    (uf,start_format) = cpp.open_ucm(fname)

# read the header
    (lmap,) = struct.unpack(start_format + 'i', uf.read(4))

    head = subs.Odict()
    for i in xrange(lmap):
        name = cpp.read_string(uf, start_format)
        (itype,) = struct.unpack(start_format + 'i', uf.read(4))
        comment = cpp.read_string(uf, start_format)

        if itype == 0: # double
            (value,) = struct.unpack(start_format + 'd', uf.read(8))
        elif itype == 1: # char
            raise Exception('Hitem: char not enabled')
        elif itype == 2: # int
            (value,) = struct.unpack(start_format + 'i', uf.read(4))
        elif itype == 3: # uint
            raise Exception('Hitem: uint not enabled')
        elif itype == 4: # lint
            raise Exception('Hitem: linit not enabled')
        elif itype == 5: # ulint
            raise Exception('Hitem: ulint not enabled')
        elif itype == 6: # float
            (value,) = struct.unpack(start_format + 'f', uf.read(4))
        elif itype == 7: # string
            value = cpp.read_string(uf, start_format)
        elif itype == 8: # bool
            (value,) = struct.unpack(start_format + 'B', uf.read(1))
        elif itype == 9: # directory
            value = None
        elif itype == 10: # date
            raise Exception('Hitem: date not enabled')
        elif itype == 11: # time
            (mjd,)  = struct.unpack(start_format + 'i', uf.read(4))
            (hour,) = struct.unpack(start_format + 'd', uf.read(8))
            value   = (mjd, hour)
        elif itype == 12: # position
            raise Exception('Hitem: position not enabled')
        elif itype == 13: # dvector
            raise Exception('Hitem: dvector not enabled')
        elif itype == 14: # uchar
            (value,) = struct.unpack(start_format + 'c', uf.read(1))
        elif itype == 15: # telescope
            raise Exception('Hitem: telescope not enabled')

# store header information
        head[name] = {'value' : value, 'comment' : comment, 'type' : itype}
        
# now for the data
    data  = []
    off   = []
        
# read number of CCDs
    (nccd,) = struct.unpack(start_format + 'i', uf.read(4))

    for nc in range(nccd):
# read number of wndows
        (nwin,) = struct.unpack(start_format + 'i', uf.read(4))
        ccd  = []
        coff = []
        for nw in range(nwin):
            (llx,lly,nx,ny,xbin,ybin,nxtot,nytot) = struct.unpack(start_format + '8i', uf.read(32))
            (iout,) = struct.unpack(start_format + 'i', uf.read(4))
            if iout == 0:
                win = numpy.fromfile(file=uf, dtype=numpy.float32, count=nx*ny)
            elif iout == 1:
                win = numpy.fromfile(file=uf, dtype=numpy.uint16, count=nx*ny)
                win = numpy.cast['float32'](win)
            else:
                raise Exception('Ultracam data output type iout = ' + str(iout) + ' not recognised')
            win = win.reshape((ny,nx))
            ccd.append(win)
            coff.append((llx, lly))

        data.append(ccd)
        off.append(coff)
    uf.close()

    return Ucm(head, data, off, xbin, ybin, nxtot, nytot)

# Test section if this is run as a script

if __name__ == '__main__':

    from ppgplot import *

    ucm = rucm('test.ucm')

    pgopen('/xs')
    pgvstd()
    pgwnad(0.,ucm.nxtot,0.,ucm.nytot)
    nccd = 0
    ucm.pggray(0,100000.,50000.)
    pgbox('bcnst',0.,0,'bcnst',0.,0)
    pgclos()

    ucm.data[0][1] *= 10.

    ucm.write('junk.ucm')




