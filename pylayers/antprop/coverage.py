"""

Class Coverage
==============

.. autosummary::
    :toctree: generated/

    Coverage.__init__
    Coverage.__repr__
    Coverage.creategrid
    Coverage.cover
    Coverage.showEd
    Coverage.showPower
    Coverage.showTransistionRegion
    Coverage.showLoss

"""
from pylayers.util.project import *
import pylayers.util.pyutil as pyu
from pylayers.util.utilnet import str2bool
from pylayers.gis.layout import Layout
import pylayers.antprop.multiwall as mw
import pylayers.signal.standard as std

import matplotlib.cm  as cm

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as m
from mpl_toolkits.axes_grid1 import make_axes_locatable
import ConfigParser
import pdb

class Coverage(object):
    """ Handle Layout Coverage

        Methods
        -------

        creategrid()
            create a uniform grid for evaluating losses
        cover()
            run the coverage calculation
        showPower()
            display the map of received power
        showLoss()
            display the map of losses


        Attributes
        ----------

        All attributes are read from fileini ino the ini directory of the
        current project

        _fileini
            default coverage.ini

        L :  a Layout
        nx    : number of point on x
        ny    : number of point on y
        tx    : transmitter position
        txpe  : transmitter power emmission level
        show  : boolean for automatic display power map

    """


    def __init__(self,_fileini='coverage-new.ini'):
        """

        Parameters
        ----------

        _fileini : string
            name of the configuration file

        Notes
        -----

        Coverage is described in an ini file.
        Default file is coverage.ini and is placed in the ini directory of the current project.

        """


        self.config = ConfigParser.ConfigParser()
        self.config.read(pyu.getlong(_fileini,pstruc['DIRSIMUL']))

        self.layoutopt = dict(self.config.items('layout'))
        self.gridopt = dict(self.config.items('grid'))
        self.apopt = dict(self.config.items('ap'))
        self.rxopt = dict(self.config.items('rx'))
        self.showopt = dict(self.config.items('show'))

        # get the Layout
        self.L = Layout(self.layoutopt['filename'])

        # get the grid
        self.nx = eval(self.gridopt['nx'])
        self.ny = eval(self.gridopt['ny'])
        self.ng = self.nx*self.ny
        self.mode = eval(self.gridopt['full'])
        self.boundary = eval(self.gridopt['boundary'])

        self.dap = {}
        for k in self.apopt:
            kwargs  = eval(self.apopt[k])
            ap = std.AP(**kwargs)
            self.dap[eval(k)]=ap

        self.nt = len(self.dap)

        # AP section
        #self.fGHz = eval(self.txopt['fghz'])
        #self.tx = np.array((eval(self.txopt['x']),eval(self.txopt['y'])))
        #self.ptdbm = eval(self.txopt['ptdbm'])
        #self.framelengthbytes = eval(self.txopt['framelengthbytes'])

        # receiver section
        self.rxsens = eval(self.rxopt['sensitivity'])
        kBoltzmann = 1.3806503e-23
        self.bandwidthmhz = eval(self.rxopt['bandwidthmhz'])
        self.temperaturek = eval(self.rxopt['temperaturek'])
        self.noisefactordb = eval(self.rxopt['noisefactordb'])

        # Evaluate Noise Power (in dBm)

        Pn = (10**(self.noisefactordb/10.)+1)*kBoltzmann*self.temperaturek*self.bandwidthmhz*1e3
        self.pndbm = 10*np.log10(Pn)+60

        # show section
        self.show = str2bool(self.showopt['show'])

        try:
            self.L.Gt.nodes()
        except:
            pass
        try:
            self.L.dumpr()
        except:
            self.L.build()
            self.L.dumpw()

        self.creategrid(full=self.mode,boundary=self.boundary)


    def __repr__(self):
        """ representation
        """
        st=''
        st = st+ 'Layout file : '+self.L.filename + '\n\n'
        st = st + '-----list of Access Points ------'+'\n'
        for k in self.dap:
            st = st + self.dap[k].__repr__()
        st = st + '-----Rx------'+'\n'
        st= st+ 'rxsens (dBm) : '+ str(self.rxsens) + '\n'
        st= st+ 'bandwith (Mhz) : '+ str(self.bandwidthmhz) + '\n'
        st= st+ 'temperature (K) : '+ str(self.temperaturek) + '\n'
        st= st+ 'noisefactor (dB) : '+ str(self.noisefactordb) + '\n\n'
        st = st + '--- Grid ----'+'\n'
        st= st+ 'nx : ' + str(self.nx) + '\n'
        st= st+ 'ny : ' + str(self.ny) + '\n'
        st= st+ 'full grid : ' + str(self.mode) + '\n'
        st= st+ 'boundary (xmin,ymin,xmax,ymax) : ' + str(self.boundary) + '\n\n'
        return(st)

    def creategrid(self,full=True,boundary=[]):
        """ create a grid

        Parameters
        ----------

        full : boolean
            default (True) use all the layout area
        boundary : (xmin,ymin,xmax,ymax)
            if full is False the boundary argument is used

        """

        if full:
            mi=np.min(self.L.Gs.pos.values(),axis=0)+0.01
            ma=np.max(self.L.Gs.pos.values(),axis=0)-0.01
        else:
            assert boundary<>[]
            mi = np.array([boundary[0],boundary[1]])
            ma = np.array([boundary[2],boundary[3]])

        x = np.linspace(mi[0],ma[0],self.nx)
        y = np.linspace(mi[1],ma[1],self.ny)

        self.grid=np.array((list(np.broadcast(*np.ix_(x, y)))))



    def cover(self):
        """ run the coverage calculation

        Parameters
        ----------

        lay_bound : bool
            If True, the coverage is performed only inside the Layout
            and clip the values of the grid chosen in coverage.ini

        Examples
        --------

        .. plot::
            :include-source:

            >>> from pylayers.antprop.coverage import *
            >>> C = Coverage()
            >>> C.cover()
            >>> C.showPower()

        Notes
        -----

        self.fGHz is an array it means that coverage is calculated at once
        for a whole set of frequencies. In practice the center frequency of a
        given standard channel.

        This function is calling `Losst` which calculates Losses along a
        straight path. In a future implementation we will
        abstract the EM solver in order to make use of other calculation
        approaches as full or partial Ray Tracing.

        The following members variables are evaluated :

        + freespace Loss @ fGHz   PL()  PathLoss (shoud be rename FS as free space) $
        + prdbmo : Received power in dBm .. math:`P_{rdBm} =P_{tdBm} - L_{odB}`
        + prdbmp : Received power in dBm .. math:`P_{rdBm} =P_{tdBm} - L_{pdB}`
        + snro : SNR polar o (H)
        + snrp : SNR polar p (H)

        See Also
        --------

        pylayers.antprop.multiwall.Losst
        pylayers.antprop.multiwall.PL

        """

        self.Lwo,self.Lwp,self.Edo,self.Edp = mw.Losst(self.L,self.fGHz,self.grid.T,self.tx)
        self.freespace = mw.PL(self.fGHz,self.grid,self.tx)

        self.prdbmo = self.ptdbm - self.freespace - self.Lwo
        self.prdbmp = self.ptdbm - self.freespace - self.Lwp
        self.snro = self.prdbmo - self.pndbm
        self.snrp = self.prdbmp - self.pndbm

    def sinr(self):
        """ run the sinr coverage calculation

        Parameters
        ----------

        lay_bound : bool
            If True, the coverage is performed only inside the Layout
            and clip the values of the grid chosen in coverage.ini

        Examples
        --------

        .. plot::
            :include-source:

            >>> from pylayers.antprop.coverage import *
            >>> C = Coverage()
            >>> C.sinr()
            >>> C.showsinr()

        Notes
        -----

        self.fGHz is an array it means that coverage is calculated at once
        for a whole set of frequencies. In practice the center frequency of a
        given standard channel.

        This function is calling `Losst` which calculates Losses along a
        straight path. In a future implementation we will
        abstract the EM solver in order to make use of other calculation
        approaches as full or partial Ray Tracing.

        The following members variables are evaluated :

        + freespace Loss @ fGHz   PL()  PathLoss (shoud be rename FS as free space) $
        + prdbmo : Received power in dBm .. math:`P_{rdBm} =P_{tdBm} - L_{odB}`
        + prdbmp : Received power in dBm .. math:`P_{rdBm} =P_{tdBm} - L_{pdB}`
        + snro : SNR polar o (H)
        + snrp : SNR polar p (H)

        See Also
        --------

        pylayers.antprop.multiwall.Losst
        pylayers.antprop.multiwall.PL

        """
        from itertools import product


        Nf = np.shape(self.fGHz)
        Ng = np.shape(self.grid)
        Nt = np.shape(self.tx)

        # creating all links (could be done outside, temporary)
        p = product(range(Ng),range(Nt))
        for k in p:
            p1 = Tx[k[0],0:2]
            p2 = Rx[k[1]+1,0:2]
            try:
                tp1 = np.vstack((tp1,p1))
            except:
                tp1 = p1
                try:
                    tp2 = np.vstack((tp2,p2))
                except:
                    tp2 = p2

        Lwo,Lwp,Edo,Edp = mw.Losst(self.L,self.fGHz,tp1.T,tp2.T,dB=False)

        self.Lwo = Lwo.reshape(Nf,Ng,Nt)
        self.Lwp = Lwp.reshape(Nf,Ng,Nt)

        freespace = mw.PL(self.fGHz,tp1.T,tp2.T,dB=False)
        freespace = np.reshape(Nf,Ng,Nt)

        # Warning we are assuming here all transmitter have the same
        # transmitting power (to be modified)

        ComW = 10**(self.ptdbm/10.)*Lwo*freespace

        CpmW = 10**(self.ptdbm/10.)*Lwp*freespace

        U = (np.ones((Nt,Nt))-np.eye(Nt))[np.newaxis,np.newaxis,:,:]

        I = np.einsum('ijkl,ijl->ijk',U,C)
        self.SINRo = ComW/(I+N)
        self.SINRp = CpmW/(I+N)



    def showEd(self,polar='o',**kwargs):
        """ shows a map of direct path excess delay

        Parameters
        ----------

        polar : string
        'o' | 'p'

        Examples
        --------

        .. plot::
            :include-source:

            >>> from pylayers.antprop.coverage import *
            >>> C = Coverage()
            >>> C.cover()
            >>> C.showEd(polar='o')

        """

        if not kwargs.has_key('alphacy'):
            kwargs['alphacy']=0.0
        if not kwargs.has_key('colorcy'):
            kwargs['colorcy']='w'
        if not kwargs.has_key('nodes'):
            kwargs['nodes']=False

        fig,ax = self.L.showG('s',**kwargs)
        l = self.grid[0,0]
        r = self.grid[-1,0]
        b = self.grid[0,1]
        t = self.grid[-1,-1]

        cdict = {
        'red'  :  ((0., 0.5, 0.5), (1., 1., 1.)),
        'green':  ((0., 0.5, 0.5), (1., 1., 1.)),
        'blue' :  ((0., 0.5, 0.5), (1., 1., 1.))
        }
        #generate the colormap with 1024 interpolated values
        my_cmap = m.colors.LinearSegmentedColormap('my_colormap', cdict, 1024)

        if polar=='o':
            prdbm=self.prdbmo
        if polar=='p':
            prdbm=self.prdbmp



        if polar=='o':
            mcEdof = np.ma.masked_where(prdbm < self.rxsens,self.Edo)

            cov=ax.imshow(mcEdof.reshape((self.nx,self.ny)).T,
                             extent=(l,r,b,t),cmap = 'jet',
                             origin='lower')



            # cov=ax.imshow(self.Edo.reshape((self.nx,self.ny)).T,
            #           extent=(l,r,b,t),
            #           origin='lower')
            titre = "Map of LOS excess delay, polar orthogonal"

        if polar=='p':
            mcEdpf = np.ma.masked_where(prdbm < self.rxsens,self.Edp)

            cov=ax.imshow(mcEdpf.reshape((self.nx,self.ny)).T,
                             extent=(l,r,b,t),cmap = 'jet',
                             origin='lower')

            # cov=ax.imshow(self.Edp.reshape((self.nx,self.ny)).T,
            #           extent=(l,r,b,t),
            #           origin='lower')
            titre = "Map of LOS excess delay, polar parallel"

        ax.scatter(self.tx[0],self.tx[1],linewidth=0)
        ax.set_title(titre)

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)
        clb = fig.colorbar(cov,cax)
        clb.set_label('excess delay (ns)')

        if self.show:
            plt.show()
        return fig,ax

    def showPower(self,rxsens=True,nfl=True,polar='o',**kwargs):
        """ show the map of received power

        Parameters
        ----------

        rxsens : bool
              clip the map with rx sensitivity set in self.rxsens
        nfl : bool
              clip the map with noise floor set in self.pndbm
        polar : string
            'o'|'p'

        Examples
        --------

        .. plot::
            :include-source:

            >>> from pylayers.antprop.coverage import *
            >>> C = Coverage()
            >>> C.cover()
            >>> C.showPower()

        """

        if not kwargs.has_key('alphacy'):
            kwargs['alphacy']=0.0
        if not kwargs.has_key('colorcy'):
            kwargs['colorcy']='w'
        if not kwargs.has_key('nodes'):
            kwargs['nodes']=False
        fig,ax = self.L.showG('s',**kwargs)

        l = self.grid[0,0]
        r = self.grid[-1,0]
        b = self.grid[0,1]
        t = self.grid[-1,-1]

        if polar=='o':
            prdbm=self.prdbmo
        if polar=='p':
            prdbm=self.prdbmp

#        tCM = plt.cm.get_cmap('jet')
#        tCM._init()
#        alphas = np.abs(np.linspace(.0,1.0, tCM.N))
#        tCM._lut[:-3,-1] = alphas

        title='Map of received power - Pt = ' + str(self.ptdbm) + ' dBm'+str(' fGHz =') + str(self.fGHz) + ' polar = '+polar

        cdict = {
        'red'  :  ((0., 0.5, 0.5), (1., 1., 1.)),
        'green':  ((0., 0.5, 0.5), (1., 1., 1.)),
        'blue' :  ((0., 0.5, 0.5), (1., 1., 1.))
        }

        if not kwargs.has_key('cmap'):
        # generate the colormap with 1024 interpolated values
            cmap = m.colors.LinearSegmentedColormap('my_colormap', cdict, 1024)
        else:
            cmap = kwargs['cmap']
        #my_cmap = cm.copper


        if rxsens :

            ## values between the rx sensitivity and noise floor
            mcPrf = np.ma.masked_where((prdbm > self.rxsens)
                                     & (prdbm < self.pndbm),prdbm)
            # mcPrf = np.ma.masked_where((prdbm > self.rxsens) ,prdbm)

            cov1 = ax.imshow(mcPrf.reshape((self.nx,self.ny)).T,
                             extent=(l,r,b,t),cmap = cm.copper,
                             vmin=self.rxsens,origin='lower')

            ### values above the sensitivity
            mcPrs = np.ma.masked_where(prdbm < self.rxsens,prdbm)
            cov = ax.imshow(mcPrs.reshape((self.nx,self.ny)).T,
                            extent=(l,r,b,t),
                            cmap = cmap,
                            vmin=self.rxsens,origin='lower')
            title=title + '\n black : Pr (dBm) < %.2f' % self.rxsens + ' dBm'

        else :
            cov=ax.imshow(prdbm.reshape((self.nx,self.ny)).T,
                          extent=(l,r,b,t),
                          cmap = cmap,
                          vmin=self.pndbm,origin='lower')

        if nfl:
            ### values under the noise floor
            ### we first clip the value below the noise floor
            cl = np.nonzero(prdbm<=self.pndbm)
            cPr = prdbm
            cPr[cl] = self.pndbm
            mcPruf = np.ma.masked_where(cPr > self.pndbm,cPr)
            cov2 = ax.imshow(mcPruf.reshape((self.nx,self.ny)).T,
                             extent=(l,r,b,t),cmap = 'binary',
                             vmax=self.pndbm,origin='lower')
            title=title + '\n white : Pr (dBm) < %.2f' % self.pndbm + ' dBm'


        ax.scatter(self.tx[0],self.tx[1],s=10,c='k',linewidth=0)

        ax.set_title(title)
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)
        clb = fig.colorbar(cov,cax)
        clb.set_label('Power (dBm)')

        if self.show:
            plt.show()

        return fig,ax


    def showTransistionRegion(self,polar='o'):
        """

        Notes
        -----

        See  : "Analyzing the Transitional Region in Low Power Wireless Links"
                Marco Zuniga and Bhaskar Krishnamachari

        Examples
        --------

        .. plot::
            :include-source:

            >>> from pylayers.antprop.coverage import *
            >>> C = Coverage()
            >>> C.cover()
            >>> C.showTransitionRegion()

        """

        frameLength = self.framelengthbytes

        PndBm = self.pndbm
        gammaU = 10*np.log10(-1.28*np.log(2*(1-0.9**(1./(8*frameLength)))))
        gammaL = 10*np.log10(-1.28*np.log(2*(1-0.1**(1./(8*frameLength)))))

        PrU = PndBm + gammaU
        PrL = PndBm + gammaL

        fig,ax = self.L.showGs()

        l = self.grid[0,0]
        r = self.grid[-1,0]
        b = self.grid[0,1]
        t = self.grid[-1,-1]

        if polar=='o':
            prdbm=self.prdbmo
        if polar=='p':
            prdbm=self.prdbmp

        zones = np.zeros(np.shape(prdbm))
        #pdb.set_trace()

        uconnected  = np.nonzero(prdbm>PrU)
        utransition = np.nonzero((prdbm < PrU)&(prdbm > PrL))
        udisconnected = np.nonzero(prdbm < PrL)

        zones[uconnected] = 1
        zones[utransition] = (prdbm[utransition]-PrL)/(PrU-PrL)
        cov = ax.imshow(zones.reshape((self.nx,self.ny)).T,
                             extent=(l,r,b,t),cmap = 'BuGn',origin='lower')

        title='PDR region'
        ax.scatter(self.tx[0],self.tx[1],linewidth=0)

        ax.set_title(title)
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)
        fig.colorbar(cov,cax)
        if self.show:
            plt.show()

    def show2(self):
        fig,ax = self.L.showGs()
        for k in self.dap:
            p = self.dap[k].p
            ax.plot(p[0],p[1],'or')

        return(fig,ax)

    def showLoss(self,polar='o',**kwargs):
        """ show losses map

        Parameters
        ----------

        polar : string
            'o'|'p'|'both'

        Examples
        --------

        .. plot::
            :include-source:

            >>> from pylayers.antprop.coverage import *
            >>> C = Coverage()
            >>> C.cover()
            >>> C.showLoss(polar='o')
            >>> C.showLoss(polar='p')
        """

        fig = plt.figure()
        fig,ax=self.L.showGs(fig=fig)

        # setting the grid

        l = self.grid[0,0]
        r = self.grid[-1,0]
        b = self.grid[0,1]
        t = self.grid[-1,-1]

        Lo = self.freespace+self.Lwo
        Lp = self.freespace+self.Lwp
        # orthogonal polarization
        if polar=='o':
            cov = ax.imshow(Lo.reshape((self.nx,self.ny)).T,
                            extent=(l,r,b,t),
                            origin='lower',
                            vmin = 40,
                            vmax = 130)
            str1 = 'Map of losses, orthogonal (V) polarization, fGHz='+str(self.fGHz)
            title = (str1)

        # parallel polarization
        if polar=='p':
            cov = ax.imshow(Lp.reshape((self.nx,self.ny)).T,
                            extent=(l,r,b,t),
                            origin='lower',
                            vmin = 40,
                            vmax = 130)
            str2 = 'Map of losses, orthogonal (V) polarization, fGHz='+str(self.fGHz)
            title = (str2)

        ax.scatter(self.tx[0],self.tx[1],s=10,c='k',linewidth=0)
        ax.set_title(title)

        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.05)
        clb = fig.colorbar(cov,cax)
        clb.set_label('Loss (dB)')

        if self.show:
            plt.show()



if (__name__ == "__main__"):
    C=Coverage()
    C.cover()
    C.showPower()
    C.showLoss(polar='o')
    C.showLoss(polar='p')
    C.showTransistionRegion(polar='o')
    C.showEd(polar='o')
#    C.L.dumpr()
#    sigar,sig=C.L.signature(C.grid[2],C.tx)

