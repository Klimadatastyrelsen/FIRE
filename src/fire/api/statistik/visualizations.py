import matplotlib.pyplot as plt
import numpy as np

from fire.api.statistik import (
    WeightedLeastSquares,
    Ttest,
)

__all__ = [
    "visualize_residuals",
    "visualize_matrices",
]


def visualize_matrices(stats: WeightedLeastSquares):
    """
    Simple plot of matrices used in levelling adjustment.
    """
    fig = plt.figure(figsize=(10, 7))

    ax1 = plt.subplot(2, 2, 1)
    ax1.set_title(f"Normal matrix")
    ax1.matshow(stats.normal_matrix)

    ax2 = plt.subplot(2, 2, 2)
    ax2.set_title(r"Covariance $\theta$")
    # has same structure as inv normal matrix
    ax2.matshow(stats.cov_theta)

    ax3 = plt.subplot(2, 2, 3)
    ax3.set_title(r"Covariance adjusted observations")
    # has same structure as the hat matrix
    ax3.matshow(stats.cov_yhat)

    ax4 = plt.subplot(2, 2, 4)
    ax4.set_title(r"Covariance residuals")
    # same structure as negative hat matrix again (unless observations are correlated)
    ax4.matshow(stats.cov_residuals)

    for ax in [ax1, ax2, ax3, ax4]:
        ax.axis("off")

    fig.tight_layout()
    plt.show()


def visualize_residuals(stats: WeightedLeastSquares):
    """
    Simple diagnostic plots of residuals

    Can be used to detect errors or highly influential observations
    """

    leverage = stats.leverage
    residuals = stats.residuals
    normalized_residuals = stats.normalized_residuals

    # 1) Plot histograms
    fig = plt.figure(figsize=(20, 7))
    ax = plt.subplot(1, 2, 1)
    ax.set_title("Residual histograms")

    # Use density=True so shapes are comparable despite different units/scales
    common_kwargs = dict(bins="auto", density=True, histtype="stepfilled")

    ax.hist(
        residuals,
        alpha=0.8,
        edgecolor="C0",
        color="C0",
        label="Residuals",
        **common_kwargs,
    )
    ax.hist(
        normalized_residuals,
        alpha=0.4,
        edgecolor="C1",
        color="C1",
        label="Normalized residuals",
        **common_kwargs,
    )

    ax.legend(loc="best")
    ax.set_xlabel("Residuals")
    ax.set_ylabel("Density")

    # 2) Plot residual vs leverage
    alpha = 0.05
    ttest = Ttest(std_est=1, H0=stats.std0_hat, dof=stats.dof - 1, alpha=alpha)
    critical_value = ttest.critical_value

    ax = plt.subplot(1, 2, 2)
    ax.set_title(f"Normalized residuals vs leverage")
    ax.plot(np.abs(normalized_residuals), leverage, "o")

    # highlight suspicious observations with high leverage
    idx_uncontrolled = [i for i, l in enumerate(leverage) if np.isclose(l, 1)]
    if len(idx_uncontrolled) > 0:
        ax.plot(
            np.abs(normalized_residuals[idx_uncontrolled]),
            leverage[idx_uncontrolled],
            "ro",
            label="Uncontrolled observation",
        )

    # Draw regions of high leverage and high residuals (outliers)
    xmin, xmax = ax.get_xlim()

    outlier_color = "C3"
    leverage_color = "C4"
    shade_alpha = 0.3

    if critical_value < xmax:
        ax.axvspan(
            critical_value,
            1e10,
            color=outlier_color,
            alpha=shade_alpha,
            zorder=0,
            label="Outliers",
        )

    if 2 * stats.M / stats.N < 1:
        ax.axhspan(
            2 * stats.M / stats.N,
            1e10,
            color=leverage_color,
            alpha=shade_alpha,
            zorder=0,
            label="High leverage",
        )

    ax.set_xlim([0, xmax + 0.1])
    ax.set_ylim([-0.01, 1.01])
    ax.legend(loc="best", framealpha=1)
    ax.grid()

    ax.set_title(f"Normalized residuals vs leverage")
    ax.set_xlabel("Abs(normalized residual)")
    ax.set_ylabel("Leverage")

    fig.tight_layout()
    plt.show()
