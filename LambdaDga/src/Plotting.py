# ------------------------------------------------ COMMENTS ------------------------------------------------------------


# -------------------------------------------- IMPORT MODULES ----------------------------------------------------------
import numpy as np
import itertools
import matplotlib
import os
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import FourPoint as fp
from mpl_toolkits.axes_grid1 import make_axes_locatable
# -------------------------------------- DEFINE MODULE WIDE VARIABLES --------------------------------------------------

# __markers__ = itertools.cycle(('o','s','v','8','v','^','<','>','p','*','h','H','+','x','D','d','1','2','3','4'))
__markers__ = ('o', 's', 'v', '8', 'v', '^', '<', '>', 'p', '*', 'h', 'H', '+', 'x', 'D', 'd', '1', '2', '3', '4')


# ----------------------------------------------- FUNCTIONS ------------------------------------------------------------

def plot_susc(susc=None):
    plt.plot(susc.iw_core, susc.mat.real, 'o')
    plt.xlim([-2, susc.beta])
    plt.xlabel(r'$\omega$')
    plt.ylabel(r'\chi')
    plt.show()


def plot_fp(fp: fp.LocalFourPoint = None, w_plot=0, name='', niv_plot=-1):
    if (niv_plot == -1):
        niv_plot = fp.niv
    A = fp
    plt.imshow(
        A.mat[A.iw == w_plot, A.niv - niv_plot:A.niv + niv_plot, A.niv - niv_plot:A.niv + niv_plot].squeeze().real,
        cmap='RdBu', extent=[-niv_plot, niv_plot, -niv_plot, niv_plot])
    plt.colorbar()
    plt.title(name + '-' + A.channel + '(' + r'$ \omega=$' + '{})'.format(w_plot))
    plt.xlabel(r'$\nu\prime$')
    plt.ylabel(r'$\nu$')
    plt.show()


def plot_tp(tp: fp.LocalThreePoint = None, niv_cut=-1, name=''):
    if (niv_cut == -1):
        niv_cut = tp.niv
    A = tp
    plt.imshow(A.mat.real[:, tp.niv - niv_cut:tp.niv + niv_cut], cmap='RdBu',
               extent=[-niv_cut, niv_cut, A.iw[0], A.iw[-1]])
    plt.colorbar()
    plt.title(r'$\Re$' + name + '-' + A.channel)
    plt.xlabel(r'$\nu$')
    plt.ylabel(r'$\omega$')
    plt.show()

    plt.imshow(A.mat.imag[:, tp.niv - niv_cut:tp.niv + niv_cut], cmap='RdBu',
               extent=[A.iw[0], A.iw[-1], -niv_cut, niv_cut])
    plt.colorbar()
    plt.title(r'$\Im$' + name + '-' + A.channel)
    plt.xlabel(r'$\nu$')
    plt.ylabel(r'$\omega$')
    plt.show()


def plot_chiw(wn_list=None, chiw_list=None, labels_list=None, channel=None, plot_dir=None, niw_plot=20):
    markers = __markers__
    np = len(wn_list)
    assert np < len(markers), 'More plot-lines requires, than markers available.'

    size = 2 * np + 1

    for i in range(len(wn_list)):
        plt.plot(wn_list[i], chiw_list[i].real, markers[i], ms=size - 2 * i, label=labels_list[i])
    plt.legend()
    plt.xlim(-2,niw_plot)
    plt.xlabel(r'$\omega$')
    plt.ylabel(r'$\chi_{}$'.format(channel))
    if (plot_dir is not None):
        plt.savefig(plot_dir + 'chiw_{}.png'.format(channel))
    try:
        plt.show()
    except:
        plt.close()

def plot_siw(vn_list=None, siw_list=None, labels_list=None, plot_dir=None, niv_plot=200, name='siw_check', ncol=1):
    markers = __markers__
    np = len(vn_list)
    assert np < len(markers), 'More plots-lines requires, than markers avaiable.'

    size = 2

    plt.subplot(211)
    for i in range(len(vn_list)):
        plt.plot(vn_list[i], siw_list[i].real, markers[i], ms=size, label=labels_list[i])
    plt.legend()
    plt.xlim([0, niv_plot])
    plt.xlabel(r'$\omega$')
    plt.ylabel(r'$\Re \Sigma$')
    plt.subplot(212)
    for i in range(len(vn_list)):
        plt.plot(vn_list[i], siw_list[i].imag, markers[i], ms=size, label=labels_list[i])
    plt.xlim([0, niv_plot])
    plt.legend(ncol=ncol)
    plt.xlabel(r'$\omega$')
    plt.ylabel(r'$\Im \Sigma$')
    if (plot_dir is not None):
        plt.savefig(plot_dir + '{}.png'.format(name))

    plt.close()


def plot_siwk_fs(siwk=None, plot_dir=None, kgrid=None, do_shift=False, kz=0,niv_plot=None):
    fig, ax = plot_fs(siwk=siwk, kgrid=kgrid, do_shift=do_shift, kz=kz,niv_plot=niv_plot)
    ax[0].set_title('$\Re \Sigma$')
    ax[1].set_title('$\Im \Sigma$')

    if (plot_dir is not None):
        plt.savefig(plot_dir + 'siwk_fermi_surface.png'.format(kz,niv_plot))
    try:
        plt.show()
    except:
        plt.close()

def plot_giwk_fs(giwk=None, plot_dir=None, kgrid=None, do_shift=False, kz=0, niv_plot=None, name=''):
    fig, ax = plot_fs(siwk=giwk, kgrid=kgrid, do_shift=do_shift, kz=kz, niv_plot=niv_plot)
    ax[0].set_title('$\Re G$')
    ax[1].set_title('$\Im G$')

    if (plot_dir is not None):
        plt.savefig(plot_dir + 'giwk_fermi_surface_{}.png'.format(name))
    try:
        plt.show()
    except:
        plt.close()

def plot_fs(siwk=None, kgrid=None, do_shift=False, kz=0,niv_plot=None):
    if(niv_plot==None):
        niv_plot = np.shape(siwk)[-1] // 2

    siwk_plot = np.copy(siwk)
    kx = kgrid._grid['kx']
    ky = kgrid._grid['ky']
    if(do_shift):
        siwk_plot = np.roll(siwk_plot,kgrid.nk[0]//2,0)
        siwk_plot = np.roll(siwk_plot,kgrid.nk[1]//2,1)
        kx = kx - np.pi
        ky = ky - np.pi



    fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(10,5))
    im = ax[0].imshow(siwk_plot[:,:,kz,niv_plot].real,cmap='RdBu', extent=[kx[0],kx[-1],ky[0],ky[-1]], origin='lower')
    divider = make_axes_locatable(ax[0])
    cax = divider.append_axes('right', size='5%', pad=0.05)
    fig.colorbar(im, cax=cax, orientation='vertical')
    ax[0].set_xlabel(r'$k_x$')
    ax[0].set_ylabel(r'$k_y$')

    im = ax[1].imshow(siwk_plot[:,:,kz,niv_plot].imag,cmap='RdBu', extent=[kx[0],kx[-1],ky[0],ky[-1]], origin='lower')
    divider = make_axes_locatable(ax[1])
    cax = divider.append_axes('right', size='5%', pad=0.05)
    fig.colorbar(im, cax=cax, orientation='vertical')
    ax[1].set_xlabel(r'$k_x$')
    ax[1].set_ylabel(r'$k_y$')

    plt.tight_layout()

    return fig, ax


def plot_gap_function(delta=None, pdir = None, name='', kgrid=None, do_shift=False):
    niv = np.shape(delta)[-1] // 2
    kx = kgrid._grid['kx']
    ky = kgrid._grid['ky']

    delta_plot = np.copy(delta)
    if(do_shift):
        delta_plot = np.roll(delta,kgrid.nk[0]//2,0)
        delta_plot = np.roll(delta,kgrid.nk[1]//2,1)
        kx = kx - np.pi
        ky = ky - np.pi

    fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(10,5))

    # First positive Matsubara frequency:

    im = ax[0].imshow(delta_plot[:, :, 0, niv].real, cmap='RdBu', origin='lower', extent=[kx[0],kx[-1],ky[0],ky[-1]])
    divider = make_axes_locatable(ax[0])
    cax = divider.append_axes('right', size='5%', pad=0.05)
    fig.colorbar(im, cax=cax, orientation='vertical')

    # First negative Matsubara frequency:
    im = ax[1].imshow(delta_plot[:, :, 0, niv-1].real, cmap='RdBu', origin='lower', extent=[kx[0],kx[-1],ky[0],ky[-1]])
    divider = make_axes_locatable(ax[1])
    cax = divider.append_axes('right', size='5%', pad=0.05)
    fig.colorbar(im, cax=cax, orientation='vertical')


    ax[0].set_xlabel(r'$k_x$')
    ax[0].set_ylabel(r'$k_y$')
    ax[0].set_title(r'$\nu_{n=0}$')

    ax[1].set_xlabel(r'$k_x$')
    ax[1].set_ylabel(r'$k_y$')
    ax[1].set_title(r'$\nu_{n=-1}$')

    plt.savefig(pdir + 'GapFunction_{}.png'.format(name))
    plt.close()