"""Event-based localization CRLB versus total event count.

This is an idealized independent-axis model on (x, t, lambda).  It estimates
the two initial positions (x0_1, x0_2), while treating velocities and spectral
centers as known.  The event model is polarity-resolved:

    rate_plus  = eta * max(d/dt log(I), 0)
    rate_minus = eta * max(-d/dt log(I), 0)

The geometric FIM is computed once for each scenario.  Since eta scales the
whole event-rate shape, N_e = eta * N_bar, where N_e is the expected total
number of events over the complete recording window.  For a recording duration
T_rec, the corresponding recording-averaged event rate is R_e = N_e / T_rec,
in events/second, and

    sigma_x(N_e) = C_x / sqrt(N_e).

This deliberately ignores the physical details of how a real sensor encodes
space, wavelength, and time.  It treats those axes as independent coordinates.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import simpson
from scipy.linalg import eigvalsh


def integrate_3d(values, x, t, wavelength):
    """Integrate an x-by-t-by-lambda array with the actual volume element."""
    values = simpson(values, x=wavelength, axis=2)
    values = simpson(values, x=t, axis=1)
    return simpson(values, x=x, axis=0)


def event_geometry_multiplier(
    dx=10.0,
    velocity_1=100.0,
    velocity_2=100.0,
    lambda_1=500.0,
    lambda_2=500.0,
    sigma_x=150.0,
    sigma_lambda=5.0,
    background=1e-4,
):
    """Return std-dev multipliers C1,C2 for sigma_i=C_i/sqrt(N_e).

    A stationary-object case has no motion-induced events in this model and
    correctly returns infinities when the FIM is singular.
    """
    x = np.linspace(-600.0, 600.0, 151)
    time = np.linspace(0.0, 1.0, 61)
    wavelength = np.linspace(480.0, 530.0, 31)
    xx, tt, ll = np.meshgrid(x, time, wavelength, indexing="ij")

    x1_t = velocity_1 * tt
    x2_t = dx + velocity_2 * tt
    i1 = np.exp(-0.5 * ((xx - x1_t) / sigma_x) ** 2) * np.exp(-0.5 * ((ll - lambda_1) / sigma_lambda) ** 2)
    i2 = np.exp(-0.5 * ((xx - x2_t) / sigma_x) ** 2) * np.exp(-0.5 * ((ll - lambda_2) / sigma_lambda) ** 2)
    total = i1 + i2 + background

    d_i1_dx = i1 * (xx - x1_t) / sigma_x**2
    d_i2_dx = i2 * (xx - x2_t) / sigma_x**2
    d_total_dt = velocity_1 * d_i1_dx + velocity_2 * d_i2_dx
    d2_i1_dxdt = i1 * velocity_1 / sigma_x**2 * (((xx - x1_t) / sigma_x) ** 2 - 1.0)
    d2_i2_dxdt = i2 * velocity_2 / sigma_x**2 * (((xx - x2_t) / sigma_x) ** 2 - 1.0)

    log_rate_derivative = d_total_dt / total
    d_log_dx1 = (d2_i1_dxdt * total - d_total_dt * d_i1_dx) / total**2
    d_log_dx2 = (d2_i2_dxdt * total - d_total_dt * d_i2_dx) / total**2

    positive = np.maximum(log_rate_derivative, 0.0)
    negative = np.maximum(-log_rate_derivative, 0.0)
    d_positive = [
        (log_rate_derivative > 0.0) * d_log_dx1,
        (log_rate_derivative > 0.0) * d_log_dx2,
    ]
    d_negative = [
        (log_rate_derivative < 0.0) * (-d_log_dx1),
        (log_rate_derivative < 0.0) * (-d_log_dx2),
    ]

    axes = (x, time, wavelength)
    n_bar = integrate_3d(positive + negative, *axes)
    fim_bar = np.zeros((2, 2))
    for rate, derivatives in ((positive, d_positive), (negative, d_negative)):
        # At rate=0 the corresponding derivative is also zero. The mask keeps
        # the numerical expression finite without inventing information.
        safe_rate = np.maximum(rate, 1e-12)
        fim_bar[0, 0] += integrate_3d(derivatives[0] ** 2 / safe_rate, *axes)
        fim_bar[0, 1] += integrate_3d(derivatives[0] * derivatives[1] / safe_rate, *axes)
        fim_bar[1, 1] += integrate_3d(derivatives[1] ** 2 / safe_rate, *axes)
    fim_bar[1, 0] = fim_bar[0, 1]

    eigenvalues = eigvalsh(fim_bar)
    if n_bar <= 1e-12 or eigenvalues[0] <= 1e-12:
        return np.inf, np.inf, n_bar, eigenvalues

    covariance_multiplier = n_bar * np.linalg.inv(fim_bar)
    return np.sqrt(covariance_multiplier[0, 0]), np.sqrt(covariance_multiplier[1, 1]), n_bar, eigenvalues


def main():
    recording_duration = 1.0  # seconds; the integration grid below spans this interval
    event_rates_per_second = np.logspace(2, 6, 200)
    same_motion = event_geometry_multiplier(
        velocity_1=100.0,
        velocity_2=100.0,
        lambda_1=500.0,
        lambda_2=500.0,
    )
    different_motion_and_spectrum = event_geometry_multiplier(
        velocity_1=100.0,
        velocity_2=200.0,
        lambda_1=500.0,
        lambda_2=510.0,
    )

    if not np.isfinite(same_motion[:2]).all() or not np.isfinite(different_motion_and_spectrum[:2]).all():
        raise RuntimeError("A selected scenario has a singular event FIM; choose nonzero motion and informative spectral separation.")

    expected_events = event_rates_per_second * recording_duration
    sigma_same_1 = same_motion[0] / np.sqrt(expected_events)
    sigma_diff_1 = different_motion_and_spectrum[0] / np.sqrt(expected_events)

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(event_rates_per_second, sigma_same_1, "r--", linewidth=2.5, label="same motion, same spectrum")
    ax.plot(event_rates_per_second, sigma_diff_1, "g-", linewidth=2.5, label="different motion and spectrum")
    ax.set_title("Event-based localization CRLB versus recording event rate")
    ax.set_xlabel("Recording-averaged event rate $R_e$ [events/s]")
    ax.set_ylabel("Localization standard-deviation bound $\u03c3_{x_{0,1}}$ [nm]")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(True, which="both", linestyle="--", alpha=0.6)
    ax.legend()
    fig.tight_layout()
    plt.show()

    print(f"same-motion multiplier C1 = {same_motion[0]:.6g} nm*sqrt(event)")
    print(f"different-motion/spectrum multiplier C1 = {different_motion_and_spectrum[0]:.6g} nm*sqrt(event)")
    print(f"same-motion minimum FIM eigenvalue = {same_motion[3][0]:.6g}")
    print(f"different-motion/spectrum minimum FIM eigenvalue = {different_motion_and_spectrum[3][0]:.6g}")


if __name__ == "__main__":
    main()
