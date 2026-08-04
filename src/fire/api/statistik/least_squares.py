from functools import cached_property

import numpy as np
from numpy import ndarray
from numpy.polynomial import polynomial as P
from scipy.stats import t, norm

__all__ = [
    "WeightedLeastSquares",
    "OrdinaryLeastSquares",
    "PolynomialRegression",
    "compute_confidence_interval_t_distribution",
    "compute_confidence_interval_normal_distribution",
]


class WeightedLeastSquares:
    def __init__(
        self,
        X: ndarray,
        W: ndarray,
        y: ndarray,
    ):
        """
        Solves WLS problems of the form:

        X·θ = y

        by minimizing the weighted squared residuals.

        X is the system matrix, y are the observations, and θ are the unknown coefficients
        and W is the weight matrix of the observations.

        The formulas follow the well known theory of least squares regression.

        References:
            title:
                Least Squares Adjustment:
                Linear and Nonlinear Weighted Regression Analysis
            author:
                Allan Aasbjerg Nielsen
            link:
                https://www2.imm.dtu.dk/pubdb/edoc/imm2804.pdf
        """
        # system matrix [N x M]
        self.X = X

        # system matrix dimensions
        # N = no of observations
        # M = no of estimated parameters
        self.N, self.M = self.X.shape

        # degrees of freedom
        self.dof = self.N - self.M

        # observation vector, [N x 1]
        self.y = y

        # weight matrix, [N x N]
        self.W = W

        self._var0_hat = None

    def invert_normal_matrix(self) -> ndarray:
        """Return the inverse of the normal matrix N⁻¹

        Not appropriate when the problem is ill-conditioned.
        Use the pseudoinverse in that case.

        Raises: LinAlgError: Singular matrix
        """
        return np.linalg.inv(self.normal_matrix)

    def compute_residuals(self) -> ndarray:
        """Compute diffence between observed and modelled observations"""
        self.yhat = self.hat_matrix @ self.y
        return self.y - self.yhat

    def solve(self):
        """Solve the problem by inverting the normal matrix,
        and subsequently computing the estimated coefficients θ.
        """
        if self.dof < 0:
            raise ValueError(
                "System is under-determined. Lower model complexity or consider using "
                "regularized least squares."
            )
        # Invert the normal matrix assuming that no numerical
        # complications arise
        self.inv_normal_matrix = self.invert_normal_matrix()

        self.theta = self.inv_normal_matrix @ self.X.T @ self.W @ self.y

        self.residuals = self.compute_residuals()

        return self.theta, self.residuals

    @cached_property
    def normal_matrix(self) -> ndarray:
        """Return the normal matrix, of shape [M x M]"""
        return self.X.T @ self.W @ self.X

    @cached_property
    def hat_matrix(self) -> ndarray:
        """Return the "hat matrix", of shape [N x N]"""
        hat = self.X @ self.inv_normal_matrix @ self.X.T @ self.W
        return hat

    @cached_property
    def leverage(self) -> ndarray:
        """Leverage of observations

        Leverage is always in the interval [1/N, 1]

        Watch out for observations with leverage=1, as errors in these propagate directly
        to the solution, with no adjustments. It also implies that the estimated variance
        of those observations becomes 0.

        E.g. in levelling, leverage=1, means that the segment is just measured once in one
        direction, and that there are no loops.

        leverage=1 gives all sorts of numerical problems later down the line
        s.a. division by 0 and sqrt of negative numbers.
        leverage can also be slightly > 1 due to numerical instability in the inversion.
        """
        return np.diag(self.hat_matrix)

    @cached_property
    def inv_W(self) -> ndarray:
        """Return the inverse weight matrix"""
        return np.linalg.inv(self.W)

    @cached_property
    def cov_theta(self) -> ndarray:
        """
        Variance-covariance matrix of estimated parameters

        e.g. the estimated heights in a levelling survey
        """
        return self.var0_hat * self.inv_normal_matrix

    @cached_property
    def cov_yhat(self) -> ndarray:
        """
        Variance-covariance matrix of modelled observations ŷ

        e.g. the adjusted height differences
        """
        return self.var0_hat * self.hat_matrix @ self.inv_W

    @cached_property
    def cov_residuals(self) -> ndarray:
        """Variance-covariance matrix of residuals"""
        return self.var0_hat * self.inv_W - self.cov_yhat

    @cached_property
    def std_residuals(self) -> ndarray:
        """Estimated standard deviation of residuals"""
        return np.sqrt(np.diag(self.cov_residuals))

    @cached_property
    def SSR(self) -> float:
        """Weighted "Sum of Squared Residuals" """
        return np.dot(self.W.diagonal(), self.residuals**2)

    @cached_property
    def MSE(self) -> float:
        """Mean Squared Error"""
        return self.SSR / self.dof

    @property
    def var0_hat(self) -> float:
        """
        Estimated variance of residuals

        We use the standard estimator for variance of residuals, namely the MSE.
        If a better estimate is known, this can be overridden (for example by estimating
        the population variance as the pooled variance of multliple samples).
        """
        if self._var0_hat is None:
            self._var0_hat = self.MSE
        return self._var0_hat

    @var0_hat.setter
    def var0_hat(self, value: float):
        """Override the standard estimator for residual variance."""
        self._var0_hat = value

    @property
    def std0_hat(self) -> float:
        """
        Estimated "standard deviation of unit weight"

        aka "spredningen på vægtenheden"
        """
        return np.sqrt(self.var0_hat)

    @cached_property
    def normalized_residuals(self) -> ndarray:
        """aka standardized residual

        obtained by scaling residuals by their estimated std. deviation
        """
        return compute_normalized_residuals(self.residuals, self.std_residuals)

    @cached_property
    def studentized_residuals(self) -> ndarray:
        """aka leave one out residuals"""
        return compute_studentized_residuals(self.normalized_residuals, self.dof)

    @cached_property
    def var_theta(self) -> ndarray:
        """Estimated variances of model parameters"""
        return np.diag(self.cov_theta)

    @cached_property
    def std_theta(self) -> ndarray:
        """Estimated standard deviation of model parameters"""
        return np.sqrt(self.var_theta)

    @cached_property
    def R2(self) -> float:
        """Determination coefficient R²"""
        return 1 - (self.SSR / np.sum((self.y - self.y.mean()) ** 2))


class OrdinaryLeastSquares(WeightedLeastSquares):
    """
    OLS is just WLS with the assumption that all observations have the same variance, and
    thus have unit weight.
    """

    def __init__(self, X: ndarray, y: ndarray):
        W = np.eye(len(y))
        super().__init__(X, W, y)


class PolynomialRegression(WeightedLeastSquares):
    """
    Fit a polynomial to data using WLS

    If `weights` are supplied, there must be one weight per observation.
    Otherwise weights will be defined by the prior variance `var0` as
    `1/sqrt(var0)`.
    """

    def __init__(
        self,
        x: list[float],
        y: list[float],
        degree: int = 1,
        var0: float = 1,
        weights: list[float] = None,
        **kwargs,
    ):
        self.x = np.array(x)
        self.y = np.array(y)
        self.degree = degree

        self.X = self._construct_system_matrix(x, degree)

        self.var0 = var0
        self.weights = (
            np.array(weights) if weights else np.ones(len(self.x)) / np.sqrt(var0)
        )

        if len(self.weights) != len(self.x):
            raise ValueError("Number of weights and observations must be equal")

        self.W = self._construct_weight_matrix()

        # WLS needs the system- and weight matrix and the observation vector.
        super().__init__(self.X, self.W, self.y, **kwargs)

    def compute_predictions(self, x_pred: list[float]) -> ndarray:
        """Compute the value of the regression in the points x_pred."""
        return P.polyval(x_pred, self.theta)

    def compute_cov_predictions(self, X_pred: ndarray) -> ndarray:
        """
        Variance-covariance matrix of predictions made at new values of the explanatory
        variable x

        X_pred should be of shape [N_pred x M], where N_pred is the number of predictions,
        and M is the number of model parameters θ.
        Output covariance matrix will be of shape [N_pred x N_pred]

        If X_pred = X, i.e. the system matrix used to estimate the model θ, then this is
        the same as the variance-covariance matrix of residuals.
        """
        return X_pred @ (self.inv_normal_matrix) @ X_pred.T

    def compute_confidence_band(
        self,
        x_pred: list[float],
        *,
        var_population: float = None,
        alpha: float = 0.05,
    ) -> ndarray:
        """
        Compute confidence bands for the regression line.

        Returns the half interval width `delta_ci` for each point.
        The confidence band is given by:

            ci = prediction ± delta_ci

        The confidence band should be interpreted as the band in which the
        true curve lie, with probability alpha.
        As usual, this assumes that the model is correct and errors are normally
        distributed.

        See also https://metricgate.com/blogs/prediction-vs-confidence-bands/

        If the population variance is known (or estimated), we use a normal distribution
        instead of a T-distribution. Population variance might be estimated as the pooled
        variance of multiple samples.
        """
        var = var_population or self.MSE

        X_pred = self._construct_system_matrix(x_pred, self.degree)
        std_pred = np.sqrt(var * np.diag(self.compute_cov_predictions(X_pred)))

        quantile = t.ppf(1 - alpha / 2, self.dof)
        if var_population:
            quantile = norm.ppf(1 - alpha / 2)

        return quantile * std_pred

    def _construct_system_matrix(self, x: list | ndarray, grad: int = 1) -> ndarray:
        """
        Construct the system matrix X for determining polynomial coefficients
        """
        return P.polyvander(x, grad)

    def _construct_weight_matrix(self) -> ndarray:
        """Construct the weight matrix W"""
        return np.diag(self.weights)

    @property
    def ddof(self) -> int:
        """Return "Delta Degrees of Freedom"."""
        return self.degree + 1

    @property
    def mex(self) -> float:
        """
        Return the mean epoch, i.e. "middelepokedatoen"
        """
        return sum(self.x) / self.N

    @property
    def mey(self) -> float:
        """Return the y-value at the mean epoch."""
        return P.polyval(self.mex, self.theta)


def compute_studentized_residuals(normalized_residuals: ndarray, dof: float) -> ndarray:
    """Studentized residuals

    The same as Leave-one-out residuals.

    When leverage=1 we get inf/-inf = nan
    When leverage>1 (due to numerical imprecision) we get nan/nan = nan
    """
    num = dof - normalized_residuals**2
    den = dof - 1
    return normalized_residuals / (np.sqrt(num / den))


def compute_normalized_residuals(
    residuals: ndarray,
    std_residuals: ndarray,
) -> ndarray:
    """Normalized aka standardized residual

    When leverage=1 we get res/0 = inf
    When leverage>1 (due to numerical imprecision) we get res/sqrt(-x)=nan
    This can be seen from the definition of standard deviation of residuals:
        std_residual = sqrt(MSE*(1-leverage)/weight)
    """
    # elementwise divide
    return residuals / std_residuals


def compute_confidence_interval_t_distribution(
    std: ndarray,
    dof: int,
    alpha: float = 0.05,
) -> ndarray:
    """
    Returns the half interval width `delta_ci` of a quantity following a t-distribution
    with `dof` degrees of freedom, standard deviation `std` og significance level `alpha`.

    Confidence intervals are computed by:

        ci = βᵢ ± delta_ci, where delta_ci = critical_value * Std(βᵢ)
    """
    quantile = t.ppf(1 - alpha / 2, dof)
    return quantile * std


def compute_confidence_interval_normal_distribution(
    std: ndarray,
    alpha: float = 0.05,
) -> ndarray:
    """
    Returns the half interval width `delta_ci` of a quantity following a
    normal-distribution with standard deviation `std` og significance level `alpha`.

    Confidence intervals are computed by:

        ci = βᵢ ± delta_ci, where delta_ci = critical_value * Std(βᵢ)
    """
    quantile = norm.ppf(1 - alpha / 2)
    return quantile * std
