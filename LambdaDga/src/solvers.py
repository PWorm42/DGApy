import sys
import numpy as np
import scipy.optimize as opt
import kernels

if sys.version_info[0] > 2:
    try:
        from LambdaDga.ana_cont import pade
    except:
        pass
else:
    try:
        import pade
    except:
        pass


class AnalyticContinuationSolver(object):
    pass


class PadeSolver(AnalyticContinuationSolver):
    def __init__(self, im_axis, re_axis, im_data):
        self.im_axis = im_axis
        self.re_axis = re_axis
        self.im_data = im_data

        # Compute the Pade coefficients
        self.a = pade.compute_coefficients(1j * self.im_axis, self.im_data)

    def check(self, show_plot=False, im_axis_fine=None):
        # As a check, look if Pade approximant smoothly interpolates the original data
        if im_axis_fine is None:
            self.ivcheck = np.linspace(0, 2 * np.max(self.im_axis), num=500)
        else:
            self.ivcheck = im_axis_fine
        check = pade.C(self.ivcheck * 1j, 1j * self.im_axis,
                            self.im_data, self.a)
        return check

    def solve(self, show_plot=False):
        # Compute the Pade approximation on the real axis

        def numerator_function(z):
            return pade.A(z, self.im_axis.shape[0],
                           1j * self.im_axis, self.im_data, self.a)
        # numerator_function = np.vectorize(numerator_function)
        #
        def denominator_function(z):
            return pade.B(z, self.im_axis.shape[0],
                           1j * self.im_axis, self.im_data, self.a)
        # denominator_function = np.vectorize(denominator_function)
        #
        # numerator = np.array([numerator_function(x) for x in self.re_axis])
        # denominator = np.array([denominator_function(x) for x in self.re_axis])
        numerator = pade.A(self.re_axis, self.im_axis.shape[0],
                           1j * self.im_axis, self.im_data, self.a)
        denominator = pade.B(self.re_axis, self.im_axis.shape[0],
                           1j * self.im_axis, self.im_data, self.a)
        # numerator = pade.A(self.re_axis, self.im_axis.shape[0],
        #                    1j * self.im_axis, self.im_data, self.a)
        # denominator = pade.B(self.re_axis, self.im_axis.shape[0],
        #                    1j * self.im_axis, self.im_data, self.a)

        # self.result = pade.C(self.re_axis, 1j * self.im_axis,
        #                      self.im_data, self.a)

        self.result = numerator / denominator

        sol = OptimizationResult()
        sol.numerator = numerator
        sol.denominator = denominator
        sol.numerator_function = numerator_function
        sol.denominator_function = denominator_function
        sol.check = self.check()
        sol.ivcheck = self.ivcheck
        sol.A_opt = -self.result.imag / np.pi
        sol.g_ret = numerator / denominator

        return sol


class MaxentSolverPlain(AnalyticContinuationSolver):
    def log(self, msg):
        if self.verbose: print(msg)

    def __init__(self, im_axis, re_axis, im_data,
                 kernel_mode='', model=None,
                 stdev=None, cov=None,
                 offdiag=False,
                 preblur=False, blur_width=0.,
                 optimizer='newton',
                 verbose=True, **kwargs):

        import cupy as cp
        self.cp = cp

        self.verbose = verbose

        self.kernel_mode = kernel_mode
        self.im_axis = im_axis
        self.re_axis = re_axis
        self.im_data = im_data
        self.offdiag = offdiag
        self.optimizer = optimizer

        self.nw = self.re_axis.shape[0]
        self.wmin = self.re_axis[0]
        self.wmax = self.re_axis[-1]
        self.dw = np.diff(
            np.concatenate(([self.wmin],
                            (self.re_axis[1:] + self.re_axis[:-1]) / 2.,
                            [self.wmax])))
        if not self.offdiag:
            self.model = model  # the model should be normalized by the user himself
        else:
            self.model_plus = model  # the model should be normalized by the user himself
            self.model_minus = model  # the model should be normalized by the user himself

        if cov is None and stdev is not None:
            self.var = stdev ** 2
            self.cov = np.diag(self.var)
            self.ucov = np.eye(self.im_axis.shape[0])
        elif stdev is None and cov is not None:
            self.cov = cov
            self.var, self.ucov = np.linalg.eigh(self.cov)  # go to eigenbasis of covariance matrix
            self.var = np.abs(self.var)  # numerically, var can be zero below machine precision

        self.im_data = np.dot(self.ucov.T.conj(), self.im_data)
        self.E = 1. / self.var
        self.niw = self.im_axis.shape[0]

        # set the kernel
        self.kernel = kernels.Kernel(kind=kernel_mode,
                                     im_axis=self.im_axis,
                                     re_axis=self.re_axis)

        # PREBLUR
        self.preblur = preblur
        if self.preblur:
            self.kernel.preblur(blur_width=blur_width)

        # rotate kernel to eigenbasis of covariance matrix
        self.kernel.rotate_to_cov_eb(ucov=self.ucov)

        # special treatment for complex data of fermionic frequency kernel
        if kernel_mode == 'freq_fermionic':
            self.niw *= 2
            self.im_data = np.concatenate((self.im_data.real, self.im_data.imag))
            self.var = np.concatenate((self.var, self.var))
            self.E = np.concatenate((self.E, self.E))

        self.d2chi2 = np.einsum('i,j,ki,kj,k->ij', self.dw, self.dw,
                            self.kernel.real_matrix(), self.kernel.real_matrix(),
                            self.E)
        self.B = self.kernel.real_matrix() * self.dw[None, :] * self.E[:, None]

    def compute_f_J_diag(self, A, alpha):
        bt = self.backtransform(A)
        bt = np.concatenate((bt.real, bt.imag))
        f = (-np.sum(self.B * (self.im_data - bt)[:, None])
             + alpha * self.dw * (np.log(np.abs(A)) - np.log(self.model)))
        J = self.d2chi2 + alpha * np.diag(self.dw / A)
        return f, J

    def backtransform(self, A):
        """ Backtransformation from real to imaginary axis.
        G(iw) = \int dw K(iw, w) * A(w)
        Also at this place we return from the 'diagonal-covariance space'
        Note: this function is not a bottleneck.
        """
        ucov = self.cp.asarray(self.ucov)
        km = self.cp.asarray(self.kernel.matrix)
        a = self.cp.asarray(A * self.dw)
        return self.cp.dot(self.cp.dot(ucov, km), a)
        return np.trapz(np.dot(self.ucov, self.kernel.matrix) * A[None, :],
                        self.re_axis, axis=-1)

    def entropy_pos(self, A):
        return np.trapz(A - self.model - A * np.log(A / self.model), self.re_axis)

    def chi2(self, A):
        bt = self.backtransform(A)
        bt = np.concatenate((bt.real, bt.imag))
        return np.sum(np.abs(self.im_data - bt)**2 * self.E)


    def maxent_optimization(self, alpha, A_start, **kwargs):
        if not self.offdiag:
            self.compute_f_J = self.compute_f_J_diag
            self.entropy = self.entropy_pos
        else:
            self.compute_f_J = self.compute_f_J_offdiag
            self.entropy = self.entropy_posneg

        if self.optimizer == 'newton':
            max_hist = kwargs['max_hist']
            newton_solver = NewtonOptimizer(self.nw, initial_guess=A_start, max_hist=max_hist)
            sol = newton_solver(self.compute_f_J, alpha)
        else:
            raise NotImplementedError('Only newton optimizer currently available')

        A_opt = sol.x
        entr = self.entropy(A_opt)
        chisq = self.chi2(A_opt)
        norm = np.trapz(A_opt, self.re_axis)
        self.log('log10(alpha)={:6.4f}\tchi2={:5.4e}\tS={:5.4e}\tnfev={},\tnorm={}'.format(
            np.log10(alpha), chisq, entr, sol.nfev, norm))

        result = OptimizationResult()
        if self.preblur:
            result.A_opt = self.kernel.blur(A_opt)
            result.blur_width = self.kernel.blur_width
        else:
            result.A_opt = A_opt
            result.blur_width = 0.
        result.alpha = alpha
        result.entropy = entr
        result.chi2 = chisq
        result.backtransform = self.backtransform(A_opt)
        result.norm = norm
        result.Q = alpha * entr - 0.5 * chisq
        return result

class MaxentSolverSVD(AnalyticContinuationSolver):


    def log(self, msg):
        if self.verbose: print(msg)


    def __init__(self, im_axis, re_axis, im_data,
                 kernel_mode='', model=None,
                 stdev=None, cov=None,
                 offdiag=False,
                 preblur=False, blur_width=0.,
                 optimizer='scipy_lm', 
                 verbose=True, **kwargs):

        self.verbose = verbose

        self.kernel_mode = kernel_mode
        self.im_axis = im_axis
        self.re_axis = re_axis
        self.im_data = im_data
        self.offdiag = offdiag
        self.optimizer = optimizer

        self.nw = self.re_axis.shape[0]
        self.wmin = self.re_axis[0]
        self.wmax = self.re_axis[-1]
        self.dw = np.diff(
            np.concatenate(([self.wmin],
                            (self.re_axis[1:] + self.re_axis[:-1]) / 2.,
                            [self.wmax])))
        if not self.offdiag:
            self.model = model  # the model should be normalized by the user himself
        else:
            self.model_plus = model  # the model should be normalized by the user himself
            self.model_minus = model  # the model should be normalized by the user himself

        if cov is None and stdev is not None:
            self.var = stdev ** 2
            self.cov = np.diag(self.var)
            self.ucov = np.eye(self.im_axis.shape[0])
        elif stdev is None and cov is not None:
            self.cov = cov
            self.var, self.ucov = np.linalg.eigh(self.cov)  # go to eigenbasis of covariance matrix
            self.var = np.abs(self.var)  # numerically, var can be zero below machine precision

        self.im_data = np.dot(self.ucov.T.conj(), self.im_data)
        self.E = 1. / self.var
        self.niw = self.im_axis.shape[0]

        # set the kernel
        self.kernel = kernels.Kernel(kind=kernel_mode,
                                     im_axis=self.im_axis,
                                     re_axis=self.re_axis)

        # PREBLUR
        self.preblur = preblur
        if self.preblur:
            self.kernel.preblur(blur_width=blur_width)

        # rotate kernel to eigenbasis of covariance matrix
        self.kernel.rotate_to_cov_eb(ucov=self.ucov)

        # special treatment for complex data of fermionic frequency kernel
        if kernel_mode == 'freq_fermionic':
            self.niw *= 2
            self.im_data = np.concatenate((self.im_data.real, self.im_data.imag))
            self.var = np.concatenate((self.var, self.var))
            self.E = np.concatenate((self.E, self.E))

        # singular value decomposition of the kernel
        U, S, Vt = np.linalg.svd(self.kernel.real_matrix(), full_matrices=False)

        self.n_sv = np.arange(min(self.nw, self.niw))[S > 1e-10][-1]  # number of singular values larger than 1e-10

        self.U_svd = np.array(U[:, :self.n_sv], dtype=np.float64, order='C')
        self.V_svd = np.array(Vt[:self.n_sv, :].T, dtype=np.float64, order='C')  # numpy.svd returns V.T
        self.Xi_svd = S[:self.n_sv]

        self.log('{} data points on real axis'.format(self.nw))
        self.log('{} data points on imaginary axis'.format(self.niw))
        self.log('{} significant singular values'.format(self.n_sv))

        # =============================================================================================
        # First, precompute as much as possible
        # The precomputation of W2 is done in C, this saves a lot of time!
        # The other precomputations need less loop, can stay in python for the moment.
        # =============================================================================================
        self.log('Precomputation of coefficient matrices...')

        if not self.offdiag:  # precompute matrices W_ml (W2), W_mil (W3)
            self.W2 = np.einsum('k,km,m,kn,n,ln,l,l->ml', self.E, self.U_svd, self.Xi_svd, self.U_svd, self.Xi_svd,
                                self.V_svd, self.dw, self.model)
            self.W3 = self.W2[:, None, :] * (self.V_svd[None, :, :]).transpose((0, 2, 1))

        else:  # precompute matrices M_ml (M2), M_mil (M3)
            self.M2 = np.einsum('k,km,m,kn,n,ln,l->ml', self.E, self.U_svd, self.Xi_svd, self.U_svd, self.Xi_svd,
                                self.V_svd, self.dw)
            self.M3 = self.M2[:, None, :] * (self.V_svd[None, :, :]).transpose((0, 2, 1))

        # precompute the evidence vector Evi_m
        self.Evi = np.einsum('m,km,k,k->m', self.Xi_svd, self.U_svd, self.E, self.im_data)

        # precompute curvature of likelihood function
        self.d2chi2 = np.einsum('i,j,ki,kj,k->ij', self.dw, self.dw,
                                self.kernel.real_matrix(), self.kernel.real_matrix(),
                                self.E)

        # some arrays that are used later...
        self.chi2arr = []
        self.specarr = []
        self.backarr = []
        self.entrarr = []
        self.alpharr = []
        self.uarr = []
        self.bayesConv = []

    # =============================================================================================
    # Here, we define the main functions needed for the root finding problem
    # =============================================================================================

    def compute_f_J_diag(self, u, alpha):
        """This function evaluates the function whose root we want to find.

        The function f_m(u) is defined as the singular value decomposition
        of the derivative dQ[A]/dA_m. Since we want to minimize Q[A],
        we have to find the root of the vector-valued function f, i.e.
        f_m(u) = SVD(dQ/dA)_m = 0.
        For more efficient root finding, we also need the Jacobian J.
        It is directly computed in singular space, J_mi=df_m/du_i.
        """

        v = np.dot(self.V_svd, u)
        w = np.exp(v)
        term_1 = np.dot(self.W2, w)
        term_2 = np.dot(self.W3, w)
        f = alpha * u + term_1 - self.Evi
        J = alpha * np.eye(self.n_sv) + term_2
        return f, J

    def compute_f_J_offdiag(self, u, alpha):
        """The analogue to compute_f_J_diag for offdiagonal elements."""
        v = np.dot(self.V_svd, u)
        w = np.exp(v)
        a_plus = self.model_plus * w
        a_minus = self.model_minus / w
        a1 = a_plus - a_minus
        a2 = a_plus + a_minus
        f = alpha * u + np.dot(self.M2, a1) - self.Evi
        J = alpha * np.eye(self.n_sv) + np.dot(self.M3, a2)
        return f, J

    # =============================================================================================
    # Some auxiliary functions
    # =============================================================================================

    def singular_to_realspace_diag(self, u):
        """transform the singular space vector u into real-frequency space (spectral function)"""
        return self.model * np.exp(np.dot(self.V_svd, u))

    def singular_to_realspace_offdiag(self, u):
        """transform the singular space vector u into real-frequency
        space in the case of an offdiagonal element."""
        v = np.dot(self.V_svd, u)
        w = np.exp(v)
        return self.model_plus * w - self.model_minus / w

    def backtransform(self, A):
        """ Backtransformation from real to imaginary axis.
        G(iw) = \int dw K(iw, w) * A(w)
        Also at this place we return from the 'diagonal-covariance space'
        Note: this function is not a bottleneck. 
        """
        return np.trapz(np.dot(self.ucov, self.kernel.matrix) * A[None, :],
                        self.re_axis, axis=-1)

    def chi2(self, A):
        """compute the log-likelihood function of A"""
        # import matplotlib.pyplot as plt
        # # plt.plot(self.im_data)
        # plt.semilogy(np.abs(self.im_data - np.trapz(self.kernel.real_matrix() * A[None, :], self.re_axis, axis=-1)))
        # plt.semilogy(1. / np.sqrt(self.E))
        # plt.show()
        return np.sum(
            self.E * (self.im_data - np.trapz(self.kernel.real_matrix() * A[None, :], self.re_axis, axis=-1)) ** 2)

    def entropy_pos(self, A, u):
        """Compute entropy for positive definite spectral function."""
        # return np.trapz(A - self.model - A * (np.log(A) - np.log(self.model)), self.re_axis)
        return np.trapz(A - self.model - A * np.dot(self.V_svd, u), self.re_axis)

    def entropy_posneg(self, A, u):
        """Compute "positive-negative entropy" for spectral function with norm 0."""
        root = np.sqrt(A ** 2 + 4. * self.model_plus * self.model_minus)
        return np.trapz(root - self.model_plus - self.model_minus
                        - A * np.log((root + A) / (2. * self.model_plus)),
                        self.re_axis)

    def bayes_conv(self, A, entr, alpha):
        """Bayesian convergence criterion for classic maxent (maximum of probablility distribution)"""
        LambdaMatrix = np.sqrt(A / self.dw)[:, None] * self.d2chi2 * np.sqrt(A / self.dw)[None, :]
        try:
            lam = np.linalg.eigvalsh(LambdaMatrix)
        except np.linalg.LinAlgError:
            self.log('LinAlgError in Bayes matrix inversion. Irrelevant for chi2kink')
            lam = np.diag(LambdaMatrix)
        ng = -2. * alpha * entr
        tr = np.sum(lam / (alpha + lam))
        conv = tr / ng
        # print('entropy={}, trace={}, -2 alpha S / trace = {}'.format(entr, tr, ng / tr))
        return ng, tr, conv

    def bayes_conv_offdiag(self, A, entr, alpha):
        """Bayesian convergence criterion for classic maxent, offdiagonal version"""
        A_sq = np.power((A ** 2 + 4. * self.model_plus * self.model_minus) / self.dw ** 2, 0.25)
        LambdaMatrix = A_sq[:, None] * self.d2chi2 * A_sq[None, :]
        lam = np.linalg.eigvalsh(LambdaMatrix)
        ng = -2. * alpha * entr
        tr = np.sum(lam / (alpha + lam))
        conv = tr / ng
        return ng, tr, conv

    def posterior_probability(self, A, alpha, entr, chisq):
        """Bayesian a-posteriori probability for alpha after optimization of A"""
        lambda_matrix = np.sqrt(A / self.dw)[:, None] * self.d2chi2 * np.sqrt(A / self.dw)[None, :]
        try:
            lam = np.linalg.eigvalsh(lambda_matrix)
        except np.linalg.LinAlgError:
            self.log('LinAlgError in Bayes matrix inversion. Irrelevant for chi2kink')
            lam = np.diag(lambda_matrix)
        try:
            eig_sum = np.sum(np.log(alpha / (alpha + lam)))
        except RuntimeWarning:
            print(lam)
        log_prob = alpha * entr - 0.5 * chisq + np.log(alpha) + 0.5 * eig_sum
        return np.exp(log_prob)

    def maxent_optimization(self, alpha, ustart, iterfac=10000000, use_bayes=False, **kwargs):
        """optimization of maxent functional for a given value of alpha"""

        if not self.offdiag:
            self.compute_f_J = self.compute_f_J_diag
            self.singular_to_realspace = self.singular_to_realspace_diag
            self.entropy = self.entropy_pos
        else:
            self.compute_f_J = self.compute_f_J_offdiag
            self.singular_to_realspace = self.singular_to_realspace_offdiag
            self.entropy = self.entropy_posneg

        if self.optimizer == 'newton':
            newton_solver = NewtonOptimizer(self.n_sv, initial_guess=ustart, max_hist=1)
            sol = newton_solver(self.compute_f_J, alpha)
        elif self.optimizer == 'scipy_lm':
            sol = opt.root(self.compute_f_J,  # function returning function value f and jacobian J (we search root of f)
                          ustart,  # sensible starting point
                          method='lm',  # levenberg-marquart method
                          jac=True,  # already self.compute_f_J returns the jacobian (slightly more efficient in this case)
                          options={'maxiter': iterfac * self.n_sv,  # max number of lm steps
                                   'factor': 100.,  # scale for initial stepwidth of lm (?)
                                   'diag': np.exp(np.arange(self.n_sv))},
                          # scale for values to find (assume that they decay exponentially)
                          args=(alpha))  # additional argument for self.compute_f_J

        u_opt = sol.x
        A_opt = self.singular_to_realspace(sol.x)
        entr = self.entropy(A_opt, u_opt)
        chisq = self.chi2(A_opt)
        norm = np.trapz(A_opt, self.re_axis)
        if use_bayes:
            if not self.offdiag:
                ng, tr, conv = self.bayes_conv(A_opt, entr, alpha)
            else:
                ng, tr, conv = self.bayes_conv_offdiag(A_opt, entr, alpha)

        # self.log('log10(alpha)={:6.4f}\tchi2={:5.4e}\tS={:5.4e}\ttr={:5.4f}\tconv={:1.3},\tnfev={},\tnorm={}'.format(
        #     np.log10(alpha), chisq, entr, tr, conv, sol.nfev, norm))
        self.log('log10(alpha) = {:3.2f},\tchi2 = {:4.3e},   S = {:4.3e},   nfev = {},   norm = {:4.3f}'.format(
            np.log10(alpha), chisq, entr, sol.nfev, norm))

        result = OptimizationResult()
        result.u_opt = u_opt
        if self.preblur:
            result.A_opt = self.kernel.blur(A_opt)
            result.blur_width = self.kernel.blur_width
        else:
            result.A_opt = A_opt
            result.blur_width = 0.
        result.alpha = alpha
        result.entropy = entr
        result.chi2 = chisq
        result.backtransform = self.backtransform(A_opt)
        result.norm = norm
        result.Q = alpha * entr - 0.5 * chisq

        if use_bayes:
            result.n_good = ng
            result.trace = tr
            result.convergence = conv
            if not self.offdiag:
                result.probability = self.posterior_probability(A_opt, alpha, entr, chisq)

        return result

    # =============================================================================================
    # Now actually solve the problem!
    # =============================================================================================

    def solve_historic(self):
        """ Historic Maxent: choose alpha in a way that chi^2 \approx N """

        if not self.offdiag:
            self.compute_f_J = self.compute_f_J_diag
            self.singular_to_realspace = self.singular_to_realspace_diag
            self.entropy = self.entropy_pos
        else:
            self.compute_f_J = self.compute_f_J_offdiag
            self.singular_to_realspace = self.singular_to_realspace_offdiag
            self.entropy = self.entropy_posneg
        self.log('Solving...')
        optarr = []
        alpha = 10 ** 6
        self.ustart = np.zeros((self.n_sv))
        converged = False
        conv = 0.
        while conv < 1:
            o = self.maxent_optimization(alpha, self.ustart)
            optarr.append(o)
            alpha /= 10.
            conv = self.niw / o.chi2

        if len(optarr) <= 1:
            raise RuntimeError('Failed to get a prediction for optimal alpha. '
                               + 'Decrease the error or increase alpha_start.')

        def root_fun(alpha, u0):  # this function is just for the newton root-finding
            res = self.maxent_optimization(alpha, u0, iterfac=100000)
            optarr.append(res)
            u0[:] = res.u_opt
            return self.niw / res.chi2 - 1.

        ustart = optarr[-2].u_opt
        alpha_opt = opt.newton(root_fun, optarr[-1].alpha, tol=1e-6, args=(ustart,))
        self.log('final optimal alpha: {}, log10(alpha_opt) = '.format(alpha_opt, np.log10(alpha_opt)))

        sol = self.maxent_optimization(alpha_opt, ustart, iterfac=250000)
        self.alpha_opt = alpha_opt
        self.A_opt = sol.A_opt
        return sol, optarr


    def solve_classic(self):
        """Classic maxent alpha determination.

        Classic maxent uses Bayes statistics to approximately determine
        the most probable value of alpha
        We start at a large value of alpha, where the optimization yields basically the default model,
        therefore u_opt is only a few steps away from ustart=0 (=default model)
        Then we gradually decrease alpha, step by step moving away from the default model towards data fitting.
        Using u_opt as ustart for the next (smaller) alpha brings a great speedup into this procedure.
        """
        if not self.offdiag:
            self.compute_f_J = self.compute_f_J_diag
            self.singular_to_realspace = self.singular_to_realspace_diag
            self.entropy = self.entropy_pos
        else:
            self.compute_f_J = self.compute_f_J_offdiag
            self.singular_to_realspace = self.singular_to_realspace_offdiag
            self.entropy = self.entropy_posneg
        self.log('Solving...')
        optarr = []
        alpha = 10 ** 6
        self.ustart = np.zeros((self.n_sv))
        converged = False
        conv = 0.
        while conv < 1:
            o = self.maxent_optimization(alpha, self.ustart, use_bayes=True)

            ustart = o.u_opt
            optarr.append(o)
            alpha /= 10.
            conv = o.convergence

        if len(optarr) <= 1:
            raise RuntimeError('Failed to get a prediction for optimal alpha. '
                               + 'Decrease the error or increase alpha_start.')

        bayes_conv = [o.convergence for o in optarr]
        alpharr = [o.alpha for o in optarr]

        # log(conv) is approximately a linear function from log(alpha),
        # based on this we can predict the optimal alpha quite precisely.
        exp_opt = np.log10(alpharr[-2]) \
                 - np.log10(bayes_conv[-2]) * (np.log10(alpharr[-1])
                                               - np.log10(alpharr[-2])) \
                   / (np.log10(bayes_conv[-1]) - np.log10(bayes_conv[-2]))
        alpha_opt = 10 ** exp_opt
        self.log('prediction for optimal alpha: {}, log10(alpha_opt) = {}'.format(alpha_opt, np.log10(alpha_opt)))

        # Starting from the predicted value of alpha, and starting the optimization at the solution for the next-lowest alpha,
        # we find the optimal alpha by newton's root finding method.

        def root_fun(alpha, u0):  # this function is just for the newton root-finding
            res = self.maxent_optimization(alpha, u0, iterfac=100000, use_bayes=True)
            optarr.append(res)
            u0[:] = res.u_opt
            return res.convergence - 1.

        ustart = optarr[-2].u_opt
        alpha_opt = opt.newton(root_fun, alpha_opt, tol=1e-6, args=(ustart,))
        self.log('final optimal alpha: {}, log10(alpha_opt) = '.format(alpha_opt, np.log10(alpha_opt)))

        sol = self.maxent_optimization(alpha_opt, ustart, iterfac=250000, use_bayes=True)
        self.alpha_opt = alpha_opt
        self.A_opt = sol.A_opt
        return sol, optarr


    def solve_bryan(self, alphastart=500, alphadiv=1.1, interactive=False):
        """Bryan's method of determining the optimal spectrum.

        Bryan's maxent calculates an average of spectral functions,
        weighted by their Bayesian probability
        """
        self.log('Solving...')
        optarr = []
        alpha = alphastart
        self.ustart = np.zeros((self.n_sv))
        maxprob = 0.
        while True:
            o = self.maxent_optimization(alpha, self.ustart, use_bayes=True)
            ustart = o.u_opt
            optarr.append(o)
            alpha /= alphadiv
            prob = o.probability
            # automatically terminate the loop when probability is small again
            if prob > maxprob:
                maxprob = prob
            elif prob < 0.01 * maxprob:
                break

        alpharr = np.array([o.alpha for o in optarr])
        probarr = np.array([o.probability for o in optarr])
        specarr = np.array([o.A_opt for o in optarr])
        probarr /= -np.trapz(probarr, alpharr)  # normalize the probability distribution
        if interactive:
            fig = plt.figure()
            plt.plot(np.log10(alpharr), probarr)
            fig.show()

        # calculate the weighted average spectrum
        A_opt = -np.trapz(specarr * probarr[:, None], alpharr,
                          axis=0)  # need a "-" sign, because alpha goes from large to small.

        sol = OptimizationResult()
        sol.A_opt = A_opt
        sol.backtransform = self.backtransform(A_opt)
        return sol, optarr

    def solve_chi2kink(self, alpha_start=1e9, alpha_end=1e-3, alpha_div=10., fit_position=2.5, interactive=False, **kwargs):
        """Determine optimal alpha by searching for the kink in log(chi2) (log(alpha))

        We start with an optimization at a large value of alpha (alpha_start),
        where we should get only the default model. Then, alpha is decreased
        step-by-step, where alpha_{n+1} = alpha_n / alpha_div, until the minimal
        value of alpha_end is reached.
        Then, we fit a function
        \phi(x; a, b, c, d) = a + b / [1 + exp(-d*(x-c))],
        from which the optimal alpha is determined by
        x_opt = c - fit_position / d; alpha_opt = 10^x_opt.
        """

        if interactive:
            import matplotlib.pyplot as plt

        alpha = alpha_start
        chi = []
        alphas = []
        optarr = []
        ustart=np.zeros((self.n_sv))
        while True:
            try:
                o = self.maxent_optimization(alpha=alpha, ustart=ustart)
                optarr.append(o)
                ustart = o.u_opt
                chi.append(o.chi2)
                alphas.append(alpha)
            except:
                print('Optimization at alpha={} failed.'.format(alpha))
            alpha = alpha / alpha_div
            if alpha < alpha_end:
                break

        alphas = np.asarray(alphas)
        chis = np.asarray(chi)

        def fitfun(x, a, b, c, d):
            return a + b / (1. + np.exp(-d * (x - c)))

        try:
            good_numbers = np.isfinite(chis)
            popt, pcov = opt.curve_fit(fitfun,
                                       np.log10(alphas[good_numbers]),
                                       np.log10(chis[good_numbers]),
                                       p0=(0., 5., 2., 0.))
        except ValueError:
            print('Fermi fit failed.')
            if interactive:
                plt.plot(np.log10(alphas), np.log10(chis), marker='s')
                plt.show()
                for o in optarr:
                    plt.plot(o.backtransform)
                plt.plot(self.im_data)
                plt.show()
            return (optarr[-1], optarr)

        a, b, c, d = popt

        if interactive:
            print('Fit parameters {}'.format(popt))
        if d < 0.:
            raise RuntimeError('Fermi fit temperature negative.')

        a_opt = c - fit_position / d
        alpha_opt = 10. ** a_opt
        self.log('Optimal log alpha {}'.format(a_opt))

        if interactive:
            plt.plot(np.log10(alphas), np.log10(chis), marker='s', label='chi2')
            plt.plot(np.log10(alphas), fitfun(np.log10(alphas), *popt), label='fit2lin')
            #plt.plot(np.log10(alphas), chi2_interp(np.log10(alphas)), label='chi2 fit')

        closest_idx = np.argmin(np.abs(np.log10(alphas) - a_opt))
        ustart = optarr[closest_idx].u_opt
        sol = self.maxent_optimization(alpha_opt, ustart)

        if interactive:
            plt.plot(a_opt, np.log10(sol.chi2), marker='s', color='red', label='opt')
            plt.legend()
            plt.show()

        return sol, optarr



    def error_propagation(self, obs, args):
        """Calculate the deviation for a callable function obs.
        This feature is still experimental"""
        hess = -self.d2chi2
        hess += self.alpha_opt * np.diag(1. / self.A_opt) \
                * self.dw[:, None] * self.dw[None, :]  # possibly, it's 2*alpha
        varmat = np.linalg.inv(hess)  # TODO actually here should be a minus...
        obsval = obs(self.re_axis, args)
        integrand = obsval[:, None] * obsval[None, :] \
                    * varmat * self.dw[:, None] * self.dw[None, :]
        deviation = np.sum(integrand)
        return deviation

    def solve(self, **kwargs):
        """Wrapper function for solve, which calls the chosen
        method of alpha_determination."""
        alpha_determination = kwargs['alpha_determination']
        if alpha_determination == 'historic':
            return self.solve_historic()
        elif alpha_determination == 'classic':
            return self.solve_classic()
        elif alpha_determination == 'bryan':
            return self.solve_bryan()
        elif alpha_determination == 'chi2kink':
            return self.solve_chi2kink(**kwargs)
        else:
            raise ValueError('Unknown alpha determination mode')


class OptimizationResult(object):
    """Dummy object for holding the result of an optimization."""

    def __init__(self):
        self.u_opt = None
        self.A_opt = None
        self.chi2 = None
        self.backtransform = None
        self.entropy = None
        self.n_good = None
        self.probability = None
        self.alpha = None
        self.convergence = None
        self.trace = None


class NewtonOptimizer(object):
    """Newton root finding."""

    def __init__(self, opt_size, max_hist=1, max_iter=20000, initial_guess=None):
        """
        :param opt_size: number of variables (integer)
        :param max_hist: maximal history for mixing (integer)
        :param max_iter: maximum number of iterations for root finding
        :param initial_guess: initial guess for the root finding.
        """

        if initial_guess is None:
            initial_guess = np.zeros((opt_size))

        self.props = [initial_guess]
        self.res = []
        self.max_hist = max_hist
        self.max_iter = max_iter
        self.opt_size = opt_size
        self.return_object = OptimizationResult()

    def iteration_function(self, proposal, function_vector, jacobian_matrix):
        """The function, whose fixed point we are searching.

        This function generates the iteration procedure in the Newton root finding.
        Basically, it computes the "result" from the "proposal".
        It has the form result = proposal + increment, but
        since the increment may be large, we apply a reduction of step width in such cases.
        """

        try:
            increment = -np.dot(np.linalg.pinv(jacobian_matrix), function_vector)
        except np.linalg.LinAlgError:
            print('LinAlgError in Newton Solver, setting increment to zero')
            increment = np.zeros_like(proposal)
        step_reduction = 1.
        significance_limit = 1e-4
        if np.any(np.abs(proposal) > significance_limit):
            ratio = np.abs(increment / proposal)
            max_ratio = np.amax(ratio[np.abs(proposal) > significance_limit])
            if max_ratio > 1.:
                step_reduction = 1. / max_ratio
        result = proposal + step_reduction * increment
        return result

    def __call__(self, function_and_jacobian, alpha):
        """Main function of Newton optimization.

        This function implements the self-consistent iteration of the root finding.
        """
        f, J = function_and_jacobian(self.props[0], alpha)
        initial_result = self.iteration_function(self.props[0], f, J)
        self.res.append(initial_result)

        counter = 0
        converged = False
        while not converged:
            prop = self.get_proposal()
            f, J = function_and_jacobian(prop, alpha)
            result = self.iteration_function(prop, f, J)
            self.props.append(prop)
            self.res.append(result)
            converged = (counter > self.max_iter or np.max(np.abs(result - prop)) < 1e-4)
            counter += 1
            if np.any(np.isnan(result)):
                raise RuntimeWarning('Function returned NaN.')
        if counter > self.max_iter:
            raise RuntimeWarning('Failed to get optimization result in {} iterations'.format(self.max_iter))
        #print('{} iterations, solution {}'.format(counter, result))

        self.return_object.x = result
        self.return_object.nfev = counter
        return self.return_object

    def get_proposal(self, mixing=0.5):
        """Propose a new solution by linear mixing."""

        n_iter = len(self.props)
        history = min(self.max_hist, n_iter) - 1

        new_proposal = self.props[n_iter - 1]
        f_i = self.res[n_iter - 1] - self.props[n_iter - 1]
        update = mixing * f_i
        return new_proposal + update

        # Here is also an implementation of the Anderson acceleration.
        # Unfortunately, for the singular-space algorithm, it seems to fail...
        # if n_iter < 10 or history == 0:# or n_iter%4!=0:  # linear mixing
        #     return new_proposal + update  # this is still correct!
        #
        # R = np.zeros((self.opt_size, history), dtype=np.float)
        # G = np.zeros((self.opt_size, history), dtype=np.float)
        # for k in range(history):
        #     R[:, k] = self.props[n_iter - history + k] - self.props[n_iter - history + k - 1]
        #     G[:, k] = self.res[n_iter - history + k] - self.res[n_iter - history + k - 1]
        # F = G - R
        # inverse = np.linalg.pinv(np.dot(F.transpose(), F))
        # h_j = np.dot(F.transpose(), f_i)
        # fact1 = np.dot(R + mixing * F, inverse)
        # update = mixing * f_i - np.dot(fact1, h_j)
        #
        # return new_proposal + update
