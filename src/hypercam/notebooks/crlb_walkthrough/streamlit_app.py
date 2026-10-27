"""Interactive course: Fisher information and CRLBs for localization."""

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from scipy.integrate import simpson
from scipy.linalg import eigvalsh

st.set_page_config(page_title="A course in localization CRLBs", page_icon=":material/school:", layout="wide")

LESSONS = [
    "Course overview", "1 · Observations and parameters", "2 · Likelihood and score",
    "3 · Fisher information", "4 · Vector parameters and Jacobians", "5 · The scalar CRLB",
    "6 · Poisson observations", "7 · The Poisson-process FIM", "8 · Gaussian PSF localization",
    "9 · Moving emitters", "10 · Adding wavelength", "11 · Event cameras",
    "12 · Two-object identifiability", "13 · Final proof audit",
]


def initialize_state():
    st.session_state.setdefault("lesson", 0)
    st.session_state.setdefault("checks", {})


def lesson_header(number, title, objectives):
    st.progress((number + 1) / len(LESSONS), text=f"Lesson {number + 1} of {len(LESSONS)}")
    st.title(title)
    with st.container(border=True):
        st.markdown("**By the end of this lesson, you should be able to:**")
        for objective in objectives:
            st.markdown(f"- {objective}")


def variable_table(rows):
    st.dataframe(pd.DataFrame(rows, columns=["Symbol", "Meaning", "Typical units"]), hide_index=True, width="stretch")


def labeled_line_chart(frame, x_title, y_title):
    """Render a multi-series line chart with explicit, visible axis labels."""
    plot_data = frame.reset_index().rename(columns={frame.index.name or "index": "x_value"})
    series = [column for column in plot_data.columns if column != "x_value"]
    long_data = plot_data.melt("x_value", value_vars=series, var_name="series", value_name="y_value")
    chart = alt.Chart(long_data).mark_line().encode(
        x=alt.X("x_value:Q", title=x_title),
        y=alt.Y("y_value:Q", title=y_title),
        color=alt.Color("series:N", title=None),
        tooltip=[alt.Tooltip("x_value:Q", title=x_title), alt.Tooltip("y_value:Q", title=y_title), alt.Tooltip("series:N", title="quantity")],
    ).properties(height=360)
    st.altair_chart(chart, width="stretch")


def checkpoint(key, question, options, answer, explanation):
    st.markdown("#### Check your understanding")
    choice = st.radio(question, options, key=f"question_{key}")
    if st.button("Check answer", key=f"check_{key}", icon=":material/check:"):
        st.session_state.checks[key] = choice == answer
    if key in st.session_state.checks:
        if st.session_state.checks[key]:
            st.success(f"Correct. {explanation}")
        else:
            st.warning(f"Not quite. The best answer is **{answer}**. {explanation}")


def navigation():
    st.sidebar.divider()
    st.sidebar.subheader("Course lessons")
    selected = st.sidebar.selectbox("Jump to a lesson", range(len(LESSONS)), index=st.session_state.lesson, format_func=lambda i: LESSONS[i])
    if selected != st.session_state.lesson:
        st.session_state.lesson = selected
        st.rerun()
    left, right = st.columns(2)
    with left:
        if st.session_state.lesson > 0 and st.button("Previous lesson", icon=":material/arrow_back:"):
            st.session_state.lesson -= 1
            st.rerun()
    with right:
        if st.session_state.lesson < len(LESSONS) - 1 and st.button("Next lesson", type="primary", icon=":material/arrow_forward:"):
            st.session_state.lesson += 1
            st.rerun()


def gaussian_2d(x, y, x0, y0, sigma):
    return np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2 * sigma**2))


def spectral_gaussian(wavelength, center, width):
    return np.exp(-((wavelength - center) ** 2) / (2 * width**2)) / (np.sqrt(2 * np.pi) * width)


def emitter_position(t, state):
    x0, y0, vx, vy, ax, ay, _, _ = state
    return x0 + vx * t + 0.5 * ax * t**2, y0 + vy * t + 0.5 * ay * t**2


def photon_rate(x, y, wavelength, t, state, sigma, spectral_width, dispersion=0.0, reference_wavelength=550.0):
    _, _, _, _, _, _, amp, center = state
    xc, yc = emitter_position(t, state)
    # A simple diffractive-optic model: wavelength shifts the PSF in x.
    encoded_xc = xc + dispersion * (center - reference_wavelength)
    return amp * gaussian_2d(x, y, encoded_xc, yc, sigma) * spectral_gaussian(wavelength, center, spectral_width)


def total_photon_rate(x, y, wavelength, t, state1, state2, background, sigma, spectral_width, dispersion=0.0):
    return photon_rate(x, y, wavelength, t, state1, sigma, spectral_width, dispersion) + photon_rate(x, y, wavelength, t, state2, sigma, spectral_width, dispersion) + background


def intensity_time_derivative(x, y, t, state1, state2, sigma, spectral_width, wavelength, dispersion=0.0):
    out = 0.0
    for state in (state1, state2):
        _, _, vx, vy, ax, ay, _, _ = state
        xc, yc = emitter_position(t, state)
        _, _, _, _, _, _, _, center = state
        xc += dispersion * (center - 550.0)
        im = photon_rate(x, y, wavelength, t, state, sigma, spectral_width, dispersion)
        out += im * ((x - xc) * (vx + ax * t) + (y - yc) * (vy + ay * t)) / sigma**2
    return out


def event_rates(x, y, wavelength, t, state1, state2, background, sigma, spectral_width, eta, gamma, dispersion=0.0):
    intensity = total_photon_rate(x, y, wavelength, t, state1, state2, background, sigma, spectral_width, dispersion)
    derivative = intensity_time_derivative(x, y, t, state1, state2, sigma, spectral_width, wavelength, dispersion)
    g = derivative / np.maximum(intensity, 1e-12)
    return gamma + eta * np.maximum(g, 0), gamma + eta * np.maximum(-g, 0)


def integrate(values, axes):
    result = values
    for axis_values in reversed(axes):
        result = simpson(result, x=axis_values, axis=result.ndim - 1)
    return result


def mixed_gaussian_derivative(x, y, t, state, sigma, spectral_width=None, wavelength=None, dispersion=0.0, reference_wavelength=550.0):
    _, _, vx, vy, ax, ay, amp, center = state
    xc, yc = emitter_position(t, state)
    xc += dispersion * (center - reference_wavelength)
    dx, dy = x - xc, y - yc
    intensity = amp * gaussian_2d(x, y, xc, yc, sigma)
    if spectral_width is not None and wavelength is not None:
        intensity *= spectral_gaussian(wavelength, center, spectral_width)
    vxt, vyt = vx + ax * t, vy + ay * t
    return intensity * (vxt * (dx**2 / sigma**4 - 1 / sigma**2) + vyt * dx * dy / sigma**4)


def finite_difference(function, vector, index, step=1e-5):
    plus, minus = np.array(vector, dtype=float), np.array(vector, dtype=float)
    plus[index] += step
    minus[index] -= step
    return (function(plus) - function(minus)) / (2 * step)


@st.cache_data(show_spinner=False, max_entries=128)
def position_crlb(spatial_separation, spectral_separation, speed_2, use_events, dispersion):
    """Numerically integrate the 2x2 position FIM and return variance bounds."""
    sigma, spectral_width = 1.0, 10.0
    state1 = (-spatial_separation / 2, 0.0, 0.7, 0.0, 0.0, 0.0, 5.0, 550.0 - spectral_separation * spectral_width / 2)
    state2 = (spatial_separation / 2, 0.0, speed_2, 0.0, 0.0, 0.0, 5.0, 550.0 + spectral_separation * spectral_width / 2)
    xs, ys, wavelengths, ts = np.linspace(-4, 4, 41), np.linspace(-3, 3, 31), np.linspace(500, 600, 21), np.linspace(0, 1, 11)
    xx, yy, ll, tt = np.meshgrid(xs, ys, wavelengths, ts, indexing="ij")

    def rates(a, b):
        if use_events:
            return event_rates(xx, yy, ll, tt, a, b, 0.5, sigma, spectral_width, 8.0, 0.2, dispersion)
        return (total_photon_rate(xx, yy, ll, tt, a, b, 0.5, sigma, spectral_width, dispersion),)

    h = 1e-4
    derivatives = []
    for emitter in (0, 1):
        base = np.array(state1 if emitter == 0 else state2)
        plus_state, minus_state = base.copy(), base.copy()
        plus_state[0] += h
        minus_state[0] -= h
        plus_rates = rates(plus_state, state2) if emitter == 0 else rates(state1, plus_state)
        minus_rates = rates(minus_state, state2) if emitter == 0 else rates(state1, minus_state)
        derivatives.append([(p - m) / (2 * h) for p, m in zip(plus_rates, minus_rates)])
    rates_at_truth = rates(state1, state2)
    fim = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            for rate, di, dj in zip(rates_at_truth, derivatives[i], derivatives[j]):
                fim[i, j] += integrate(di * dj / np.maximum(rate, 1e-9), (xs, ys, wavelengths, ts))
    fim = (fim + fim.T) / 2
    eigenvalues = eigvalsh(fim)
    if eigenvalues[0] <= 1e-8:
        return np.nan, np.nan, np.nan, eigenvalues[0]
    covariance = np.linalg.inv(fim)
    correlation = covariance[0, 1] / np.sqrt(covariance[0, 0] * covariance[1, 1])
    return covariance[0, 0], covariance[1, 1], correlation, eigenvalues[0]


@st.cache_data(show_spinner=False, max_entries=128)
def four_parameter_poisson_crlb(n_photons, sigma_xy, sigma_lambda, sigma_time, eta, gamma, event_model):
    """CRLB for theta=(x0,y0,lambda0,t0) on independent 4D axes."""
    x = np.linspace(-4 * sigma_xy, 4 * sigma_xy, 25)
    y = np.linspace(-4 * sigma_xy, 4 * sigma_xy, 25)
    wavelength = np.linspace(-4 * sigma_lambda, 4 * sigma_lambda, 21)
    time = np.linspace(-4 * sigma_time, 4 * sigma_time, 21)
    xx, yy, ll, tt = np.meshgrid(x, y, wavelength, time, indexing="ij")
    normal_x = np.exp(-xx**2 / (2 * sigma_xy**2)) / (np.sqrt(2 * np.pi) * sigma_xy)
    normal_y = np.exp(-yy**2 / (2 * sigma_xy**2)) / (np.sqrt(2 * np.pi) * sigma_xy)
    normal_lambda = np.exp(-ll**2 / (2 * sigma_lambda**2)) / (np.sqrt(2 * np.pi) * sigma_lambda)
    normal_time = np.exp(-tt**2 / (2 * sigma_time**2)) / (np.sqrt(2 * np.pi) * sigma_time)
    density = normal_x * normal_y * normal_lambda * normal_time
    derivatives = [
        density * xx / sigma_xy**2,
        density * yy / sigma_xy**2,
        density * ll / sigma_lambda**2,
        density * tt / sigma_time**2,
    ]
    if event_model:
        # g = ∂t log(p) = -t/sigma_time². Split positive/negative contrast
        # into two Poisson channels to avoid differentiating abs(g) at zero.
        contrast = -tt / sigma_time**2
        positive = np.maximum(contrast, 0)
        negative = np.maximum(-contrast, 0)
        d_contrast = [np.zeros_like(tt), np.zeros_like(tt), np.zeros_like(tt), np.full_like(tt, 1 / sigma_time**2)]
        rates = (gamma + eta * n_photons * density * positive, gamma + eta * n_photons * density * negative)
        rate_derivatives = []
        for sign_rate, d_sign_rate in ((positive, d_contrast), (negative, [-d for d in d_contrast])):
            rate_derivatives.append([eta * n_photons * (derivative * sign_rate + density * (sign_rate > 0) * d_sign) for derivative, d_sign in zip(derivatives, d_sign_rate)])
    else:
        rates = (n_photons * density,)
        rate_derivatives = ([n_photons * derivative for derivative in derivatives],)
    fim = np.zeros((4, 4))
    for rate, derivative_set in zip(rates, rate_derivatives):
        for i in range(4):
            for j in range(4):
                fim[i, j] += integrate(derivative_set[i] * derivative_set[j] / np.maximum(rate, 1e-12), (x, y, wavelength, time))
    fim = (fim + fim.T) / 2
    eigenvalues = eigvalsh(fim)
    if eigenvalues[0] <= 1e-10:
        return np.full(4, np.inf), eigenvalues[0]
    return np.diag(np.linalg.inv(fim)), eigenvalues[0]


@st.cache_data(show_spinner=False, max_entries=32)
def independent_axis_event_multiplier(dx, velocity_1, velocity_2, lambda_1, lambda_2):
    """Geometry multiplier for a polarity-resolved event FIM on x,t,lambda axes."""
    sigma_x, sigma_lambda, background = 150.0, 5.0, 1e-4
    x = np.linspace(-600, 600, 121)
    time = np.linspace(0, 1, 41)
    wavelength = np.linspace(480, 530, 31)
    xx, tt, ll = np.meshgrid(x, time, wavelength, indexing="ij")
    x1 = velocity_1 * tt
    x2 = dx + velocity_2 * tt
    i1 = np.exp(-0.5 * (xx - x1)**2 / sigma_x**2) * np.exp(-0.5 * (ll - lambda_1)**2 / sigma_lambda**2)
    i2 = np.exp(-0.5 * (xx - x2)**2 / sigma_x**2) * np.exp(-0.5 * (ll - lambda_2)**2 / sigma_lambda**2)
    total = i1 + i2 + background
    d_i1_dx = i1 * (xx - x1) / sigma_x**2
    d_i2_dx = i2 * (xx - x2) / sigma_x**2
    d_total_dt = velocity_1 * d_i1_dx + velocity_2 * d_i2_dx
    d2_i1 = i1 * velocity_1 / sigma_x**2 * (((xx - x1) / sigma_x)**2 - 1)
    d2_i2 = i2 * velocity_2 / sigma_x**2 * (((xx - x2) / sigma_x)**2 - 1)
    log_rate_derivative = d_total_dt / total
    d_log_dx1 = (d2_i1 * total - d_total_dt * d_i1_dx) / total**2
    d_log_dx2 = (d2_i2 * total - d_total_dt * d_i2_dx) / total**2
    positive = np.maximum(log_rate_derivative, 0)
    negative = np.maximum(-log_rate_derivative, 0)
    d_positive_1 = (log_rate_derivative > 0) * d_log_dx1
    d_positive_2 = (log_rate_derivative > 0) * d_log_dx2
    d_negative_1 = (log_rate_derivative < 0) * (-d_log_dx1)
    d_negative_2 = (log_rate_derivative < 0) * (-d_log_dx2)
    axes = (x, time, wavelength)
    n_bar = integrate(positive + negative, axes)
    fim_bar = np.zeros((2, 2))
    for rate, d1, d2 in ((positive, d_positive_1, d_positive_2), (negative, d_negative_1, d_negative_2)):
        safe_rate = np.maximum(rate, 1e-12)
        fim_bar[0, 0] += integrate(d1 * d1 / safe_rate, axes)
        fim_bar[0, 1] += integrate(d1 * d2 / safe_rate, axes)
        fim_bar[1, 1] += integrate(d2 * d2 / safe_rate, axes)
    fim_bar[1, 0] = fim_bar[0, 1]
    eigenvalues = eigvalsh(fim_bar)
    if n_bar <= 1e-12 or eigenvalues[0] <= 1e-12:
        return np.inf, np.inf, n_bar, eigenvalues[0]
    covariance_multiplier = n_bar * np.linalg.inv(fim_bar)
    return np.sqrt(covariance_multiplier[0, 0]), np.sqrt(covariance_multiplier[1, 1]), n_bar, eigenvalues[0]


def page_overview():
    lesson_header(0, "A course in localization CRLBs", ["Understand observations and parameters.", "Build Fisher information from likelihoods and derive the CRLB.", "Apply the ideas to PSFs, motion, wavelength, and event streams.", "Use eigenvalues to diagnose two-object identifiability."])
    st.markdown("""
This is a guided course rather than a formula catalogue. We repeatedly use the same pattern:

1. **Define the random observation.** What does the sensor actually record?
2. **Define the parameters.** Which unknown physical quantities are we estimating?
3. **Write the likelihood.** How probable is the data for each parameter value?
4. **Measure sensitivity.** Fisher information quantifies local likelihood change.
5. **Compute the lower bound.** The CRLB limits covariance of unbiased estimators.

The final model concerns two moving emitters. Their light is blurred by a point-spread function,
may be separated spectrally, and may be recorded as asynchronous events.
""")
    with st.container(border=True):
        st.markdown("### Prerequisites")
        st.markdown("Be comfortable with derivatives, integrals, expectation, variance, and the Gaussian distribution. The information-theory vocabulary is introduced here.")
    checkpoint("overview", "What does the CRLB provide?", ["A guaranteed exact estimator", "A lower bound on covariance", "A way to create new optical resolution"], "A lower bound on covariance", "It is a local statistical bound for a specified model.")


def page_observations():
    lesson_header(1, "Observations and parameters", ["Separate what is measured from what is unknown.", "Read the state vector used by the localization model.", "Recognize nuisance parameters and observability limits."])
    st.markdown(r"""
An **observation** is random data produced by the sensor. A **parameter** is an unknown quantity that controls the distribution of that data. We write all unknowns as $\Theta$.

For one moving emitter, use

$$\theta_k=(x_{0,k},y_{0,k},v_{x,k},v_{y,k},a_{x,k},a_{y,k},\Phi_k,\lambda_k).$$
""")
    variable_table([("x₀, y₀", "Initial image-plane position", "pixels or length"), ("vₓ, vᵧ", "Velocity components", "length / time"), ("aₓ, aᵧ", "Acceleration components", "length / time²"), ("Φ", "Brightness or photon-rate scale", "photons / time"), ("λ", "Spectral center, if measured/encoded", "wavelength"), ("Θ", "All unknown parameters", "mixed units")])
    st.markdown(r"A parameter that does not affect the distribution of the observed data is not identifiable. Writing $\lambda$ in a vector does not make wavelength available to an event sensor.")
    checkpoint("observations", "In a Poisson event-stream model, which is an observation?", ["The unknown velocity", "An event time and pixel", "The assumed PSF width"], "An event time and pixel", "The event record is data; velocity and PSF width are parameters or known inputs.")


def page_likelihood():
    lesson_header(2, "Likelihood and score", ["Interpret a likelihood as a function of parameters.", "Differentiate a log-likelihood to obtain the score.", "Understand why local sensitivity matters."])
    st.markdown(r"""
Let $Y$ be one observation with density $p(y;\theta)$. The **likelihood** is the same function viewed as a function of $\theta$ after $y$ is observed:

$$L(\theta;y)=p(y;\theta),\qquad \ell(\theta;y)=\log L(\theta;y).$$

The **score** is $U(\theta)=\partial\ell(\theta;Y)/\partial\theta$. Large score magnitude means the observed data are locally sensitive to $\theta$.
""")
    theta = st.slider("Candidate mean θ", -2.0, 2.0, 0.5)
    observation = st.slider("Observed value y", -3.0, 3.0, 1.0)
    noise = st.slider("Known Gaussian noise σ", 0.2, 2.0, 1.0)
    st.latex(r"U(\theta)=\frac{y-\theta}{\sigma^2}")
    st.metric("Score at the selected observation", f"{(observation-theta)/noise**2:.4f}")
    checkpoint("likelihood", "Why use the log-likelihood?", ["It turns products into sums", "It removes all noise", "It makes every estimator unbiased"], "It turns products into sums", "Independent-data likelihoods multiply; logarithms simplify differentiation.")


def page_information():
    lesson_header(3, "Fisher information", ["Derive information for a Gaussian mean.", "Connect information to expected score curvature.", "Interpret information as an inverse uncertainty scale."])
    st.markdown(r"""
For $Y\sim\mathcal N(\theta,\sigma^2)$,

$$\ell=-\frac{(y-\theta)^2}{2\sigma^2}+C,\qquad U=\frac{y-\theta}{\sigma^2}.$$

The Fisher information is the expected squared score:

$$\mathcal I(\theta)=\mathbb E[U^2]=\frac1{\sigma^2}.$$

For $N$ independent observations, information adds: $\mathcal I_N=N/\sigma^2$.
""")
    n = st.slider("Number of independent measurements N", 1, 100, 20)
    sigma = st.slider("Noise standard deviation σ", 0.1, 3.0, 1.0)
    st.metric("Fisher information", f"{n/sigma**2:.4f}")
    checkpoint("information", "If σ doubles while N stays fixed, information becomes…", ["Twice as large", "Half as large", "One quarter as large"], "One quarter as large", r"Information scales as $1/\sigma^2$.")


def page_vector_parameters():
    lesson_header(4, "Vector parameters, Jacobians, and the matrix CRLB", ["Construct a FIM for several unknowns at once.", "Use the Jacobian of the observation model correctly.", "Account for parameter correlations and nuisance parameters."])
    st.markdown(r"""
Localization is not usually a one-number problem. For one emitter we may estimate

$$\boldsymbol\theta=\begin{bmatrix}x_0 & y_0 & v_x & v_y & \lambda\end{bmatrix}^{\mathsf T}.$$

The CRLB becomes a matrix inequality:

$$\operatorname{Cov}(\hat{\boldsymbol\theta})\succeq\mathcal I(\boldsymbol\theta)^{-1}.$$

Here $A\succeq B$ means that $A-B$ is positive semidefinite. The diagonal entries
bound individual variances; off-diagonal entries describe coupled uncertainty.

### Where the Jacobian enters

For a Gaussian observation model $\mathbf Y\sim\mathcal N(\boldsymbol\mu(\boldsymbol\theta),\Sigma)$,
the Jacobian is

$$J_{ri}=\frac{\partial\mu_r}{\partial\theta_i}.$$

The FIM is

$$\boxed{\mathcal I_\theta=J^{\mathsf T}\Sigma^{-1}J.}$$

For a Poisson rate model, the same idea appears pointwise:

$$[\mathcal I_\theta]_{ij}=\int\frac{1}{\Lambda(u;\theta)}
\frac{\partial\Lambda}{\partial\theta_i}\frac{\partial\Lambda}{\partial\theta_j}\,du.$$

So the relevant Jacobian is the Jacobian of the **mean or rate model**, not a
Jacobian of the FIM itself. The FIM is built from that Jacobian and then inverted.
""")
    variable_table([
        ("θ", "Vector of unknown parameters", "mixed units"),
        ("μ(θ)", "Expected observation vector", "same units as data"),
        ("J", "Jacobian ∂μ/∂θ", "data units / parameter units"),
        ("Σ", "Observation-noise covariance", "data units²"),
        ("Iθ", "Fisher information matrix", "inverse parameter units²"),
    ])
    st.subheader("NumPy matrix example")
    angle = st.slider("Noise correlation angle", -0.9, 0.9, 0.3, key="vector_corr")
    covariance = np.array([[1.0, angle, 0.0], [angle, 1.0, 0.0], [0.0, 0.0, 1.0]])
    jacobian = np.array([[1.0, 0.5], [0.2, 1.2], [-0.4, 0.8]])
    fim = jacobian.T @ np.linalg.inv(covariance) @ jacobian
    crlb = np.linalg.inv(fim)
    st.markdown("For this example, the mean model has three outputs and two unknown parameters. The rows of $J$ are the sensitivities of each output.")
    c1, c2 = st.columns(2)
    with c1:
        st.dataframe(pd.DataFrame(jacobian, index=["μ₁", "μ₂", "μ₃"], columns=["θ₁", "θ₂"]).round(4), width="stretch")
        st.caption("Jacobian J")
    with c2:
        st.dataframe(pd.DataFrame(fim, index=["θ₁", "θ₂"], columns=["θ₁", "θ₂"]).round(4), width="stretch")
        st.caption("FIM JᵀΣ⁻¹J")
    st.success(f"✓ NumPy verified the matrix CRLB. SD bounds: θ₁ ≥ {np.sqrt(crlb[0,0]):.4f}, θ₂ ≥ {np.sqrt(crlb[1,1]):.4f}; covariance = {crlb[0,1]:.4f}.")
    st.subheader("General four-parameter CRLB versus photon count")
    st.markdown(r"""
Now consider a single-emitter estimator

$$\boldsymbol\theta=(x_0,y_0,\lambda_0,t_0).$$

For this **general idealized case**, treat $(x,y,\lambda,t)$ as four independent
axes and use a separable Poisson intensity

$$\Lambda(x,y,\lambda,t;\boldsymbol\theta)=N\,p_x(x-x_0)p_y(y-y_0)p_\lambda(\lambda-\lambda_0)p_t(t-t_0),$$

where $\boldsymbol\theta=(x_0,y_0,\lambda_0,t_0)$. This intentionally ignores
how a real instrument encodes these axes. It is a clean information-theory model.

For the logarithmic-contrast detector, define

$$g=\partial_t\log\Lambda=-\frac{t-t_0}{\sigma_t^2},\qquad
\Lambda_\pm=\gamma+\eta Np\max(\pm g,0).$$

The two polarity channels are Poisson processes, and their FIMs add. For independent photons, information adds:

$$\mathcal I_N=N\mathcal I_1,\qquad
\operatorname{CRLB}_N=\mathcal I_N^{-1}=\frac1N\mathcal I_1^{-1}.$$

Therefore every finite variance bound scales as $1/N$, while its standard
deviation scales as $1/\sqrt N$.
""")
    sigma_xy = st.slider("Spatial axis width σxy", 0.2, 2.0, 1.0, key="four_sigma_xy")
    sigma_lambda = st.slider("Wavelength-axis width σλ", 1.0, 30.0, 10.0, key="four_sigma_lambda")
    sigma_time = st.slider("Time-axis width σt", 0.01, 1.0, 0.2, key="four_sigma_time")
    eta = st.slider("Log-contrast event scale η", 0.1, 20.0, 4.0, key="four_eta")
    gamma = st.slider("Poisson event background γ", 0.001, 1.0, 0.02, key="four_gamma")
    event_model = st.checkbox("Use logarithmic-contrast event model", value=True, key="four_event_model")
    n_values = np.unique(np.round(np.logspace(0, 5, 60)).astype(int))
    rows = []
    for n_photons in n_values:
        bounds, minimum_eigenvalue = four_parameter_poisson_crlb(n_photons, sigma_xy, sigma_lambda, sigma_time, eta, gamma, event_model)
        rows.append({"N photons": n_photons, "CRLB var(x₀)": bounds[0], "CRLB var(y₀)": bounds[1], "CRLB var(λ₀)": bounds[2], "CRLB var(t₀)": bounds[3]})
    four_frame = pd.DataFrame(rows).set_index("N photons")
    labeled_line_chart(four_frame, "number of photons, N", "CRLB variance")
    if event_model:
        st.success("✓ The polarity-resolved Poisson/log-contrast FIM is full rank for this separable model. The plotted finite bounds should fall approximately as 1/N.")
    else:
        st.success("✓ The ordinary separable Poisson photon-rate FIM is full rank. This is the independent-axis idealization, not the diffractive-optic model.")
    st.markdown(r"""
### Reparameterization

If $\boldsymbol\phi=g(\boldsymbol\theta)$ has Jacobian
$G=\partial\boldsymbol\phi/\partial\boldsymbol\theta$, then the transformed
CRLB is

$$\operatorname{Cov}(\hat{\boldsymbol\phi})\succeq
G\mathcal I_\theta^{-1}G^{\mathsf T}.$$

This is the place where a parameter-transformation Jacobian relates a known CRLB
to a new parameterization.

### Nuisance parameters

If $\boldsymbol\theta$ is the parameter of interest and $\boldsymbol\nu$ is a
nuisance vector, partition the FIM as

$$\mathcal I=\begin{bmatrix}A&B\\B^{\mathsf T}&C\end{bmatrix}.$$

When $\boldsymbol\nu$ is unknown, the effective information for $\boldsymbol\theta$
is the Schur complement $A-BC^{-1}B^{\mathsf T}$, not simply $A$. Unknown flux,
background, PSF width, velocity, or wavelength can therefore increase position
uncertainty through the off-diagonal blocks.
""")
    checkpoint("vector_parameters", "Which Jacobian is used to form JᵀΣ⁻¹J?", ["The Jacobian of the FIM", "The Jacobian of the mean observation model", "The Jacobian of the estimator"], "The Jacobian of the mean observation model", "The model Jacobian contains parameter sensitivities. The FIM is then formed from it and inverted to obtain the matrix CRLB.")


def page_scalar_crlb():
    lesson_header(5, "The scalar Cramér–Rao lower bound", ["State the scalar CRLB.", "Understand unbiasedness and regularity.", "Verify the Gaussian-mean bound numerically."])
    st.markdown(r"""
Under standard regularity conditions, an unbiased estimator satisfies

$$\operatorname{var}(\hat\theta)\geq\frac1{\mathcal I(\theta)}.$$

For the Gaussian example,

$$\boxed{\operatorname{var}(\hat\theta)\geq\frac{\sigma^2}{N}}.$$

This is a lower bound, not automatically the variance of every estimator. The sample mean attains it in this simple Gaussian model.
""")
    n = st.slider("N", 1, 100, 20, key="scalar_n")
    sigma = st.slider("σ", 0.1, 3.0, 1.0, key="scalar_sigma")
    st.success(f"✓ CRLB variance = σ²/N = {sigma**2/n:.6f}; standard deviation = {sigma/np.sqrt(n):.6f}")
    checkpoint("crlb", "What happens to the CRLB when more independent photons are collected?", ["It usually decreases", "It must increase", "It is unchanged"], "It usually decreases", "More independent observations add information, so the inverse-information bound gets smaller.")


def page_poisson():
    lesson_header(6, "Poisson observations", ["Explain why photon counts are often Poisson.", "Understand rate, expected count, and background.", "Write a simple photon-count likelihood."])
    st.markdown(r"""
For an average rate $\Lambda$, the number of arrivals over an interval is often modeled as

$$N\sim\operatorname{Poisson}(\mu),\qquad p(N=n)=\frac{e^{-\mu}\mu^n}{n!}.$$

Here $\mu=\Lambda T$ is the expected count. Spatially varying background gives

$$\Lambda(u;\Theta)=\Lambda_1(u;\theta_1)+\Lambda_2(u;\theta_2)+\gamma.$$
""")
    rate = st.slider("Expected rate Λ", 0.1, 10.0, 2.0)
    duration = st.slider("Observation time T", 0.1, 10.0, 3.0)
    st.metric("Expected count μ = ΛT", f"{rate*duration:.3f}")
    st.markdown(r"The Poisson variance equals its mean: $\operatorname{var}(N)=\mu$. This is why inverse rate appears in the Poisson FIM.")
    checkpoint("poisson", "For a Poisson count, what equals the variance?", ["The mean", "The square of the mean", "Always one"], "The mean", "The Poisson distribution has mean and variance both equal to μ.")


def page_ppp_fim():
    lesson_header(7, "The Poisson-process FIM", ["Write the point-process likelihood.", "Differentiate it to obtain the FIM.", "Verify the formula by numerical quadrature."])
    st.markdown(r"""
For event locations $u_1,\ldots,u_N$ from an inhomogeneous Poisson process,

$$\ell(\Theta)=\sum_{n=1}^N\log\Lambda(u_n;\Theta)-\int_{\mathcal D}\Lambda(u;\Theta)\,du.$$

The expected negative Hessian gives

$$\boxed{\mathcal I_{ij}(\Theta)=\int_{\mathcal D}\frac1{\Lambda(u;\Theta)}\frac{\partial\Lambda}{\partial\Theta_i}\frac{\partial\Lambda}{\partial\Theta_j}\,du.}$$

This is “sensitivity squared divided by rate,” integrated over coordinates the data actually contain.
""")
    rate = st.slider("Constant rate θ", 0.2, 10.0, 2.0, key="ppp_rate")
    length = st.slider("Domain length T", 0.5, 10.0, 4.0, key="ppp_length")
    grid = np.linspace(0, length, 1001)
    numerical = simpson(np.ones_like(grid) / rate, x=grid)
    analytic = length / rate
    st.success(f"✓ SciPy quadrature = {numerical:.8f}; analytic T/θ = {analytic:.8f}; error = {abs(numerical-analytic):.2e}")
    checkpoint("ppp_fim", "What belongs in the FIM denominator?", ["The rate Λ", "The derivative ∂Λ/∂θ", "The domain size only"], "The rate Λ", "For Poisson data, local sensitivity is weighted by inverse event rate.")


def page_gaussian():
    lesson_header(8, "Gaussian PSF localization", ["Define a point-spread function.", "Differentiate a Gaussian with respect to position.", "Verify the derivative numerically."])
    st.markdown(r"""
Optics blur a point source. A useful local model is

$$h(x,y;x_0,y_0)=\exp\left[-\frac{(x-x_0)^2+(y-y_0)^2}{2\sigma^2}\right].$$

For $I=\Phi h$ and $d_x=x-x_0$,

$$\frac{\partial I}{\partial x_0}=I\frac{d_x}{\sigma^2}.$$
""")
    sigma = st.slider("PSF width σ", 0.5, 2.0, 1.0, key="psf_sigma")
    x = np.linspace(-4, 4, 301)
    intensity = gaussian_2d(x, 0, 0, 0, sigma)
    derivative = intensity * x / sigma**2
    labeled_line_chart(pd.DataFrame({"PSF h(x)": intensity, "∂h/∂x₀": derivative}, index=x), "image coordinate x", "PSF / positional sensitivity")
    st.markdown("The PSF peaks at its center, while positional sensitivity changes sign and is large on either side.")
    checkpoint("gaussian", "Where is the Gaussian position derivative exactly zero?", ["At the PSF center", "Only at infinity", "Everywhere"], "At the PSF center", "At x=x₀, the factor x−x₀ is zero.")


def page_motion():
    lesson_header(9, "Moving emitters and chain rules", ["Add velocity and acceleration to the state.", "Derive the temporal intensity derivative.", "Verify the mixed spatial-temporal derivative."])
    st.markdown(r"""
Let $x_c(t)=x_0+v_xt+\tfrac12a_xt^2$ and similarly for $y_c$. Then

$$\frac{\partial I}{\partial t}=I\frac{d_xv_x(t)+d_yv_y(t)}{\sigma^2},$$

and

$$\frac{\partial^2 I}{\partial x_0\partial t}=I\left[v_x(t)\left(\frac{d_x^2}{\sigma^4}-\frac1{\sigma^2}\right)+v_y(t)\frac{d_xd_y}{\sigma^4}\right].$$
""")
    sigma = st.slider("σ", 0.5, 2.0, 1.0, key="motion_sigma")
    t = st.slider("t", 0.0, 2.0, 0.5, key="motion_t")
    x = st.slider("Test x", -2.5, 2.5, 0.7, key="motion_x")
    y = st.slider("Test y", -2.5, 2.5, -0.4, key="motion_y")
    state = (0.2, -0.3, 0.8, -0.4, 0.3, 0.2, 4.0, 550.0)
    analytic = mixed_gaussian_derivative(x, y, t, state, sigma, 10.0, 550.0)
    numerical = finite_difference(lambda q: (photon_rate(x, y, 550.0, t + 1e-5, q, sigma, 10.0) - photon_rate(x, y, 550.0, t - 1e-5, q, sigma, 10.0)) / (2e-5), state, 0)
    st.success(f"✓ Analytic mixed derivative = {analytic:.8g}; finite difference = {numerical:.8g}; error = {abs(analytic-numerical):.2e}")
    checkpoint("motion", "Why does velocity appear in ∂I/∂t?", ["The PSF center changes with time", "Velocity changes photon energy", "The CRLB defines velocity"], "The PSF center changes with time", "Motion changes the PSF argument, so the chain rule introduces center velocity.")


def page_spectral():
    lesson_header(10, "Adding wavelength through a diffractive PSF", ["Distinguish latent wavelength from a measured coordinate.", "Put wavelength directly inside the PSF.", "Understand how optical encoding makes λ observable in image data."])
    st.markdown(r"""
In your setup, a diffractive optic makes the PSF wavelength-dependent. A simple
local model is a wavelength-dependent lateral shift:

$$h_D(x,y;x_k,y_k,\lambda_k)=h\left(x-D(\lambda_k-\lambda_{\rm ref}),y;x_k,y_k\right),$$

where $D$ is the optic's dispersion in image distance per wavelength. The detector
does not need a separate wavelength pixel: the image position itself carries
information about $\lambda_k$.

If the source has finite spectral width, its normalized spectrum is

$$S(\lambda;\lambda_k)=\frac1{\sqrt{2\pi}\sigma_\lambda}\exp\left[-\frac{(\lambda-\lambda_k)^2}{2\sigma_\lambda^2}\right].$$

The encoded rate is therefore

$$\Lambda_k(x,y,\lambda,t)=\Phi_kS(\lambda;\lambda_k)h_D(x,y;x_k(t),y_k(t),\lambda_k).$$

For a sensor with no spectral channel, $\lambda$ is integrated out of the rate;
the wavelength information remains because $h_D$ has already moved the photons
to different image locations. A wavelength-resolved detector would retain the
extra $\lambda$ coordinate as well.
""")
    separation = st.slider("Spectral separation Δλ / σλ", 0.0, 5.0, 1.5, key="spectral_separation")
    dispersion = st.slider("Diffractive dispersion D", 0.0, 0.15, 0.06, key="spectral_dispersion")
    width = 10.0
    wavelengths = np.linspace(500, 600, 401)
    c1, c2 = 550.0 - separation * width / 2, 550.0 + separation * width / 2
    spectra = pd.DataFrame({"S₁(λ)": spectral_gaussian(wavelengths, c1, width), "S₂(λ)": spectral_gaussian(wavelengths, c2, width)}, index=wavelengths)
    labeled_line_chart(spectra, "wavelength λ", "spectral response S(λ)")
    image_x = np.linspace(-3, 3, 301)
    psf_1 = gaussian_2d(image_x, 0, dispersion * (c1 - 550.0), 0, 1.0)
    psf_2 = gaussian_2d(image_x, 0, dispersion * (c2 - 550.0), 0, 1.0)
    labeled_line_chart(pd.DataFrame({"encoded PSF for object 1": psf_1, "encoded PSF for object 2": psf_2}, index=image_x), "image coordinate x", "encoded PSF h_D")
    st.success(f"✓ SciPy integral of S₁ = {simpson(spectra['S₁(λ)'].to_numpy(), x=wavelengths):.6f}; the response is normalized.")
    checkpoint("spectral", "In the diffractive-optic setup, where does wavelength enter the measurement model?", ["Only as a label in Θ", "Inside the PSF h_D, shifting the image", "It does not enter the measurement"], "Inside the PSF h_D, shifting the image", "The optic maps wavelength to a spatial pattern, so image coordinates carry spectral information.")


def page_events():
    lesson_header(11, "Event cameras", ["Separate optical intensity from event generation.", "Define a log-intensity derivative.", "Use polarity-resolved Poisson rates and verify a Jacobian."])
    st.markdown(r"""
An idealized event camera responds to $g(u;\Theta)=\partial_t\log I=\partial_tI/I$.
Because $|g|$ has a kink at zero, use two polarity processes:

$$\Lambda_+=\gamma_e+\eta\max(g,0),\qquad\Lambda_-=\gamma_e+\eta\max(-g,0).$$

This is an idealized likelihood; threshold variability, refractory periods, leakage, timing uncertainty, and pixel correlations may matter physically.
""")
    eta = st.slider("Contrast-to-event scale η", 1.0, 30.0, 8.0, key="event_eta")
    gamma = st.slider("Background event rate γₑ", 0.01, 2.0, 0.2, key="event_gamma")
    speed = st.slider("Emitter speed", 0.1, 2.0, 0.8, key="event_speed")
    xs = np.linspace(-4, 4, 301)
    state1 = (0.0, 0.0, speed, 0.0, 0.0, 0.0, 5.0, 550.0)
    state2 = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 550.0)
    plus, minus = event_rates(xs, np.zeros_like(xs), 550.0, 0.5, state1, state2, 0.5, 1.0, 10.0, eta, gamma)
    labeled_line_chart(pd.DataFrame({"positive polarity": plus, "negative polarity": minus}, index=xs), "image coordinate x", "event rate")
    h = 1e-5
    qp, qm = np.array(state1), np.array(state1)
    qp[0] += h; qm[0] -= h
    fd = (event_rates(0.65, 0.1, 550.0, 0.5, qp, state2, 0.5, 1.0, 10.0, eta, gamma)[0] - event_rates(0.65, 0.1, 550.0, 0.5, qm, state2, 0.5, 1.0, 10.0, eta, gamma)[0]) / (2*h)
    st.success(f"✓ Finite-difference check of ∂Λ₊/∂x₀ = {fd:.8g}")
    checkpoint("events", "What does the event sensor fundamentally measure here?", ["Absolute intensity", "Changes in log intensity", "Wavelength directly"], "Changes in log intensity", "The event rate is driven by temporal contrast; optical intensity remains latent.")


def page_two_object():
    lesson_header(12, "Two-object identifiability", ["Construct a two-parameter FIM.", "Use eigenvalues and condition number as diagnostics.", "See why extra coordinates help only under real data separation."])
    st.markdown(r"""
Estimate only $\Theta=(x_{0,1},x_{0,2})$, treating other state variables as known:

$$\mathcal I_{ij}=\sum_s\iiint\frac1{\Lambda_s}\frac{\partial\Lambda_s}{\partial\Theta_i}\frac{\partial\Lambda_s}{\partial\Theta_j}\,dx\,dy\,dt.$$

A small eigenvalue means some position combination is weakly identified. A large condition number makes inversion fragile. Neither metric automatically proves “super-resolution.”

The velocity sweep below varies $v_2$ while holding $v_1=0.7$ fixed. Thus its
horizontal axis is $v_2-v_1$, but the event model can still depend on the two
absolute velocities, the finite time window, and the two trajectories—not only
their difference.
""")
    separation = st.slider("Spatial separation Δx / σ", 0.05, 3.0, 0.6, key="two_separation")
    spectral_separation = st.slider("Spectral separation Δλ / σλ", 0.0, 4.0, 1.5, key="two_spectral")
    speed_2 = st.slider("Object 2 velocity v₂", -1.5, 1.5, -0.4, key="two_speed")
    dispersion = st.slider("Diffractive dispersion D", 0.0, 0.15, 0.06, key="two_dispersion")
    use_events = st.checkbox("Use event rates", value=True, key="two_events")
    sigma, spectral_width = 1.0, 10.0
    state1 = (-separation / 2, 0.0, 0.7, 0.0, 0.0, 0.0, 5.0, 550.0 - spectral_separation * spectral_width / 2)
    state2 = (separation / 2, 0.0, speed_2, 0.0, 0.0, 0.0, 5.0, 550.0 + spectral_separation * spectral_width / 2)
    xs, ys, wavelengths, ts = np.linspace(-4, 4, 51), np.linspace(-3, 3, 41), np.linspace(500, 600, 31), np.linspace(0, 1, 11)
    xx, yy, ll, tt = np.meshgrid(xs, ys, wavelengths, ts, indexing="ij")

    def rates(a, b):
        if use_events:
            return event_rates(xx, yy, ll, tt, a, b, 0.5, sigma, spectral_width, 8.0, 0.2, dispersion)
        return (total_photon_rate(xx, yy, ll, tt, a, b, 0.5, sigma, spectral_width, dispersion),)

    h = 1e-4
    derivatives = []
    for emitter in (0, 1):
        base = np.array(state1 if emitter == 0 else state2)
        plus_state, minus_state = base.copy(), base.copy()
        plus_state[0] += h; minus_state[0] -= h
        plus_rates = rates(plus_state, state2) if emitter == 0 else rates(state1, plus_state)
        minus_rates = rates(minus_state, state2) if emitter == 0 else rates(state1, minus_state)
        derivatives.append([(p - m) / (2 * h) for p, m in zip(plus_rates, minus_rates)])
    rates_at_truth = rates(state1, state2)
    fim = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            for rate, di, dj in zip(rates_at_truth, derivatives[i], derivatives[j]):
                fim[i, j] += integrate(di * dj / np.maximum(rate, 1e-9), (xs, ys, wavelengths, ts))
    fim = (fim + fim.T) / 2
    eigenvalues = eigvalsh(fim)
    st.dataframe(pd.DataFrame(fim, index=["x₀,1", "x₀,2"], columns=["x₀,1", "x₀,2"]).round(5), width="stretch")
    c1, c2, c3 = st.columns(3)
    c1.metric("Smallest eigenvalue", f"{eigenvalues[0]:.4g}")
    c2.metric("Largest eigenvalue", f"{eigenvalues[-1]:.4g}")
    c3.metric("Condition number", f"{eigenvalues[-1] / max(eigenvalues[0], 1e-15):.4g}")
    if eigenvalues[0] > 1e-8:
        crlb = np.linalg.inv(fim)
        st.success(f"✓ Positive-definite FIM. CRLB SDs: σ(x₀,1)={np.sqrt(crlb[0, 0]):.4g}, σ(x₀,2)={np.sqrt(crlb[1, 1]):.4g}.")
    else:
        st.warning("The FIM is nearly singular. The selected model cannot reliably separate both position parameters locally.")

    st.subheader("CRLB sweeps")
    st.markdown(r"""
The following plots hold the other settings fixed and recompute the position FIM
for each point. The plotted quantities are the diagonal entries of

$$\mathcal I^{-1}=\operatorname{CRLB},$$

so they are **variance bounds** for $x_{0,1}$ and $x_{0,2}$. A missing point means
the numerical FIM became singular or too ill-conditioned to invert reliably.
""")
    sweep_points = np.linspace(0.0, 4.0, 21)
    with st.spinner("Computing CRLB versus spectral separation…"):
        spectral_rows = []
        for delta_lambda in sweep_points:
            var_1, var_2, correlation, minimum_eigenvalue = position_crlb(separation, float(delta_lambda), speed_2, use_events, dispersion)
            spectral_rows.append({"Δλ / σλ": delta_lambda, "CRLB var(x₀,1)": var_1, "CRLB var(x₀,2)": var_2, "position correlation": correlation})
    spectral_frame = pd.DataFrame(spectral_rows).set_index("Δλ / σλ")
    labeled_line_chart(spectral_frame[["CRLB var(x₀,1)", "CRLB var(x₀,2)"]], "spectral separation Δλ / σλ", "CRLB variance of initial position")
    st.caption("Spectral sweep: spatial separation, velocity, dispersion, and event/photon choice are held at the selected values.")

    velocity_points = np.linspace(-1.5, 1.5, 21)
    with st.spinner("Computing CRLB versus relative velocity…"):
        velocity_rows = []
        for candidate_speed_2 in velocity_points:
            var_1, var_2, correlation, minimum_eigenvalue = position_crlb(separation, spectral_separation, float(candidate_speed_2), use_events, dispersion)
            velocity_rows.append({"relative velocity v₂ − v₁": candidate_speed_2 - 0.7, "CRLB var(x₀,1)": var_1, "CRLB var(x₀,2)": var_2, "position correlation": correlation})
    velocity_frame = pd.DataFrame(velocity_rows).set_index("relative velocity v₂ − v₁")
    labeled_line_chart(velocity_frame[["CRLB var(x₀,1)", "CRLB var(x₀,2)"]], "relative velocity v₂ − v₁", "CRLB variance of initial position")
    st.caption("Velocity sweep: spatial separation, spectrum, dispersion, and event/photon choice are held at the selected values.")
    if use_events:
        st.info("With event rates selected, a triangular or piecewise-linear-looking curve is a model signature: motion-induced events scale with temporal contrast, the polarity split uses max(±g, 0), and a nearly stationary object produces little motion information. Because v₁=0.7 is fixed, the stationary-object point v₂=0 appears at relative velocity v₂−v₁=−0.7. This is different from equal velocities (v₂−v₁=0), where both objects move but may have strongly correlated event signatures. It is not a universal CRLB law. Compare with photon rates using the checkbox above.")
    else:
        st.info("With photon rates selected, the curve should be smoother because the absolute intensity is observed. Any remaining structure comes from PSF overlap, finite observation time, and the chosen trajectories.")

    st.subheader("Corrected event CRLB versus total event count")
    st.markdown(r"""
This comparison uses the ideal independent-axis event model on $(x,t,\lambda)$.
It estimates $(x_{0,1},x_{0,2})$ and uses two informative baselines:

- **Same motion:** both objects move at $100\ \mathrm{nm/s}$ and have the same spectrum.
- **Different motion and spectrum:** object 1 moves at $100\ \mathrm{nm/s}$,
  object 2 at $200\ \mathrm{nm/s}$, and their spectral centers differ by $10\ \mathrm{nm}$.

The polarity-resolved rates are integrated with the actual $dx\,dt\,d\lambda$
volume element. For a fixed normalized event shape,

$$\sigma_x(N_e)=\frac{C_x}{\sqrt{N_e}}.$$

A stationary-object scenario is correctly treated as an uninformative event model,
not repaired with an epsilon.
""")
    same_motion = independent_axis_event_multiplier(separation * 150.0, 100.0, 100.0, 500.0, 500.0)
    different_motion = independent_axis_event_multiplier(separation * 150.0, 100.0, 200.0, 500.0, 510.0)
    recording_duration = 1.0
    event_rates_per_second = np.logspace(2, 6, 80)
    expected_events = event_rates_per_second * recording_duration
    event_count_frame = pd.DataFrame({
        "same motion σ(x₀,1)": same_motion[0] / np.sqrt(expected_events),
        "different motion/spectrum σ(x₀,1)": different_motion[0] / np.sqrt(expected_events),
    }, index=event_rates_per_second)
    labeled_line_chart(event_count_frame, "recording-averaged event rate Rₑ [events/s]", "CRLB standard deviation σ(x₀,1) [nm]")
    st.caption(f"Recording duration T={recording_duration:.1f} s. Geometry multipliers: same motion C₁={same_motion[0]:.3g}; different motion/spectrum C₁={different_motion[0]:.3g}.")

    with st.expander("Inspect position correlation"):
        labeled_line_chart(spectral_frame[["position correlation"]].rename(columns={"position correlation": "corr(x₀,1, x₀,2)"}), "spectral separation Δλ / σλ", "position correlation")
        labeled_line_chart(velocity_frame[["position correlation"]].rename(columns={"position correlation": "corr(x₀,1, x₀,2)"}), "relative velocity v₂ − v₁", "position correlation")
    checkpoint("two_object", "Does spectral separation guarantee zero spatial cross-terms?", ["Yes, always", "No, it may reduce them but depends on the full integral", "Only if stationary"], "No, it may reduce them but depends on the full integral", "Orthogonality must be calculated for a specific model and window.")


def page_audit():
    lesson_header(13, "Final proof audit", ["Separate identities from assumptions.", "State what the CRLB can and cannot prove.", "Identify missing ingredients for a physical study."])
    st.markdown(r"""
### Proven under the stated assumptions

- Gaussian-mean Fisher information and scalar CRLB.
- Vector-parameter matrix CRLB, model Jacobian construction, reparameterization, and nuisance-parameter Schur complements.
- Poisson-process FIM $\int(\partial_i\Lambda\,\partial_j\Lambda)/\Lambda$.
- Gaussian PSF spatial, temporal, and mixed derivatives.
- Wavelength-augmented rate model when spectral information is measured.
- Event-rate FIM after choosing a polarity-resolved Poisson approximation.
- Local covariance bound $\operatorname{cov}(\hat\Theta)\succeq\mathcal I^{-1}$ when regularity conditions hold.

### Claims requiring caution

- **Adding dimensions does not make localization trivial.** They help only when the measurement contains parameter-dependent information.
- **Cross-terms do not automatically vanish.** They may be small for a particular PSF, window, spectrum, motion, and background.
- **Events do not automatically beat diffraction.** Temporal differentiation does not restore optical spatial frequencies removed by the transfer function.
- **Wavelength is not automatically available.** It must be measured or encoded.

To move toward an experiment, use the real optical transfer function, pixel sampling,
spectral encoding, event threshold distribution, refractory behavior, timing uncertainty,
background, flux uncertainty, nuisance parameters, and an actual estimator or two-object test.
""")
    st.success(f"Completed checkpoints: {sum(st.session_state.checks.values())} / {len(st.session_state.checks)} answered so far.")


initialize_state()
st.sidebar.title("Localization CRLB course")
st.sidebar.caption("Probability → information → localization")
navigation()
pages = [page_overview, page_observations, page_likelihood, page_information, page_vector_parameters, page_scalar_crlb, page_poisson, page_ppp_fim, page_gaussian, page_motion, page_spectral, page_events, page_two_object, page_audit]
pages[st.session_state.lesson]()
