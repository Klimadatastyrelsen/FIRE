import matplotlib.pyplot as plt
import numpy as np

from fire.api.statistik import (
    WeightedLeastSquares,
)

__all__ = [
    "visualize_residuals",
    "visualize_matrices",
]

def visualize_matrices(stats: WeightedLeastSquares):
    """
    Simple plot of matrices used in levelling adjustment.
    """
    fig = plt.figure()

    ax1 = plt.subplot(2,2,1)
    ax1.set_title(f"Normal matrix")
    ax1.matshow(stats.normal_matrix)

    ax2 = plt.subplot(2,2,2)
    ax2.set_title(r"Covariance $\theta$")
    # has same structure as inv normal matrix
    ax2.matshow(stats.cov_theta)

    ax3 = plt.subplot(2,2,3)
    ax3.set_title(r"Covariance adjusted observations")
    # has same structure as the hat matrix
    ax3.matshow(stats.cov_yhat)

    ax4 = plt.subplot(2,2,4)
    ax4.set_title(r"Covariance residuals")
    # same structure as negative hat matrix again (unless observations are correlated)
    ax4.matshow(stats.cov_residuals)

    for ax in [ax1,ax2,ax3,ax4]:
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

    # highlight suspicious observations with high leverage
    idx_high_leverage = [i for i, l in enumerate(leverage) if l > 2*stats.M/stats.N or np.isclose(l,1)]

    fig = plt.figure()

    ax = plt.subplot(2,2,1)
    ax.set_title(f"Residuals")
    ax.plot(residuals, 'o')
    ax.plot(idx_high_leverage, residuals[idx_high_leverage], 'ro')

    ax = plt.subplot(2,2,2)
    ax.set_title(f"Leverage")
    ax.plot(leverage, 'o')
    ax.plot(idx_high_leverage, leverage[idx_high_leverage], 'ro')

    # plot lines M/N, 2*M/N, 3*M/N, via grid lines
    ys = [stats.M/stats.N*i for i in range(0,4)] + [1]
    ylabels = ["0", "1M/N", "2M/N", "3M/N", "1"]
    ys, ylabels = zip(
        *[
            (y, lab)
            for y, lab in
            sorted(zip(ys, ylabels), key=lambda x: x[0])
            if (y<1 or np.isclose(y, 1))
        ]
    )

    ax.set_yticks(ys)
    ax.set_yticklabels(ylabels)
    plt.grid(axis = 'y')

    ax = plt.subplot(2,2,3)
    ax.set_title(f"Normalized residuals")
    ax.plot(normalized_residuals, 'o')
    ax.plot(idx_high_leverage, normalized_residuals[idx_high_leverage], 'ro')


    ax = plt.subplot(2,2,4)
    ax.set_title(f"Normalized residuals vs leverage")
    ax.plot(np.abs(normalized_residuals), leverage, 'o')
    ax.plot(np.abs(normalized_residuals[idx_high_leverage]), leverage[idx_high_leverage], 'ro')

    plt.show()
