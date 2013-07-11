#!/usr/bin/env python

"""
enables Python access to ultracam ucm files

ULTRACAM stores frames in its own native binary format, which presents a
high hurdle for one-off manipulations. This module allows you to read 
ULTRACAM frames into python where you can use standard python code to do 
what you want to the data and headers.

The headers are stored in an ordered dictionary keyed on the header parameter
name. Each parameter has a value, a comment and a type. The types refer to 
particular C++ data types and you are better off not changing them if possible
(however, read further below if you want to).

Example:

import trm.ucm

# read image
ucm = trm.ucm.Ucm('image.ucm')

# subtract 10. from 2nd window of 3rd CCD
ucm[2][1] -= 10.

# dump result
ucm.write('image_new.ucm')

Headers:

The Ucm class is inherited from trm.subs.Odict, so you could set a new header item as
follows:

ucm['My.Header.Item'] = {'value' : 23.345, 'comment' : 'a test header item', 'type' : trm.ucm.ITYPE_DOUBLE}

The last one tells it what C++ data type to use; see below for a full list but note that not
all of them have been implemented. The times are a little subtle. You need to provide a 2 element tuple
with an integer MJD day number and a double representing the hour of the day and this is what you will
get back if you query a time header parameter (ITYPE_TIME).

Here is how you might set the standard UT_date time used by ULTRACAM:

ucm['UT_date']=  {'comment': 'UT at the centre of the exposure', 'type': trm.ucm.ITYPE_TIME, 'value': (53592, 2.5800921733025461)}

Classes
=======

Ucm     -- a class to contain a ucm frame (multiple windows of multiple CCDs)
Pgucm   -- a class derived from Ucm that knows to plot itself with PGPLOT
Mpucm   -- a class derived from Ucm that knows to plot itself with matplotlib

Third-party dependencies
========================

You must already have numpy (fairly standard) and my trm.subs module. matplotlib and ppgplot are needed
if you wish to use the plottable objects Mpucm and Pgucm, but not otherwise.

"""

import os.path, sys, struct, numpy
import trm.subs as subs
import trm.subs.cpp as cpp

# Integer type numbers
ITYPE_DOUBLE    = 0
ITYPE_CHAR      = 1
ITYPE_INT       = 2
ITYPE_UINT      = 3
ITYPE_LINT      = 4
ITYPE_ULINT     = 5
ITYPE_FLOAT     = 6
ITYPE_STRING    = 7
ITYPE_BOOL      = 8
ITYPE_DIR       = 9
ITYPE_DATE      = 10
ITYPE_TIME      = 11
ITYPE_POSITION  = 12
ITYPE_DVECTOR   = 13
ITYPE_UCHAR     = 14
ITYPE_TELESCOPE = 15
ITYPE_USINT     = 16
ITYPE_IVECTOR   = 17
ITYPE_FVECTOR   = 18

# ucm magic number
MAGIC           = 47561009

def _check_ucm(fobj):
    """
    Check a file opened for reading in binary mode to see if it is a ucm.

    Returns endian which is a string to be passed
    to later routines indicating endian-ness. 
    """

    # read the format code
    fbytes = fobj.read(4)
    (fcode,) = struct.unpack('i',fbytes)
    if fcode != MAGIC:
        (fcode,) = struct.unpack('>i',fbytes)
        if fcode != MAGIC:
            fobj.close()
            raise CppError('_open_ucm: could not recognise first 4 bytes of ' + fname + ' as a ucm file')
        endian = '>'
    else:
        endian = ''
    return endian


class Ucm(subs.Odict):

    """
    Represents a Ucm file.

    Ucm is a sub-class of an Odict (ordered dictionary). The Odict is used to store
    the header while extra attributes store the data in numpy 2D arrays. The Odict is keyed
    on the header item name with '.' used to descend into directory hierarchies. So for instance,
    if you read a file as follows:

    flat = trm.ucm.rucm('flat.ucm')
    
    then

    flat['Site.Observatory']['value']

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

    They have been kept deliberately simple otherwise and don't have much functionality.
    """

    def __init__(self, *args):
        """
        Creates a Ucm file

        Two ways to call:

        One argument:

          fnoro -- reads in from a file name or a file object

        Seven arguments:

          head  -- the header, an ordered dictionary keyed on the header name with each entry 
                   being a dictionary with the format:

                   {'value' : value, 'comment' : comment, 'type' : itype}

                   The name can be made hierarchical by using '.'. e.g. entries with
                   names 'Detector', 'Detector.Name' and 'Detector.Type' would create
                   a directory and two sub-items in uinfo.

          data  -- list of list of numpy 2D arrays so that data[nc][nw] represents
                   window nw of CCD nc

          off   -- list of list of tuples such that off[nc][nw] has the form (llx,lly)

          xbin  -- x binning factor

          ybin  -- y binning factor

          nxtot -- maximum X dimension

          nytot -- maximum Y dimension
        """

        if len(args) == 1:
            head, data, off, xbin, ybin, nxtot, nytot = _rucm(args[0])
        elif len(args) == 7:
            head, data, off, xbin, ybin, nxtot, nytot = args
        else:
            raise TypeError('ucm.Ucm(): takes 1 or 7 arguments; ' + str(len(args)) + 'were given.')

        if head == None:
            subs.Odict.__init__(self)
        else:
            subs.Odict.__init__(self, head)
        
        self.data  = data
        self.off   = off
        self.xbin  = xbin
        self.ybin  = ybin
        self.nxtot = nxtot
        self.nytot = nytot

    def __eq__(self, other):
        """
        Equality operator based on file formats: same number of CCDs,
        same number of windows per CCD, sqame binning factors etc. 
        """

        if type(other) is type(self):

            if self.nccd() != other.nccd(): return False
            if self.xbin != other.xbin or self.ybin != other.ybin: return False
            if self.nxtot != other.nxtot or self.nytot != other.nytot: return False
            for nc in range(self.nccd()):
                if self.nwin(nc) != other.nwin(nc): return False
                for nw in range(self.nwin(nc)):
                    (ny1,nx1) = self.nxy(nc,nw)
                    (ny2,nx2) = other.nxy(nc,nw)
                    if nx1 != nx2 or ny1 != ny2: return False
                    (llx1,lly1) = self.off[nc][nw]
                    (llx2,lly2) = other.off[nc][nw]
                    if llx1 != llx2 or lly1 != lly2: return False
            return True
        else:
            return NotImplemented

    def __ne__(self, other):
        """
        Inequality operator based on file formats: same number of CCDs,
        same number of windows per CCD, same binning factors etc. 
        """
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def nccd(self):
        "Returns number of CCDs"
        return len(self.data)

    def nwin(self, nc):
        "Returns number of windows of CCD nc (starting from 0)"
        return len(self.data[nc])

    def win(self, nc, nw):
        "Returns window number nw of CCD nc (starting from 0)"
        return self.data[nc][nw]

    def nxy(self, nc, nw):
        "Returns (ny,nx) tuple of pixels dimensions of window number nw of CCD nc (starting from 0)"
        return self.win(nc,nw).shape

    def write(self, fname):
        """
        Writes out to disk in ucm format

        fname  -- file to write to. '.ucm' will be appended if necessary.
        """    

        if not fname.strip().endswith('.ucm'):
            fname = fname.strip() + '.ucm'
        uf = open(fname, 'wb')
    
        # write the format code
        uf.write(struct.pack('i',MAGIC))

        # write the header, starting with the number of entries
        lmap = len(self)
        uf.write(struct.pack('i',lmap))

        for (key,val) in self.iteritems():

            cpp.write_string(uf, key)
            itype = val['type']
            uf.write(struct.pack('i',itype))
            cpp.write_string(uf, val['comment'])

            if itype == ITYPE_DOUBLE:
                uf.write(struct.pack('d', val['value']))
            elif itype == ITYPE_CHAR:
                raise Exception('Hitem: char not enabled')
            elif itype == ITYPE_INT:
                uf.write(struct.pack('i', val['value']))
            elif itype == ITYPE_UINT:
                uf.write(struct.pack('I', val['value']))
            elif itype == ITYPE_LINT:
                raise Exception('Hitem: linit not enabled')
            elif itype == ITYPE_ULINT:
                raise Exception('Hitem: ulint not enabled')
            elif itype == ITYPE_FLOAT:
                uf.write(struct.pack('f', val['value']))
            elif itype == ITYPE_STRING:
                cpp.write_string(uf, val['value'])
            elif itype == ITYPE_BOOL:
                uf.write(struct.pack('B', val['value']))
            elif itype == ITYPE_DIR:
                pass
            elif itype == ITYPE_DATE:
                raise Exception('Hitem: date not enabled')
            elif itype == ITYPE_TIME:
                uf.write(struct.pack('i', val['value'][0]))
                uf.write(struct.pack('d', val['value'][1]))
            elif itype == ITYPE_POSITION:
                raise Exception('Hitem: position not enabled')
            elif itype == ITYPE_DVECTOR:
                uf.write(struct.pack('i', len(val['value'])))
                uf.write(struct.pack(str(len(val['value']))+'d', *val['value']))
            elif itype == ITYPE_UCHAR:
                uf.write(struct.pack('c', val['value']))
            elif itype == ITYPE_TELESCOPE:
                raise Exception('Hitem: telescope not enabled')
            elif itype == ITYPE_USINT:
                uf.write(struct.pack('H', val['value']))
            elif itype == ITYPE_IVECTOR:
                uf.write(struct.pack('i', len(val['value'])))
                uf.write(struct.pack(str(len(val['value']))+'i', *val['value']))
            elif itype == ITYPE_FVECTOR:
                uf.write(struct.pack('i', len(val['value'])))
                uf.write(struct.pack(str(len(val['value']))+'f', *val['value']))
            else:
                raise Exception('Hitem: type =' + str(itype) + 'not recognised')

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
        print "ERROR: Ucm.pggray now deprectaed. Please use Pgucm instead"
        exit(1)

class Pgucm(Ucm):
    """
    Plottable version of a Ucm using pgplot.
    """
    import ppgplot

#    def __init__(self, *args):
#       Ucm.__init__(self, *args)
        
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
            ppgplot.pggray(self.data[nccd][nw], 0, nx-1, 0, ny-1, imin, imax, tr)

class Mpucm(Ucm):
    """
    Plottable version of a Ucm using matplotlib
    """

    from matplotlib.pyplot import cm

    def imshow(self, nccd, imin=None, imax=None, cmap=cm.jet):
        """
        Plots a CCD using matplotlib's imshow function.

        nccd   -- the CCD to plot (0,1,2 ...)
        imin   -- minimum intensity (default = minimum of image)
        imax   -- maximum intensity (default = maximum of image)
        cmap   -- colour map (defaults to cm.jet)
        """

        import matplotlib.pyplot as plt

        if imin is None:
            imin = self.min(nccd)
        if imax is None:
            imax = self.max(nccd)
        for nw in xrange(len(self.data[nccd])):
            ny,nx   = self.data[nccd][nw].shape
            llx,lly = self.off[nccd][nw]
            plt.imshow(self.data[nccd][nw], cmap, origin='lower', interpolation='nearest', \
                           extent=(llx-0.5,llx+nx-0.5,lly-0.5,lly+ny-0.5),vmin=imin,vmax=imax)
        plt.xlim(0.,self.nxtot)
        plt.ylim(0.,self.nytot)


def rucm(dummy):
    print 'ucm.rucm now deprecated. Please use Ucm constructors.'
    exit(1)

def _rucm(fnoro):
    """
    Read ucm file from disk

    fnoro  -- either a string containing the name of the file to read from ('.ucm' 
              will be appended if necessary), or a file object opened for reading
              in binary mode. The file is closed on exiting the routine.

    Returns head, data, off, xbin, ybin, nxtot, nytot as needed to construct a Ucm
    """    

    # Assume it is a file object, if that fails, assume it is
    # the name of a file.
    try:
        uf = fnoro
        start_format =  _check_ucm(uf)
    except AttributeError, err:
        uf = open(fnoro, 'rb')
        start_format =  _check_ucm(uf)

    # read the header
    (lmap,) = struct.unpack(start_format + 'i', uf.read(4))

    head = subs.Odict()
    for i in xrange(lmap):
        name = cpp.read_string(uf, start_format)
        (itype,) = struct.unpack(start_format + 'i', uf.read(4))
        comment = cpp.read_string(uf, start_format)

        if itype == ITYPE_DOUBLE:
            (value,) = struct.unpack(start_format + 'd', uf.read(8))
        elif itype == ITYPE_CHAR:
            raise Exception('Hitem: char not enabled')
        elif itype == ITYPE_INT:
            (value,) = struct.unpack(start_format + 'i', uf.read(4))
        elif itype == ITYPE_UINT:
            (value,) = struct.unpack(start_format + 'I', uf.read(4))
        elif itype == ITYPE_LINT:
            raise Exception('Hitem: linit not enabled')
        elif itype == ITYPE_ULINT:
            raise Exception('Hitem: ulint not enabled')
        elif itype == ITYPE_FLOAT:
            (value,) = struct.unpack(start_format + 'f', uf.read(4))
        elif itype == ITYPE_STRING:
            value = cpp.read_string(uf, start_format)
        elif itype == ITYPE_BOOL:
            (value,) = struct.unpack(start_format + 'B', uf.read(1))
        elif itype == ITYPE_DIR:
            value = None
        elif itype == ITYPE_DATE:
            raise Exception('Hitem: date not enabled')
        elif itype == ITYPE_TIME:
            (mjd,)  = struct.unpack(start_format + 'i', uf.read(4))
            (hour,) = struct.unpack(start_format + 'd', uf.read(8))
            value   = (mjd, hour)
        elif itype == ITYPE_POSITION:
            raise Exception('Hitem: position not enabled')
        elif itype == ITYPE_DVECTOR:
            (nvec,) = struct.unpack(start_format + 'i', uf.read(4))
            value = struct.unpack(start_format + str(nvec) + 'd', uf.read(8*nvec))
        elif itype == ITYPE_UCHAR:
            (value,) = struct.unpack(start_format + 'c', uf.read(1))
        elif itype == ITYPE_TELESCOPE: # telescope
            raise Exception('Hitem: telescope not enabled')
        elif itype == ITYPE_USINT:
            (value,) = struct.unpack(start_format + 'H', uf.read(2))
        elif itype == ITYPE_IVECTOR:
            (nvec,) = struct.unpack(start_format + 'i', uf.read(4))
            value = struct.unpack(start_format + str(nvec) + 'i', uf.read(4*nvec))
        elif itype == ITYPE_FVECTOR:
            (nvec,) = struct.unpack(start_format + 'i', uf.read(4))
            value = struct.unpack(start_format + str(nvec) + 'f', uf.read(4*nvec))

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

    return head, data, off, xbin, ybin, nxtot, nytot



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




