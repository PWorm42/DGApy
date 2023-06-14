#!/usr/bin/env python
# SBATCH -N 1
# SBATCH -J Susc_cont
# SBATCH --ntasks-per-node=48
# SBATCH --partition=mem_0096
# SBATCH --qos=p71282_0096
# SBATCH --time=06:00:00

# SBATCH --mail-type=ALL                              # first have to state the type of event to occur
# SBATCH --mail-user=<p.worm@a1.net>   # and then your email address

# ------------------------------------------------ COMMENTS ------------------------------------------------------------


# -------------------------------------------- IMPORT MODULES ----------------------------------------------------------
import h5py
import numpy as np
import matplotlib.pyplot as plt
import os
import MatsubaraFrequencies as mf
import continuation as cont
import BrillouinZone as bz
import Output as output


# ToDo: Scan alpha for single q=(pi,pi)
# ToDo: Plot Matsubara for q=(pi,pi)

# ----------------------------------------------- FUNCTIONS ------------------------------------------------------------

def cont_k(iw, data_1, w, err_val=0.002, sigma=2.0, verbose=False, preblur=False, blur_width=0.0, alpha_determination='chi2kink'):
    #     model = np.ones_like(w)
    data_1 = np.squeeze(data_1)
    model = np.exp(-w ** 2 / sigma ** 2)
    model *= data_1[0].real / np.trapz(model, w)
    err = err_val * np.ones_like(iw)
    probl = cont.AnalyticContinuationProblem(re_axis=w, im_axis=iw,
                                             im_data=data_1, kernel_mode='freq_bosonic')
    sol, _ = probl.solve(method='maxent_svd', optimizer='newton', preblur=preblur, blur_width=blur_width,
                         alpha_determination=alpha_determination,
                         model=model, stdev=err, interactive=False, verbose=verbose,
                         alpha_start=1e12, alpha_end=1e-3, fit_position=2.)  # fit_psition smaller -> underfitting

    if (verbose):
        fig, ax = plt.subplots(ncols=3, nrows=1, figsize=(15, 4))
        ax[0].plot(w, sol.A_opt * w)
        ax[1].plot(iw, data_1)
        ax[1].plot(iw, sol.backtransform)
        ax[2].plot(iw, data_1 - sol.backtransform)
        plt.show()
    return (sol.A_opt, sol.backtransform)


# ------------------------------------------------ OBJECTS -------------------------------------------------------------
def add_lambda(chi,lambda_add):
    chi = 1./(1./chi+lambda_add)
    return chi

# -------------------------------------------------- MAIN --------------------------------------------------------------
tev = 1.0
t_scal = 1
err = 0.01
w_max = 15
nw = 501
use_preblur = False
bw = 0.0
sigma = 4.0
ncut = 10
lambda_add = 0.00
alpha_det = 'chi2kink'
channel = 'magn'
name = '_pipi'
bz_k_path = 'Gamma-X-M2-Gamma'


input_path = '/mnt/d/Research/La2NiO4/TwoOrbital/1onSTO_n2.2/DGAHighT/'
input_path = 'D:/Research/La2NiO4/TwoOrbital/1onSTO_n2.2/DGAHighT/'
input_path = 'D:/Research/La2NiO4/TwoOrbital/1onSTO_n2.0/HighT_nw75/'
input_path = 'D:/Research/La2NiO4/TwoOrbital/4onLAO_n2.0/HighT_2/'
input_path = 'D:/Research/La2NiO4/TwoOrbital/4onLAO_n2.2/HighT_nw50/'
input_path = '/mnt/d/Research/HoleDopedCuprates/2DSquare_U8_tp-0.2_tpp0.1_beta20_n0.80/scdga_invert/'
input_path = '/mnt/d/Research/HubbardModel_tp-0.0_tpp0.0/2DSquare_U8_tp-0.0_tpp0.0_beta4_n0.85/scdga_kaufmann/'
# input_path = '/mnt/d/Research/HubbardModel_tp-0.0_tpp0.0/2DSquare_U8_tp-0.0_tpp0.0_beta4_n0.85/scdga_kaufmann/'
# input_path = '/mnt/c/Users/pworm/Research/La2NiO4/TwoBand/1onSTO_n2.2/Nk32/'
output_path = input_path
output_folder = f'ChiCont_nw_{nw}_err_{err}_sigma_{sigma}_lambda_{lambda_add}'
output_path = output.uniquify(output_path + output_folder) + '/'
out_dir = output_path
if not os.path.exists(out_dir):
    os.mkdir(out_dir)

fname = 'adga_Nkx100_Nky100_Nkz001_000.hdf5'
fname = 'adga_Nkx064_Nky064_Nkz002_000.hdf5'
fname = 'adga-008.hdf5'
fname = 'adga-000.hdf5'
fname = 'adga_sc_3.hdf5'
hfile = h5py.File(name=input_path+fname)
chi = hfile['susceptibility/nonloc/magn'][()]
beta = hfile['input/beta']
n = hfile['input/n_dmft']
niw = chi.shape[-1] // 2
if ncut == -1:
    ncut = niw
nk = chi.shape[2:-1]
n_band = chi.shape[0]

iw = mf.w(beta=beta, n=niw)
#_q_grid = config._q_grid

# Cut negative frequencies:
chi = chi[..., niw:niw+ncut]

fig = plt.figure()
plt.plot(chi[0,0,nk[0]//2,nk[1]//2,0,:].real)
plt.savefig(output_path + 'chi_magn_real.png')
plt.show()




# create q-path:
q_path = bz.KPath(nk=nk,path=bz_k_path)

fac = 1


q_dict ={
    'kpts':q_path.kpts,
    'cind':q_path.cind,
    'k_axis':q_path.k_axis,
    'k_val': q_path.k_val,
    'path': q_path.path,
    'path_split': q_path.ckps
}
np.save(out_dir + 'q_path', q_dict,allow_pickle=True)


np.savetxt(out_dir + 'q_path_string.txt', [bz_k_path], delimiter=" ", fmt="%s")

chi_qpath = chi[:,:,q_path.ikx[::fac], q_path.iky[::fac], :,:]
w = w_max * np.tan(np.linspace(0., np.pi / 2.1, num=nw)) / np.tan(np.pi / 2.1)
#w = np.linspace(0,w_max,num=nw)
s = np.zeros((n_band,n_band,len(q_path.ikx[::fac]), nw))
bt = np.zeros((n_band,n_band,len(q_path.ikx[::fac]), ncut))

for ib1 in range(n_band):
    for ib2 in range(n_band):
        for ik in range(len(q_path.ikx[::fac])):
            print(ik)
            a, b = cont_k(iw[niw:niw+ncut], chi_qpath[ib1,ib2,ik,0, :], w, err,sigma=sigma, preblur=use_preblur, blur_width=bw, alpha_determination=alpha_det)
            s[ib1,ib2,ik] = a[:]
            bt[ib1,ib2,ik] = b[:]



np.save(out_dir + 'chi', s)

np.save(out_dir + 'w', w)


plt.figure()
plt.plot(q_path.k_axis[::fac], chi_qpath[0,0,:,0].real, label='real')
plt.plot(q_path.k_axis[::fac], chi_qpath[0,0,:,0].imag, label='imag')
plt.xlabel('q-path')
plt.ylabel('chi')
plt.savefig(
    out_dir + 'chi_qpath_matsubara_err{}_usepreblur_{}_bw{}_alpha_{}_.pdf'.format(err, use_preblur, bw,
                                                                                             alpha_det), dpi=300)
plt.savefig(
    out_dir +  'chi_qpath_matsubara_err{}_usepreblur_{}_bw{}_alpha_{}_.png'.format(err, use_preblur, bw,
                                                                                             alpha_det), dpi=300)
plt.show()
plt.close()

fig, ax = plt.subplots(nrows=2, ncols=1, figsize=(14, 8))
pl0 = ax[0].pcolormesh(q_path.k_axis[::fac], w * tev, w[:, None] * s[0,0].T, shading='auto',
                       rasterized=True, cmap='terrain')
plt.colorbar(pl0, ax=ax[0])
ax[0].set_title('chi(q, w)')
pl1 = ax[1].pcolormesh(q_path.k_axis[::fac], w * tev, np.log10(w[:, None] * s[0,0].T + 1e-8), vmin=-1.0, vmax=0,
                       shading='auto', rasterized=True, cmap='terrain')
plt.colorbar(pl1, ax=ax[1])
ax[1].set_title('log10 chi(q, w)')
ax[0].set_ylabel('$\omega [eV]$')
ax[1].set_ylabel('$\omega [eV]$')

ax[0].vlines([0.5,0.5+0.25 * np.sqrt(2.)],0,1.0,'k')
ax[1].vlines([0.5,0.5+0.25 * np.sqrt(2.)],0,1.0,'k')
ax[0].hlines([0.2],0,0.5+0.5 * np.sqrt(2.),'k')
ax[1].hlines([0.2],0,0.5+0.5 * np.sqrt(2.),'k')
ax[0].set_ylim(0., 0.5)
ax[1].set_ylim(0., 0.5)
plt.savefig(
    out_dir + 'chi_qpath_err{}_usepreblur_{}_bw{}_alpha_{}_.pdf'.format(err, use_preblur, bw, alpha_det),
    dpi=300)
plt.savefig(
    out_dir + 'chi_qpath_err{}_usepreblur_{}_bw{}_alpha_{}_.png'.format(err, use_preblur, bw, alpha_det),
    dpi=300)
plt.show()
plt.close()


###################
fig, ax = plt.subplots(nrows=2, ncols=1, figsize=(14, 8))
pl0 = ax[0].pcolormesh(q_path.k_axis[::fac], w * tev, w[:, None] * s[0,0].T, shading='auto',
                       rasterized=True, cmap='terrain')
plt.colorbar(pl0, ax=ax[0])
ax[0].set_title('chi(q, w)')
pl1 = ax[1].pcolormesh(q_path.k_axis[::fac], w * tev, np.log10(w[:, None] * s[0,0].T + 1e-8), vmin=-1.0, vmax=0,
                       shading='auto', rasterized=True, cmap='terrain')
plt.colorbar(pl1, ax=ax[1])
ax[1].set_title('log10 chi(q, w)')
ax[0].set_ylabel('$\omega [eV]$')
ax[1].set_ylabel('$\omega [eV]$')

ax[0].vlines([0.5,0.5+0.25 * np.sqrt(2.)],0,1.0,'k')
ax[1].vlines([0.5,0.5+0.25 * np.sqrt(2.)],0,1.0,'k')
ax[0].hlines([0.2],0,0.5+0.5 * np.sqrt(2.),'k')
ax[1].hlines([0.2],0,0.5+0.5 * np.sqrt(2.),'k')
ax[0].set_ylim(0., 0.5)
ax[1].set_ylim(0., 0.5)
plt.savefig(
    out_dir + 'chi_qpath_err{}_usepreblur_{}_bw{}_alpha_{}_0.pdf'.format(err, use_preblur, bw, alpha_det),
    dpi=300)
plt.savefig(
    out_dir + 'chi_qpath_err{}_usepreblur_{}_bw{}_alpha_{}_0.png'.format(err, use_preblur, bw, alpha_det),
    dpi=300)
plt.show()
plt.close()


###################
fig, ax = plt.subplots(nrows=2, ncols=1, figsize=(14, 8))
pl0 = ax[0].pcolormesh(q_path.k_axis[::fac], w * tev, w[:, None] * s[1,0].T, shading='auto',
                       rasterized=True, cmap='terrain')
plt.colorbar(pl0, ax=ax[0])
ax[0].set_title('chi(q, w)')
pl1 = ax[1].pcolormesh(q_path.k_axis[::fac], w * tev, np.log10(w[:, None] * s[1,0].T + 1e-8), vmin=-1.0, vmax=0,
                       shading='auto', rasterized=True, cmap='terrain')
plt.colorbar(pl1, ax=ax[1])
ax[1].set_title('log10 chi(q, w)')
ax[0].set_ylabel('$\omega [eV]$')
ax[1].set_ylabel('$\omega [eV]$')

ax[0].vlines([0.5,0.5+0.25 * np.sqrt(2.)],0,1.0,'k')
ax[1].vlines([0.5,0.5+0.25 * np.sqrt(2.)],0,1.0,'k')
ax[0].hlines([0.2],0,0.5+0.5 * np.sqrt(2.),'k')
ax[1].hlines([0.2],0,0.5+0.5 * np.sqrt(2.),'k')
ax[0].set_ylim(0., 0.5)
ax[1].set_ylim(0., 0.5)
plt.savefig(
    out_dir + 'chi_qpath_err{}_usepreblur_{}_bw{}_alpha_{}_10.pdf'.format(err, use_preblur, bw, alpha_det),
    dpi=300)
plt.savefig(
    out_dir + 'chi_qpath_err{}_usepreblur_{}_bw{}_alpha_{}_10.png'.format(err, use_preblur, bw, alpha_det),
    dpi=300)
plt.show()
plt.close()



# plt.figure()
# plt.plot(_q_grid.kx[q_path.ikx])
# plt.plot(_q_grid.ky[q_path.iky])
# plt.savefig(out_dir + 'q_path.png'.format(err, use_preblur, bw, alpha_det), dpi=300)
# plt.show()
# plt.close()
