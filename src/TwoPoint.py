# ------------------------------------------------ COMMENTS ------------------------------------------------------------
# Classes to handle self-energies and Green's functions.
# For the self-energy tail fitting and asymptotic extrapolation is supported.
# The Green's function routine can estimate the chemical potential and also support asymptotic extrapolation.

# -------------------------------------------- IMPORT MODULES ----------------------------------------------------------
import numpy as np
import MatsubaraFrequencies as mf
import scipy.linalg
import scipy.optimize


# -------------------------------------------- SELF ENERGY ----------------------------------------------------------

def get_smom0(u, n):
    '''Return Hartree for the single-band SU(2) symmetric case'''
    return u * n / 2


def get_smom1(u, n):
    ''' return 1/ivu asymptotic prefactor of Im(Sigma) for the single-band SU(2) symmetric case'''
    return -u ** 2 * n / 2 * (1 - n / 2)

def get_sum_chiupup(n):
    ''' return 1/ivu asymptotic prefactor of Im(Sigma) for the single-band SU(2) symmetric case'''
    return  n / 2 * (1 - n / 2)


def fit_smom(iv=None, siwk=None, only_positive=True):
    """Read or calculate self-energy moments"""
    niv = siwk.shape[-1] // 2
    if (not only_positive):
        siwk = siwk[..., niv:]

    n_freq_fit = int(0.2 * niv)
    if n_freq_fit < 4:
        n_freq_fit = 4
    s_loc = np.mean(siwk, axis=(0, 1, 2))  # moments should not depend on momentum

    iwfit = iv[niv - n_freq_fit:]
    fitdata = s_loc[niv - n_freq_fit:]
    mom0 = np.mean(fitdata.real)
    mom1 = np.mean(fitdata.imag * iwfit.imag)  # There is a minus sign in Josef's corresponding code, but this complies with the output from w2dyn.

    return mom0, mom1


class SelfEnergy():
    ''' class to handle self-energies'''

    niv_core_min = 20

    def __init__(self, sigma, beta, pos=True, smom0=None, smom1=None, err=5e-4):
        assert len(np.shape(sigma)) == 4, 'Currently only single-band SU(2) supported with [kx,ky,kz,v]'
        if (not pos):
            niv = sigma.shape[-1] // 2
            sigma = sigma[..., niv:]

        self.sigma = sigma
        self.beta = beta
        iv_plus = mf.iv_plus(beta, self.niv)
        fit_mom0, fit_mom1 = fit_smom(iv_plus, sigma)

        self.err = err

        # Set the moments for the symptotic behaviour:
        if (smom0 is None):
            self.smom0 = fit_mom0
        else:
            self.smom0 = smom0

        if (smom1 is None):
            self.smom1 = fit_mom1
        else:
            self.smom1 = smom1

        # estimate when the asymptotic behavior is sufficient:
        self.niv_core = self.estimate_niv_core()

    @property
    def niv(self):
        return self.sigma.shape[-1]

    @property
    def nk(self):
        return self.sigma.shape[:-1]

    @property
    def sigma_core(self):
        return mf.fermionic_full_nu_range(self.sigma[..., :self.niv_core])

    def k_mean(self):
        return np.mean(self.sigma, axis=(0, 1, 2))

    def estimate_niv_core(self):
        '''check when the real and the imaginary part are within error margin of the asymptotic'''
        asympt = self.get_asympt(niv_asympt=self.niv,n_min=0)
        ind_real = np.argmax(np.abs(self.k_mean().real - asympt.real) < self.err)
        ind_imag = np.argmax(np.abs(self.k_mean().imag - asympt.imag) < self.err)
        niv_core = max(ind_real, ind_imag)
        if (niv_core < self.niv_core_min):
            return self.niv_core_min
        else:
            return niv_core

    def get_siw(self, niv_core=None, niv_full=None):
        if (niv_core is None):
            niv_core = self.niv
        if (niv_core <= self.niv and niv_full is None):
            return mf.fermionic_full_nu_range(self.sigma[..., :niv_core])
        else:
            iv_asympt = mf.iv_plus(self.beta, n=niv_full, n_min=niv_core)
            asympt = (self.smom0 - 1 / iv_asympt * self.smom1)[None, None, None, :] * np.ones(self.nk)[:, :, :, None]
            sigma_asympt = np.concatenate((self.sigma[..., :niv_core], asympt), axis=-1)
            return mf.fermionic_full_nu_range(sigma_asympt)

    def get_asympt(self, niv_asympt,n_min=None, pos=True):
        if(n_min is None):
            n_min = self.niv_core
        iv_asympt = mf.iv_plus(self.beta, n=niv_asympt+n_min, n_min=n_min)
        asympt = (self.smom0 - 1 / iv_asympt * self.smom1)[None, None, None, :] * np.ones(self.nk)[:, :, :, None]
        if (pos):
            return asympt
        else:
            return mf.fermionic_full_nu_range(asympt)


# -------------------------------------------- SELF ENERGY ----------------------------------------------------------
def get_gloc(iv=None, hk=None, siwk=None, mu_trial=None):
    """
    Calculate local Green's function by momentum integration.
    The integration is done by trapezoid integration, which amounts
    to a call of np.mean()
    """
    return np.mean(
        1. / (
                iv[None, None, None, :]
                + mu_trial
                - hk[:, :, :, None]
                - siwk), axis=(0, 1, 2))


# ==================================================================================================================
def get_g_model(mu=None, iv=None, hloc=None, smom0=None):
    """
    Calculate a model Green's function, needed for
    the calculation of the electron density by Matsubara summation.
    References: w2dynamics code, Markus Wallerberger's thesis.
    """
    g_model = 1. / (iv
                    + mu
                    - hloc.real
                    - smom0)

    return g_model


# ==================================================================================================================

# ==================================================================================================================
def get_fill(iv=None, hk=None, siwk=None, beta=1.0, smom0=0.0, hloc=None, mu=None, verbose=False):
    """
    Calculate the filling from the density matrix.
    The density matrix is obtained by frequency summation
    under consideration of the model.
    """
    g_model = get_g_model(mu=mu, iv=iv, hloc=hloc, smom0=smom0)
    gloc = get_gloc(iv=iv, hk=hk, siwk=siwk, mu_trial=mu)
    if (beta * (smom0 + hloc.real - mu) < 20):
        rho_loc = 1. / (1. + np.exp(beta * (smom0 + hloc.real - mu)))
    else:
        rho_loc = np.exp(-beta * (smom0 + hloc.real - mu))
    rho_new = rho_loc + np.sum(gloc.real - g_model.real, axis=0) / beta
    n_el = 2. * rho_new
    if (verbose): print(n_el, 'electrons at ', mu)
    return n_el, rho_new


# ==================================================================================================================

# ==================================================================================================================
def root_fun(mu=0.0, target_filling=1.0, iv=None, hk=None, siwk=None, beta=1.0, smom0=0.0, hloc=None, verbose=False):
    """Auxiliary function for the root finding"""
    return get_fill(iv=iv, hk=hk, siwk=siwk, beta=beta, smom0=smom0, hloc=hloc, mu=mu, verbose=False)[0] - target_filling


# ==================================================================================================================

# ==================================================================================================================
def update_mu(mu0=0.0, target_filling=1.0, iv=None, hk=None, siwk=None, beta=1.0, smom0=0.0, tol=1e-6, verbose=False):
    """
    Update internal chemical potential (mu) to fix the filling to the target filling with given precision.
    :return:
    """
    if (verbose): print('Update mu...')
    hloc = hk.mean()
    mu = mu0
    if (verbose): print(root_fun(mu=mu, target_filling=target_filling, iv=iv, hk=hk, siwk=siwk, beta=beta, smom0=smom0, hloc=hloc))
    try:
        mu = scipy.optimize.newton(root_fun, mu, tol=tol,
                                   args=(target_filling, iv, hk, siwk, beta, smom0, hloc, verbose))
    except RuntimeError:
        if (verbose): print('Root finding for chemical potential failed.')
        if (verbose): print('Using old chemical potential again.')
    if np.abs(mu.imag) < 1e-8:
        mu = mu.real
    else:
        raise ValueError('In OneParticle.update_mu: Chemical Potential must be real.')
    return mu


# ==================================================================================================================

def build_g(v, ek, mu, sigma):
    ''' Build Green's function with [kx,ky,kz,v]'''
    return 1 / (v[None, None, None, :] + mu - ek[..., None] - sigma)


class GreensFunction():
    '''Object to build the Green's function from hr and sigma'''
    mu0 = 0
    mu_tol = 1e-6

    def __init__(self, sigma: SelfEnergy, ek, mu=None, n=None,niv_asympt = 2000):
        self.sigma = sigma
        self.iv_core = mf.iv(sigma.beta, self.sigma.niv_core)
        self.ek = ek
        if (n is not None):
            self.n = n
            self.mu = update_mu(mu0=self.mu0, target_filling=self.n, iv=self.iv_core, hk=ek, siwk=sigma.sigma_core, beta=self.beta, smom0=sigma.smom0,
                                tol=self.mu_tol)
        elif (mu is not None):
            self.mu = mu
            self.n = get_fill(iv=self.iv_core, hk=ek, siwk=sigma.sigma_core, beta=self.beta, smom0=sigma.smom0, hloc=np.mean(ek), mu=mu)
        else:
            raise ValueError('Either mu or n, but bot both, must be supplied.')

        self.core = self.build_g_core()
        self.asympt = None
        self.niv_asympt = None
        self.full = None
        self.set_g_asympt(niv_asympt)
        self.g_loc = None
        self.set_gloc()

    @property
    def v_core(self):
        return mf.v(self.beta,self.niv_core)

    @property
    def beta(self):
        return self.sigma.beta

    @property
    def niv_core(self):
        return self.sigma.niv_core

    @property
    def mem(self):
        ''' returns the memory consumption of the Green's function'''
        if(self.full is not None):
            return self.full.size * self.full.itemsize * 1e-9
        else:
            return self.core.size * self.core.itemsize * 1e-9

    @property
    def g_full(self):
        if (self.asympt is None):
            return self.core
        else:
            return mf.concatenate_core_asmypt(self.core, self.asympt)

    def build_g_core(self):
        return build_g(self.iv_core, self.ek, self.mu, self.sigma.sigma_core)

    def k_mean(self, range='core'):
        if (range == 'core'):
            return np.mean(self.core, axis=(0, 1, 2))
        elif (range == 'full'):
            if(self.full is None):
                raise ValueError('Full Greens function has to be set first.')
            return np.mean(self.full, axis=(0, 1, 2))
        else:
            raise ValueError('Range has to be core or full.')

    def set_gloc(self):
        self.g_loc = self.k_mean(range='full')

    def set_g_asympt(self, niv_asympt):
        self.asympt = self.build_asympt(niv_asympt)
        self.niv_asympt = niv_asympt
        self.full = self.g_full
        self.set_gloc()

    def build_asympt(self, niv_asympt):
        sigma_asympt = self.sigma.get_asympt(niv_asympt)
        iv_asympt = mf.iv_plus(self.beta, n=niv_asympt+self.niv_core, n_min=self.niv_core)
        return mf.fermionic_full_nu_range(build_g(iv_asympt, self.ek, self.mu, sigma_asympt))


if __name__ == '__main__':
    import w2dyn_aux
    import matplotlib.pyplot as plt
    import BrillouinZone as bz
    import Hr as hamr
    import Hk as hamk

    path = '../test/2DSquare_U8_tp-0.2_tpp0.1_beta17.5_n0.90/'
    file = '1p-data.hdf5'

    dmft_file = w2dyn_aux.w2dyn_file(fname=path + file)
    siw = dmft_file.get_siw()[0, 0, :][None, None, None, :]
    beta = dmft_file.get_beta()
    u = dmft_file.get_udd()
    n = dmft_file.get_totdens()
    mu_dmft = dmft_file.get_mu()
    sigma_dmft = SelfEnergy(sigma=siw, beta=beta, pos=False)
    giw_dmft = dmft_file.get_giw()[0, 0, :]
    niv_dmft = dmft_file.get_niw()

    # Build Green's function:
    hr = hamr.one_band_2d_t_tp_tpp(1, -0.2, 0.1)
    nk = (42, 42, 1)
    k_grid = bz.KGrid(nk=nk, symmetries=bz.two_dimensional_square_symmetries())
    ek = hamk.ek_3d(k_grid.grid, hr)

    giwk = GreensFunction(sigma_dmft, ek, n=n)
    niv_asympt = 2000
    giwk.set_g_asympt(niv_asympt)
    g_loc = giwk.k_mean(range='full')

    vn_core = mf.vn(giwk.niv_core)
    vn_asympt = mf.vn(giwk.niv_core+giwk.niv_asympt)

    n_start = 800
    n_plot = 50
    fig, ax = plt.subplots(1,2,figsize=(7,3.5))
    ax[0].plot(mf.cut_v_1d_pos(vn_asympt,n_plot,n_start), mf.cut_v_1d_pos(g_loc,n_plot,n_start).real, '-o', color='cornflowerblue')
    ax[0].plot(mf.cut_v_1d_pos(vn_asympt,n_plot,n_start), mf.cut_v_1d_pos(giw_dmft,n_plot,n_start).real, '-', color='k')
    ax[1].plot(mf.cut_v_1d_pos(vn_asympt,n_plot,n_start), mf.cut_v_1d_pos(g_loc,n_plot,n_start).imag, '-o', color='cornflowerblue')
    ax[1].plot(mf.cut_v_1d_pos(vn_asympt,n_plot,n_start), mf.cut_v_1d_pos(giw_dmft,n_plot,n_start).imag, '-', color='k')
    ax[0].set_xlabel(r'$\nu_n$')
    ax[1].set_xlabel(r'$\nu_n$')
    ax[0].set_ylabel(r'$\Re G$')
    ax[1].set_ylabel(r'$\Im G$')
    plt.tight_layout()
    # plt.savefig(PLOT_PATH+'GreensFunction_TestAsymptotic_1.png')
    plt.show()
