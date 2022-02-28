# ------------------------------------------------ COMMENTS ------------------------------------------------------------


# -------------------------------------------- IMPORT MODULES ----------------------------------------------------------
from scipy.stats import gaussian_kde

import w2dyn_aux
import TwoPoint as tp
import copy
import numpy as np
import Indizes as ind
import MatsubaraFrequencies as mf
import Config as conf


# ----------------------------------------------- FUNCTIONS ------------------------------------------------------------

def cut_iv(mat=None, niv_cut=10):
    niv = mat.shape[-1] // 2
    assert (mat.shape[-1] == mat.shape[-2]), 'Last two dimensions of the array are not consistent'
    return mat[..., niv - niv_cut:niv + niv_cut, niv - niv_cut:niv + niv_cut]


def cut_iw(mat=None, niw_cut=0):
    assert mat.shape > 1, 'Matrix has to be reshaped to [qx,qy,qz,Niw] format.'
    niw = mat.shape[-1] // 2
    mat = mat[..., niw - niw_cut:niw + niw_cut + 1]
    return mat


def get_ggv(giw=None, niv_ggv=-1):
    niv = giw.shape[0] // 2
    if (niv_ggv == -1):
        niv_ggv = niv
    return giw[niv - niv_ggv:niv + niv_ggv][:, None] * giw[niv - niv_ggv:niv + niv_ggv][None, :]


def chir_from_g2(g2=None, ggv=None, beta=1.0, wn=0):
    if (ggv is not None and wn == 0):
        return beta * (g2 - 2. * ggv)
    else:
        return beta * g2


def get_ur(u=1.0, channel='dens'):
    if (channel == 'magn'):
        sign = -1
    elif (channel == 'dens'):
        sign = 1
    else:
        raise ValueError
    return u * sign


# ------------------------------------------------ OBJECTS -------------------------------------------------------------


# ======================================================================================================================
# ---------------------------------------------- LOCAL BUBBLE CLASS  ---------------------------------------------------
# ======================================================================================================================


class LocalBubble():
    ''' Computes the local Bubble suszeptibility \chi_0 = - beta GG '''

    asympt = None  # Asymptotic correction with G = 1/iv

    def __init__(self, giw=None, beta=1.0, niv_sum=-1, iw=None):
        self._giw = giw
        self._beta = beta
        if (niv_sum == -1):
            niv_sum = self._niv_giw - np.max(np.abs(iw))
        self._niv_sum = niv_sum
        self._iw = iw
        self.set_chi0()
        self.set_gchi0()

        self.set_asympt()

    @property
    def giw(self):
        return self._giw

    @property
    def iw(self):
        return self._iw

    @property
    def niw(self):
        return self.iw.size

    @property
    def iw_ind(self):
        return np.arange(0, self.iw.size)

    @property
    def niv_sum(self) -> int:
        return self._niv_sum

    @property
    def niv(self) -> int:
        return self._niv_sum

    @property
    def niv_giw(self) -> int:
        return self._giw.shape[0] // 2

    @property
    def chi0_asympt(self):
        return self.chi0 + self.asympt

    @property
    def beta(self) -> float:
        return self._beta

    @property
    def chi0(self):
        return self._chi0

    @property
    def gchi0(self):
        return self._gchi0

    def set_chi0(self):
        self._chi0 = self.vec_get_chi0()

    def get_chi0(self, wn=0):
        niv_giw = self.niv_giw
        niv_sum = self.niv_sum
        return - 1. / self._beta * np.sum(self._giw[niv_giw - niv_sum:niv_giw + niv_sum]
                                          * self._giw[niv_giw - niv_sum - wn:niv_giw + niv_sum - wn])

    def vec_get_chi0(self):
        return np.array([self.get_chi0(wn=wn) for wn in self._iw])

    def set_asympt(self):
        self.asympt = self.vec_get_asympt_correction()

    def get_asympt_correction(self, wn=0):
        vn = (2 * mf.vn(n=self.niv_sum) + 1)
        vpwn = (2 * mf.vn(n=self.niv_sum) + 1) - 2 * wn
        if (wn == 0):
            return self.beta / np.pi ** 2 * (np.pi ** 2 / 8 - 0.5 * np.sum(1. / vn * 1. / vpwn))
        else:
            return self.beta / np.pi ** 2 * (- 0.5 * np.sum(1. / vn * 1. / vpwn))

    def vec_get_asympt_correction(self):
        return np.array([self.get_asympt_correction(wn=wn) for wn in self._iw])

    def set_gchi0(self):
        self._gchi0 = self.vec_get_gchi0()

    def get_gchi0(self, wn=0):
        niv = self.niv
        niv_giw = self.niv_giw
        return - self.beta * self.giw[niv_giw - niv:niv_giw + niv] * self.giw[
                                                                     niv_giw - niv - wn:niv_giw + niv - wn]

    def vec_get_gchi0(self):
        return np.array([self.get_gchi0(wn=wn) for wn in self.iw])


# ======================================================================================================================
# -------------------------------------------- FOUR POINT PARENT CLASS  ------------------------------------------------
# ======================================================================================================================
class LocalFourPoint():
    ''' Parent class for local four-point correlation '''

    def __init__(self, matrix=None, channel=None, beta=None, iw=None):
        assert (matrix.shape[0] == iw.size), 'Size of iw_core does not match first dimension of four_point'

        self._channel = channel
        self._mat = matrix
        self._beta = beta
        self._iw = iw
        self._niw = np.size(self._iw)

    @property
    def mat(self):
        return self._mat

    @property
    def iw(self):
        return self._iw

    @property
    def iw_ind(self):
        return np.arange(0, self.iw.size)

    @property
    def channel(self):
        return self._channel

    @property
    def beta(self) -> float:
        return self._beta

    @property
    def niv(self) -> int:
        return self._mat.shape[-1] // 2

    @property
    def niw(self) -> int:
        return self._iw.size

    def cut_iv(self, niv_cut=None):
        niv = self.niv
        self._mat = self._mat[..., niv - niv_cut:niv + niv_cut, niv - niv_cut:niv + niv_cut]

    def contract_legs(self):
        return 1. / self.beta ** 2 * np.sum(self._mat, axis=(-2, -1))


def vec_chir_from_g2(g2: LocalFourPoint = None, giw=None):
    if (g2.channel == 'dens'):
        ggv = get_ggv(giw=giw, niv_ggv=g2.niv)
    else:
        ggv = None
    return np.array([chir_from_g2(g2=g2._mat[wn], ggv=ggv, beta=g2.beta, wn=g2.iw[wn]) for wn in g2.iw_ind])


class LocalThreePoint(LocalFourPoint):
    ''' Class for local three-point objects like the Fermi-bose vertex'''

    def contract_legs(self):
        return 1. / self.beta * np.sum(self._mat, axis=(-1))


# ======================================================================================================================
# ------------------------------------------- LOCAL SUSCEPTIBILITY CLASS  ----------------------------------------------
# ======================================================================================================================

class LocalSusceptibility():
    ''' Parent class for local susceptibilities'''

    asympt = None  # asymptotic correction from Chi = Chi0

    def __init__(self, matrix=None, channel='dens', beta=1.0, iw=None, chi0_urange: LocalBubble = None):
        assert (matrix.shape[0] == iw.size), 'Size of iw_core does not match first dimension of four_point'

        self._channel = channel
        self._mat = matrix
        self._beta = beta
        self._iw = iw
        self._niw = np.size(self._iw)

        self.set_asympt(chi0_urange=chi0_urange)

    @property
    def mat(self):
        return self._mat

    @property
    def iw(self):
        return self._iw

    @property
    def channel(self):
        return self._channel

    @property
    def beta(self) -> float:
        return self._beta

    @property
    def niv(self) -> int:
        return self._niv

    @property
    def niw(self) -> int:
        return self._iw.size

    def set_asympt(self, chi0_urange: LocalBubble = None):
        self.asympt = chi0_urange.chi0_asympt - chi0_urange.chi0

    @property
    def mat_asympt(self):
        return self.mat + self.asympt


def local_chi_phys_from_chi_aux(chi_aux=None, chi0_urange: LocalBubble = None, chi0_core: LocalBubble = None, u=None):
    u_r = get_ur(u=u, channel=chi_aux.channel)
    chi = 1. / (1. / (chi_aux.mat + chi0_urange.chi0 - chi0_core.chi0) + u_r)
    return LocalSusceptibility(matrix=chi, channel=chi_aux.channel, beta=chi_aux.beta, iw=chi_aux.iw,
                               chi0_urange=chi0_urange)


def local_susceptibility_from_four_point(four_point: LocalFourPoint = None, chi0_urange=None):
    return LocalSusceptibility(matrix=four_point.contract_legs(), channel=four_point.channel
                               , beta=four_point.beta, iw=four_point.iw, chi0_urange=chi0_urange)


def local_rpa_susceptibility(chi0_urange: LocalBubble = None, channel=None, u=None):
    u_r = get_ur(u=u, channel=channel)
    chir = chi0_urange.chi0 / (1 + u_r * chi0_urange.chi0)
    return LocalSusceptibility(matrix=chir, channel=channel, beta=chi0_urange.beta, iw=chi0_urange.iw,
                               chi0_urange=chi0_urange)


# ======================================================================================================================
# ------------------------------------- FREE FUNCTIONS THAT USE OBJECTS AS INPUT ---------------------------------------
# ======================================================================================================================

# ==================================================================================================================
def gammar_from_gchir(gchir: LocalFourPoint = None, gchi0_urange: LocalBubble = None, u=1.0):
    u_r = get_ur(u=u, channel=gchir.channel)
    gammar = np.array(
        [gammar_from_gchir_wn(gchir=gchir.mat[wn], gchi0_urange=gchi0_urange.gchi0[wn], niv_core=gchir.niv,
                              beta=gchir.beta, u=u_r) for wn in gchir.iw_ind])
    return LocalFourPoint(matrix=gammar, channel=gchir.channel, beta=gchir.beta, iw=gchir.iw)


def gammar_from_gchir_wn(gchir=None, gchi0_urange=None, niv_core=None, beta=1.0, u=1.0):
    full = u / (beta * beta) + np.diag(1. / gchi0_urange)
    inv_full = np.linalg.inv(full)
    inv_core = cut_iv(inv_full, niv_core)
    core = np.linalg.inv(inv_core)
    chigr_inv = np.linalg.inv(gchir)
    return -(core - chigr_inv - u / (beta * beta))


# ==================================================================================================================

# ==================================================================================================================
def local_gchi_aux_from_gammar(gammar: LocalFourPoint = None, gchi0_core: LocalBubble = None, u=None):
    u_r = get_ur(u=u, channel=gammar.channel)
    gchi_aux = np.array([local_gchi_aux_from_gammar_wn(gammar=gammar.mat[wn], gchi0=gchi0_core.gchi0[wn],
                                                       beta=gammar.beta, u=u_r) for wn in gammar.iw_ind])
    return LocalFourPoint(matrix=gchi_aux, channel=gammar.channel, beta=gammar.beta, iw=gammar.iw)


def local_gchi_aux_from_gammar_wn(gammar=None, gchi0=None, beta=1.0, u=1.0):
    gchi0_inv = np.diag(1. / gchi0)
    chi_aux_inv = gchi0_inv + gammar - u / (beta * beta)
    return np.linalg.inv(chi_aux_inv)


# ==================================================================================================================


# ==================================================================================================================
def local_fermi_bose_from_chi_aux(gchi_aux: LocalFourPoint = None, gchi0: LocalBubble = None):
    vrg = 1. / gchi0.gchi0 * 1. / gchi0.beta * np.sum(gchi_aux.mat, axis=-1)
    return LocalThreePoint(matrix=vrg, channel=gchi_aux.channel, beta=gchi_aux.beta, iw=gchi_aux.iw)


def local_fermi_bose_urange(vrg: LocalThreePoint = None, niv_urange=-1):
    if (niv_urange == -1):
        niv_urange = vrg.niv
    vrg_urange = 1. / vrg.beta * np.ones((vrg.niw, 2 * niv_urange), dtype=complex)
    vrg_urange[:, niv_urange - vrg.niv:niv_urange + vrg.niv] = vrg.mat
    return LocalThreePoint(matrix=vrg_urange, channel=vrg.channel, beta=vrg.beta, iw=vrg.iw)


def local_fermi_bose_asympt(vrg: LocalThreePoint = None, chi_urange: LocalSusceptibility = None, u=None, niv_core=None):
    u_r = get_ur(u=u, channel=vrg.channel)
    #vrg_asympt = vrg.mat #* (1 - u_r * chi_urange.mat_asympt[:, None]) / (1 - u_r * chi_urange.mat[:, None])
    #vrg_asympt[:, vrg.niv - niv_core:vrg.niv + niv_core] *= (1 - u_r * chi_urange.mat[:, None]) / (1 - u_r * chi_urange.mat_asympt[:, None])
    vrg_asympt = vrg.mat * (1 - u_r * chi_urange.mat[:, None]) / (1 - u_r * chi_urange.mat_asympt[:, None])
    return LocalThreePoint(matrix=vrg_asympt, channel=vrg.channel, beta=vrg.beta, iw=vrg.iw)


def local_fermi_bose_from_chi_aux_urange(gchi_aux: LocalFourPoint = None, gchi0: LocalBubble = None, niv_urange=-1):
    vrg = local_fermi_bose_from_chi_aux(gchi_aux=gchi_aux, gchi0=gchi0)
    vrg = local_fermi_bose_urange(vrg=vrg, niv_urange=niv_urange)
    return vrg


# ======================================================================================================================

# ======================================================================================================================

def local_vertex_urange(gchi_aux: LocalFourPoint = None, gchi0_urange = None, gchi0_core = None, vrg: LocalThreePoint = None,
                        chi = None, u=None):
    u_r = get_ur(u=u, channel=vrg.channel)
    niv_urange = np.shape(gchi0_urange)[-1] // 2
    niv_core = np.shape(gchi_aux.mat)[-1] // 2
    F_urange = u_r * (1-u_r * chi[:,None,None]) * vrg.mat[:,:,None] * vrg.mat[:,None,:]
    unity = np.eye(np.shape(gchi0_core)[-1], dtype=complex)
    F_urange[:,niv_urange-niv_core:niv_urange+niv_core,niv_urange-niv_core:niv_urange+niv_core] += 1./gchi0_core[:,:,None] * (unity - gchi_aux.mat * 1./gchi0_core[:,None,:])
    return F_urange

def local_vertex_inverse_bse_wn(gamma=None, chi0=None, u_r=None, beta=None):
    niv = np.shape(gamma)[-1] // 2
    niv_u = np.shape(chi0)[-1] // 2
    gamma_u = u_r * np.ones((2*niv_u,2*niv_u), dtype=complex) * 1./beta**2
    gamma_u[niv_u-niv:niv_u+niv,niv_u-niv:niv_u+niv] = gamma # gamma contains internally 1/beta^2
    return np.matmul(gamma_u,np.linalg.inv(np.eye(2*niv_u,dtype=complex) + gamma_u * chi0[:,None]))
    #return np.linalg.inv(np.linalg.inv(gamma_u))- np.diag(chi0))

def local_vertex_inverse_bse(gamma=None, chi0=None, u=None):
    u_r = get_ur(u=u, channel=gamma.channel)
    return np.array([local_vertex_inverse_bse_wn(gamma=gamma.mat[wn], chi0=chi0.gchi0[wn], u_r=u_r, beta=gamma.beta) for wn in gamma.iw_ind])



# ======================================================================================================================
# ----------------------------------------------- NONLOCAL BUBBLE CLASS ------------------------------------------------
# ======================================================================================================================

class Bubble():
    ''' Computes the Bubble suszeptibility \chi_0 = - beta GG
        Layout of gkiw dimensions is: [Nkx,Nky,Nkz,Niv]
    '''

    asympt = None  # Asymptotic correction from G = 1/iv

    def __init__(self, gk=None, gkpq=None, beta=None, wn=None):
        self._gk = gk
        self._gkpq = gkpq
        self._beta = beta
        self.set_chi0()
        self.wn = wn
        self.set_asympt()

    @property
    def gk(self):
        return self._gk

    @property
    def gkpq(self):
        return self._gkpq

    @property
    def niv(self) -> int:
        return self._gk.shape[-1] // 2

    @property
    def beta(self) -> float:
        return self._beta

    @property
    def chi0(self):
        return self._chi0

    @property
    def gchi0(self):
        return self._gchi0

    @property
    def chi0_asympt(self):
        return self.chi0 + self.asympt

    def set_chi0(self):
        self._chi0 = self.get_chi0()

    def get_chi0(self):
        return - 1. / self._beta * np.sum(np.mean(self.gk * self.gkpq, axis=(0, 1, 2)))

    def vec_get_chi0(self):
        return np.array([self.get_chi0(wn=wn) for wn in self._iw])

    def set_asympt(self):
        self.asympt = self.get_asympt_correction(wn=self.wn)

    def get_asympt_correction(self, wn=0):
        vn = (2 * mf.vn(n=self.niv) + 1)
        vpwn = (2 * mf.vn(n=self.niv) + 1) - 2 * wn
        if (wn == 0):
            return self.beta / np.pi ** 2 * (np.pi ** 2 / 8 - 0.5 * np.sum(1. / vn * 1. / vpwn))
        else:
            return self.beta / np.pi ** 2 * (- 0.5 * np.sum(1. / vn * 1. / vpwn))

    def set_gchi0(self):
        self._gchi0 = self.get_gchi0()

    def get_gchi0(self):
        return - self.beta * np.mean(self.gk * self.gkpq, axis=(0, 1, 2))


# ======================================================================================================================
# ----------------------------------------- NONLOCAL SUSCEPTIBILITY CLASS ----------------------------------------------
# ======================================================================================================================

class Susceptibility():
    ''' Class for the non-local susceptibility '''

    asympt = None  # asymptotic correction from Chi = Chi0

    def __init__(self, matrix=None, channel='dens', beta=None, u=None, chi0_urange=None):
        self._u = u
        self._channel = channel
        self._mat = matrix
        self._beta = beta

        if (chi0_urange is not None):
            self.set_asympt(chi0_urange=chi0_urange)

    @property
    def channel(self):
        return self._channel

    @property
    def mat(self):
        return self._mat

    @mat.setter
    def mat(self, matrix):
        self._mat = matrix

    @property
    def beta(self):
        return self._beta

    @property
    def u(self):
        return self._u

    @property
    def u_r(self):
        return get_ur(self.u, self.channel)

    @property
    def mat_asympt(self):
        return self.mat + self.asympt

    def set_asympt(self, chi0_urange: Bubble = None):
        self.asympt = chi0_urange.chi0_asympt - chi0_urange.chi0


class FullQ():
    ''' Contains an object on the full {q,w} grid
        Dimension layout is [{q,w},...]
    '''

    def __init__(self, channel='dens', beta=1.0, u=1.0, qiw: ind.qiw = None):
        self._u = u
        self._beta = beta
        self._channel = channel
        self._qiw = qiw
        self._mat = [0] * qiw.size

    @property
    def channel(self):
        return self._channel

    @property
    def mat(self):
        return self._mat

    @mat.setter
    def mat(self, value, index):
        self._mat[index] = value

    @property
    def beta(self):
        return self._beta

    @property
    def u(self):
        return self._u

    @property
    def u_r(self):
        return get_ur(self.u, self.channel)

    @property
    def qiw(self):
        return self._qiw

    def mat_to_array(self):
        self._mat = np.array(self.mat)


class LadderSusceptibility(Susceptibility):
    ''' Class for a ladder susceptibility object. Stores for {q,w} '''

    def __init__(self, qiw=None, **kwargs):
        Susceptibility.__init__(self, **kwargs)
        self.qiw = qiw
        self.mat = [0] * self.nqiw

    @property
    def qiw(self):
        return self._qiw

    @qiw.setter
    def qiw(self, value):
        self._qiw = value

    @property
    def nqiw(self):
        return self.qiw.shape[0]

    def mat_to_array(self):
        self.mat = np.array(self.mat)


# ======================================================================================================================
# ------------------------------------------- NONLOCAL FOUR POINT CLASS ------------------------------------------------
# ======================================================================================================================

class FourPoint():
    ''' Parent class for non-local {iv,iv'} slice of a four-point correlation functions '''

    def __init__(self, matrix=None, channel='dens', beta=1.0, u=1.0):
        self._u = u
        self._channel = channel
        self.mat = matrix
        self._beta = beta

    @property
    def niv(self):
        return self.mat.shape[-1] // 2

    @property
    def channel(self):
        return self._channel

    @property
    def mat(self):
        return self._mat

    @mat.setter
    def mat(self, matrix):
        self._mat = matrix

    @property
    def beta(self):
        return self._beta

    @property
    def u(self):
        return self._u

    @property
    def u_r(self):
        return get_ur(self.u, self.channel)

    def cut_iv(self, niv_cut=10):
        niv = self.niv
        self._mat = self._mat[..., niv - niv_cut:niv + niv_cut, niv - niv_cut:niv + niv_cut]

    def contract_legs(self):
        return 1. / self.beta ** 2 * np.sum(self._mat, axis=(-2, -1))


class LadderFourPoint(FourPoint):
    ''' Class for a ladder four-point object. Stores for {q,w} four-vector {iv,iv'} slices'''

    def __init__(self, qiw=None, **kwargs):
        FourPoint.__init__(self, **kwargs)
        self.qiw = qiw

    @property
    def qiw(self):
        return self._qiw

    @qiw.setter
    def qiw(self, value):
        self._qiw = value

    @property
    def nqiw(self):
        return np.size(self.qiw)


class ThreePoint(FourPoint):
    ''' Class for three-point objects like the Fermi-bose vertex'''

    def contract_legs(self):
        return 1. / self.beta * np.sum(self._mat, axis=(-1))


class LadderThreePoint(ThreePoint):
    ''' Class for a ladder susceptibility object. Stores for {q,w} '''

    def __init__(self, qiw=None, **kwargs):
        ThreePoint.__init__(self, **kwargs)
        self.qiw = qiw
        self.mat = [0] * self.nqiw

    @property
    def qiw(self):
        return self._qiw

    @qiw.setter
    def qiw(self, value):
        self._qiw = value

    @property
    def nqiw(self):
        return np.size(self.qiw)

    def mat_to_array(self):
        self.mat = np.array(self.mat)


class LadderObject():
    ''' Parent class for ladder objects. Contains {q,iw} arrays of basis object'''

    def __init__(self, qiw=None, channel=None, beta=None, u=None):
        self.qiw = qiw
        self._ladder = [0] * self.nqiw
        self._u = u
        self._channel = channel
        self._beta = beta
        self._mat = None

    @property
    def qiw(self):
        return self._qiw

    @qiw.setter
    def qiw(self, value):
        self._qiw = value

    @property
    def ladder(self):
        return self._ladder

    @property
    def nqiw(self):
        return self.qiw.shape[0]

    @property
    def mat(self):
        return self._mat

    @property
    def channel(self):
        return self._channel

    @property
    def beta(self):
        return self._beta

    @property
    def u(self):
        return self._u

    @property
    def u_r(self):
        return get_ur(self.u, self.channel)

    def set_qiw_mat(self):
        other_size = self.ladder[0].mat.shape
        self._mat = np.zeros((self.nqiw,) + other_size, dtype=self.ladder[0].mat.dtype)

        for iqw, qiw in enumerate(self.qiw):
            self._mat[iqw] = self.ladder[iqw].mat

    # ----------------------------------- FREE FUNCTIONS FOR THE NONLOCAL FOUR POINT CLASS ---------------------------------


# ======================================================================================================================

def construct_gchi_aux(gammar: LocalFourPoint = None, gchi0: Bubble = None, u=1.0, wn_lin=0):
    u_r = get_ur(u=u, channel=gammar.channel)
    return FourPoint(matrix=gchi_aux_from_gammar(gammar=gammar.mat[wn_lin], gchi0=gchi0.gchi0, beta=gammar.beta, u=u_r)
                     , channel=gammar.channel, beta=gammar.beta, u=u)


def gchi_aux_from_gammar(gammar=None, gchi0=None, beta=1.0, u=1.0):
    gchi0_inv = np.diag(1. / gchi0)
    chi_aux_inv = gchi0_inv + gammar - u / (beta * beta)
    chi_aux = np.linalg.inv(chi_aux_inv)
    return chi_aux


# ==================================================================================================================
def fermi_bose_from_chi_aux(gchi_aux: FourPoint = None, gchi0: Bubble = None):
    vrg = 1. / gchi0.gchi0 * 1. / gchi0.beta * np.sum(gchi_aux.mat, axis=-1)
    return ThreePoint(matrix=vrg, channel=gchi_aux.channel, beta=gchi_aux.beta, u=gchi_aux.u)


def fermi_bose_urange(vrg: ThreePoint = None, niv_urange=-1):
    if (niv_urange == -1):
        niv_urange = vrg.niv
    vrg_urange = 1. / vrg.beta * np.ones((2 * niv_urange,), dtype=complex)
    vrg_urange[niv_urange - vrg.niv:niv_urange + vrg.niv] = vrg.mat
    return ThreePoint(matrix=vrg_urange, channel=vrg.channel, beta=vrg.beta, u=vrg.u)


def fermi_bose_asympt(vrg: ThreePoint = None, chi_urange: Susceptibility = None):
    vrg_asympt = vrg.mat * (1 - vrg.u_r * chi_urange.mat) / (1 - vrg.u_r * chi_urange.mat_asympt)
    return ThreePoint(matrix=vrg_asympt, channel=vrg.channel, beta=vrg.beta, u=vrg.u)


def fermi_bose_from_chi_aux_urange(gchi_aux: FourPoint = None, gchi0: Bubble = None, niv_urange=-1):
    vrg_core = fermi_bose_from_chi_aux(gchi_aux=gchi_aux, gchi0=gchi0)
    vrg = fermi_bose_urange(vrg=vrg_core, niv_urange=niv_urange)
    return vrg, vrg_core


# ==================================================================================================================


# ------------------------------------- FREE FUNCTIONS FOR NONLOCAL SUSCEPTIBILITY CLASS -------------------------------
# ======================================================================================================================

def chi_rpa(chi0_urange: Bubble = None, channel=None, u=None):
    u_r = get_ur(u=u, channel=channel)
    chi = chi0_urange.chi0 / (1 + u_r * chi0_urange.chi0)
    return Susceptibility(matrix=chi, channel=channel, beta=chi0_urange.beta, u=u, chi0_urange=chi0_urange)


def chi_phys_from_chi_aux(chi_aux: Susceptibility = None, chi0_urange: Bubble = None, chi0_core: Bubble = None):
    chi = 1. / (1. / (chi_aux.mat + chi0_urange.chi0 - chi0_core.chi0) + chi_aux.u_r)
    return Susceptibility(matrix=chi, channel=chi_aux.channel, beta=chi_aux.beta, u=chi_aux.u, chi0_urange=chi0_urange)


def susceptibility_from_four_point(four_point: FourPoint = None):
    return Susceptibility(matrix=four_point.contract_legs(), channel=four_point.channel
                          , beta=four_point.beta, u=four_point.u)


# ------------------------------------- WRAPPER FUNCTIONS FOR NONLOCAL SUSCEPTIBILITY CLASS ----------------------------
# ======================================================================================================================

# -------------------------------------------- DGA SUSCEPTIBILITY ------------------------------------------------------
def rpa_susceptibility(dga_conf: conf.DgaConfig = None, dmft_input=None, qiw_indizes=None, sigma=None):
    beta = dga_conf.sys.beta
    u = dga_conf.sys.u
    mu = dmft_input['mu']
    niv_urange = dga_conf.box.niv_urange

    g_generator = tp.GreensFunctionGenerator(beta=beta, kgrid=dga_conf.k_grid, hr=dga_conf.sys.hr, sigma=sigma)

    gk_urange = g_generator.generate_gk(mu=mu, qiw=[0, 0, 0, 0], niv=niv_urange)

    chi_rpa_dens = LadderSusceptibility(channel='dens', beta=beta, u=u, qiw=qiw_indizes)
    chi_rpa_magn = LadderSusceptibility(channel='magn', beta=beta, u=u, qiw=qiw_indizes)

    for iqw in range(qiw_indizes.shape[0]):
        wn = qiw_indizes[iqw][-1]
        q_ind = qiw_indizes[iqw][0]
        q = dga_conf.q_grid.irr_kmesh[:, q_ind]
        qiw = np.append(q, wn)
        gkpq_urange = g_generator.generate_gk(mu=mu, qiw=qiw, niv=niv_urange)

        chi0q_urange = Bubble(gk=gk_urange.gk, gkpq=gkpq_urange.gk, beta=gk_urange.beta, wn=wn)

        chiq_dens = chi_rpa(chi0_urange=chi0q_urange, channel='dens', u=u)
        chiq_magn = chi_rpa(chi0_urange=chi0q_urange, channel='magn', u=u)

        chi_rpa_dens.mat[iqw] = chiq_dens.mat_asympt
        chi_rpa_magn.mat[iqw] = chiq_magn.mat_asympt

    chi_rpa_dens.mat_to_array()
    chi_rpa_magn.mat_to_array()

    chi = {
        'dens': chi_rpa_dens,
        'magn': chi_rpa_magn
    }

    return chi


def chi_aux_asympt(chi_aux: FourPoint = None, chi: Susceptibility = None):
    # u = chi_aux.u_r
    # u_mat = np.ones(np.shape(chi_aux.mat), dtype=complex) * u
    # chi_u_chi = 1./chi_aux.beta**2 * np.matmul(chi_aux.mat, np.matmul(u_mat, chi_aux.mat))
    # return chi_aux.mat + chi_u_chi * (1 - u * chi.mat) * (
    #             (1 - u * chi.mat) / (1 - u * chi.mat_asympt) - 1.)
    return chi_aux.mat


# -------------------------------------------- DGA SUSCEPTIBILITY ------------------------------------------------------
def dga_susceptibility(dga_conf: conf.DgaConfig = None, dmft_input=None, gamma_dmft=None, qiw_grid=None,
                       file=None, k_grid=None, q_grid=None, hr=None, sigma=None, save_vrg=True):
    '''

    :param dmft_input: Dictionary containing input from DMFT.
    :param local_sde:
    :param hr:
    :param sigma: input self-energy
    :param kgrid:
    :param box_sizes:
    :param qiw_grid: [nqx*nqy*nqz*2*niw,4] flattened meshgrid. Layout: {qx,qy,qz,iw}
    :return:
    '''
    if (dga_conf.opt.do_pairing_vertex):
        import PairingVertex as pv
    beta = dga_conf.sys.beta
    u = dga_conf.sys.u
    mu = dga_conf.sys.mu
    niw = dga_conf.box.niw_core
    niv_core = dga_conf.box.niv_core
    niv_pp = dga_conf.box.niv_pp
    niv_urange = dga_conf.box.niv_urange
    niw_vrg_save = dga_conf.box.niw_vrg_save
    niv_vrg_save = dga_conf.box.niv_vrg_save
    gamma_dens_loc = gamma_dmft['dens']
    gamma_magn_loc = gamma_dmft['magn']

    chi_dens = LadderSusceptibility(channel='dens', beta=beta, u=u, qiw=qiw_grid)
    chi_magn = LadderSusceptibility(channel='magn', beta=beta, u=u, qiw=qiw_grid)

    vrg_dens = LadderObject(qiw=qiw_grid, channel='dens', beta=beta, u=u)
    vrg_magn = LadderObject(qiw=qiw_grid, channel='magn', beta=beta, u=u)

    g_generator = tp.GreensFunctionGenerator(beta=beta, kgrid=k_grid, hr=hr, sigma=sigma)

    gk_urange = g_generator.generate_gk(mu=mu, qiw=[0, 0, 0, 0], niv=niv_urange)
    gk_core = copy.deepcopy(gk_urange)
    gk_core.cut_self_iv(niv_cut=niv_core)

    if (dga_conf.opt.do_pairing_vertex):
        ivn = np.arange(-niv_pp, niv_pp)
        omega = np.zeros((2 * niv_pp, 2 * niv_pp))
        for i, vi in enumerate(ivn):
            for j, vip in enumerate(ivn):
                omega[i, j] = vi - vip

    for iqw in range(qiw_grid.shape[0]):
        wn = qiw_grid[iqw][-1]
        q_ind = qiw_grid[iqw][0]
        q = q_grid.irr_kmesh[:, q_ind]
        qiw = np.append(-q, wn)  # WARNING: Here I am not sure if it should be +q or -q.
        wn_lin = np.array(mf.cen2lin(wn, -niw), dtype=int)
        gkpq_urange = g_generator.generate_gk(mu=mu, qiw=qiw, niv=niv_urange)

        gkpq_core = copy.deepcopy(gkpq_urange)
        gkpq_core.cut_self_iv(niv_cut=niv_core)

        chi0q_core = Bubble(gk=gk_core.gk, gkpq=gkpq_core.gk, beta=gk_core.beta, wn=wn)
        chi0q_urange = Bubble(gk=gk_urange.gk, gkpq=gkpq_urange.gk, beta=gk_urange.beta, wn=wn)

        gchi_aux_dens = construct_gchi_aux(gammar=gamma_dens_loc, gchi0=chi0q_core, u=u, wn_lin=wn_lin)
        gchi_aux_magn = construct_gchi_aux(gammar=gamma_magn_loc, gchi0=chi0q_core, u=u, wn_lin=wn_lin)

        chi_aux_dens = susceptibility_from_four_point(four_point=gchi_aux_dens)
        chi_aux_magn = susceptibility_from_four_point(four_point=gchi_aux_magn)

        chiq_dens = chi_phys_from_chi_aux(chi_aux=chi_aux_dens, chi0_urange=chi0q_urange,
                                          chi0_core=chi0q_core)

        chiq_magn = chi_phys_from_chi_aux(chi_aux=chi_aux_magn, chi0_urange=chi0q_urange,
                                          chi0_core=chi0q_core)

        vrgq_dens, vrgq_dens_core = fermi_bose_from_chi_aux_urange(gchi_aux=gchi_aux_dens, gchi0=chi0q_core,
                                                                   niv_urange=niv_urange)
        vrgq_dens = fermi_bose_asympt(vrg=vrgq_dens, chi_urange=chiq_dens)
        vrgq_magn, vrgq_magn_core = fermi_bose_from_chi_aux_urange(gchi_aux=gchi_aux_magn, gchi0=chi0q_core,
                                                                   niv_urange=niv_urange)
        vrgq_magn = fermi_bose_asympt(vrg=vrgq_magn, chi_urange=chiq_magn)

        chi_dens.mat[iqw] = chiq_dens.mat_asympt
        chi_magn.mat[iqw] = chiq_magn.mat_asympt

        vrg_dens.ladder[iqw] = vrgq_dens
        vrg_magn.ladder[iqw] = vrgq_magn

        if (dga_conf.opt.do_pairing_vertex):
            if (np.abs(wn) < 2 * niv_pp):
                condition = omega == wn

                gchi_aux_magn = chi_aux_asympt(chi_aux=gchi_aux_magn, chi=chiq_magn)
                gchi_aux_dens = chi_aux_asympt(chi_aux=gchi_aux_dens, chi=chiq_dens)
                f1_magn_slice, f2_magn_slice = pv.ladder_vertex_from_chi_aux_components(gchi_aux=gchi_aux_magn,
                                                                                        vrg=vrgq_magn_core.mat,
                                                                                        gchi0=chi0q_core.gchi0,
                                                                                        beta=beta,
                                                                                        u_r=get_ur(u=u, channel='magn'))
                f1_dens_slice, f2_dens_slice = pv.ladder_vertex_from_chi_aux_components(gchi_aux=gchi_aux_dens,
                                                                                        vrg=vrgq_dens_core.mat,
                                                                                        gchi0=chi0q_core.gchi0,
                                                                                        beta=beta,
                                                                                        u_r=get_ur(u=u, channel='dens'))

                group = '/irrq{:03d}wn{:04d}/'.format(*qiw_grid[iqw])
                file[group + 'f1_magn/'] = pv.get_pp_slice_4pt(mat=f1_magn_slice, condition=condition, niv_pp=niv_pp)
                file[group + 'f2_magn/'] = pv.get_pp_slice_4pt(mat=f2_magn_slice, condition=condition, niv_pp=niv_pp)
                file[group + 'f1_dens/'] = pv.get_pp_slice_4pt(mat=f1_dens_slice, condition=condition, niv_pp=niv_pp)
                file[group + 'f2_dens/'] = pv.get_pp_slice_4pt(mat=f2_dens_slice, condition=condition, niv_pp=niv_pp)
                file[group + 'condition/'] = condition

        # Save the lowest 5 frequencies for the spin-fermion vertex::
        if (np.abs(wn) < niw_vrg_save and save_vrg == True):
            group = '/irrq{:03d}wn{:04d}/'.format(*qiw_grid[iqw])
            file[group + 'vrg_magn/'] = beta * vrgq_magn.mat[niv_urange - niv_vrg_save:niv_urange + niv_vrg_save]
            file[group + 'vrg_dens/'] = beta * vrgq_dens.mat[niv_urange - niv_vrg_save:niv_urange + niv_vrg_save]

    chi_dens.mat_to_array()
    chi_magn.mat_to_array()

    vrg_dens.set_qiw_mat()
    vrg_magn.set_qiw_mat()

    dga_chi = {
        'dens': chi_dens,
        'magn': chi_magn
    }
    dga_vrg = {
        'dens': vrg_dens,
        'magn': vrg_magn
    }
    return dga_chi, dga_vrg


def load_spin_fermion(output_path=None, name='Qiw', mpi_size=None, nq=None, niv=None, niw=None):
    '''WARNING: This currently works only if we are using positive matsubaras only. '''
    import h5py
    import re

    # Collect data from subfiles (This is quite ugly, as it is hardcoded to my structure. This should be replaced by a general routine):
    vrg_dens = np.zeros((nq, niw, 2 * niv), dtype=complex)
    vrg_magn = np.zeros((nq, niw, 2 * niv), dtype=complex)

    for ir in range(mpi_size):
        fname = output_path + name + 'Rank{0:05d}'.format(ir) + '.hdf5'
        file_in = h5py.File(fname, 'r')
        for key1 in list(file_in.file.keys()):
            # extract the q indizes from the group name!
            irrq = np.array(re.findall("\d+", key1), dtype=int)[0]
            wn = np.array(re.findall("\d+", key1), dtype=int)[1]
            if (wn < niw):
                # wn_lin = np.array(mf.cen2lin(wn, -niw), dtype=int)
                vrg_magn[irrq, wn, :] = file_in.file[key1 + '/vrg_magn/'][()]
                vrg_dens[irrq, wn, :] = file_in.file[key1 + '/vrg_dens/'][()]

        file_in.close()

    return vrg_dens, vrg_magn


def allgather_qiw_and_build_fbziw(dga_conf=None, mat=None, distributor=None, qiw_grid=None):
    ''' Gather a {q,iw} object and rebuild the full q, iw structure'''
    mat = distributor.allgather(rank_result=mat)
    mat = dga_conf.q_grid.irrk2fbz(mat=qiw_grid.reshape_matrix(mat))
    mat = mf.wplus2wfull(mat=mat)
    return mat


def ladder_susc_allgather_qiw_and_build_fbziw(dga_conf=None, distributor=None, mat=None, qiw_grid=None,
                                              qiw_grid_fbz=None, channel=None):
    ''' Gather a Ladder suszeptibility object and rebuild the full q, iw structure'''
    gathered_qiw = LadderSusceptibility(qiw=qiw_grid_fbz.meshgrid, channel=channel, u=dga_conf.sys.u,
                                        beta=dga_conf.sys.beta)
    gathered_qiw.mat = allgather_qiw_and_build_fbziw(dga_conf=dga_conf, mat=mat, distributor=distributor,
                                                     qiw_grid=qiw_grid)
    return gathered_qiw


def save_and_plot_chi_lambda(dga_conf: conf.DgaConfig = None, chi_lambda=None):
    np.save(dga_conf.nam.output_path + 'chi_lambda.npy', chi_lambda, allow_pickle=True)
    string_temp = 'Chi[q=(0,0),iw=0,{}]: {}'
    np.savetxt(dga_conf.nam.output_path + 'Knight_shift.txt',
               [string_temp.format('magn', chi_lambda['magn'].mat[0, 0, 0, dga_conf.box.niw_core]),
                string_temp.format('dens', chi_lambda['dens'].mat[0, 0, 0, dga_conf.box.niw_core])], delimiter=' ',
               fmt='%s')
    import Plotting as plotting
    plotting.plot_chi_fs(chi=chi_lambda['magn'].mat.real, output_path=dga_conf.nam.output_path, kgrid=dga_conf.q_grid,
                         name='magn_w0')
    plotting.plot_chi_fs(chi=chi_lambda['dens'].mat.real, output_path=dga_conf.nam.output_path, kgrid=dga_conf.q_grid,
                         name='dens_w0')


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import TwoPoint as twop
    import Hr as hr_mod
    import BrillouinZone as bz

    hr = hr_mod.one_band_2d_t_tp_tpp(t=1.0, tp=-0.2, tpp=0.1)
    nk = (32, 32, 1)
    k_grid = bz.KGrid(nk=nk)
    beta = 10
    sigma = np.zeros((5000,), dtype=complex)
    g_gen = twop.GreensFunctionGenerator(beta=beta, kgrid=k_grid, hr=hr, sigma=sigma)

    mu = g_gen.adjust_mu(n=0.85, mu0=1)
    giwk = g_gen.generate_gk(mu=mu)
    giw = giwk.k_mean()
    niv_core = 20
    niv_urange = 100
    niv_urange2 = 500
    niv_urange3 = 1000
    niv_urange4 = 2000
    wn = 1
    chi0_core = LocalBubble(giw=giw, beta=beta, niv_sum=niv_core, iw=[wn])
    chi0_urange = LocalBubble(giw=giw, beta=beta, niv_sum=niv_urange, iw=[wn])
    chi0_urange2 = LocalBubble(giw=giw, beta=beta, niv_sum=niv_urange2, iw=[wn])
    chi0_urange3 = LocalBubble(giw=giw, beta=beta, niv_sum=niv_urange3, iw=[wn])
    chi0_urange4 = LocalBubble(giw=giw, beta=beta, niv_sum=niv_urange4, iw=[wn])

    plt.plot([chi0_core.chi0, chi0_urange.chi0, chi0_urange2.chi0, chi0_urange3.chi0, chi0_urange4.chi0])
    plt.plot([chi0_core.chi0_asympt, chi0_urange.chi0_asympt, chi0_urange2.chi0_asympt, chi0_urange3.chi0_asympt,
              chi0_urange4.chi0_asympt])
    plt.show()

    print(f'{chi0_core.chi0=}')
    print(f'{chi0_urange.chi0=}')
    print(f'{chi0_urange2.chi0=}')
    print(f'{chi0_urange3.chi0=}')
    print(f'{chi0_urange4.chi0=}')

    print(f'{chi0_core.chi0_asympt=}')
    print(f'{chi0_urange.chi0_asympt=}')
    print(f'{chi0_urange2.chi0_asympt=}')
    print(f'{chi0_urange3.chi0_asympt=}')
    print(f'{chi0_urange4.chi0_asympt=}')
