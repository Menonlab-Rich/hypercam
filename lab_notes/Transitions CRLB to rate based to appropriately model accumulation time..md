### 1. Asymmetric Motion Blur and Information Truncation

- **What needs to change:** The point spread function (PSF) must transition from a static spatial distribution to a velocity-warped, directionally dependent spatial distribution.
    
- **How to change it:** Instead of numerical time-step integration, apply a closed-form spatial transfer function to the intensity field $I^b$. This function must account for the pixel dwell time $t_{dwell} \approx \frac{w_{PSF}}{v}$ and cap the maximum local intensity using the refractory limit $\frac{t_{dwell}}{t_{ref}}$.
    
- **Why it is necessary:** In event cameras, motion blur is not a symmetric smear. When a bright object moves, the leading edge of the PSF triggers a rapid succession of events, but the rate of change $\frac{\partial \log I}{\partial t}$ often exceeds the pixel's recovery rate. The pixel enters its dead state, flattening or omitting the peak and trailing edge of the PSF. This "comet-tail" distortion makes the spatial gradients ($\frac{\partial I}{\partial x}, \frac{\partial I}{\partial y}$) highly dependent on the velocity vector, causing the Fisher Information to be higher on the leading edge and truncated on the trailing edge.
    

### 2. The State Vector: Kinematic Parameterization

- **What needs to change:** The parameter set $\theta$ being optimized must shift from absolute spatial coordinates to kinematic variables.
    
- **How to change it:** Update the parameter matrix from discrete endpoints $\theta = \{x_t, y_t, z_t, x_{t-\tau}, y_{t-\tau}, z_{t-\tau}\}$ to an initial state and velocity vector:
    
    $$\theta_{kinematic} = \{x_0, y_0, z_0, v_x, v_y, v_z\}$$
    
- **Why it is necessary:** Over a continuous accumulation period, a single discrete position is insufficient. Re-parameterizing with velocity allows the Jacobian matrix to evaluate the system's sensitivity to changes in speed and heading, yielding a CRLB for velocity tracking rather than isolated spatial localization.
    

### 3. Event Sensor Realities: Refractory Dead-Time

- **What needs to change:** The expected mean event count ($N_{ideal}$) must be capped by the physical limits of the pixel's reset circuitry across the entire accumulation window.
    
- **How to change it:** Apply a non-paralyzable dead-time saturation factor based on the hardware refractory period ($t_{ref}$):
    
    $$N_{obs} = \frac{N_{ideal}}{1 + N_{ideal} \left(\frac{t_{ref}}{t_a}\right)}$$
    
    This squashing factor must be chained through to the mean's derivative: $\frac{\partial N_{obs}}{\partial \theta}$.
    
- **Why it is necessary:** Event pixels go "blind" for 1–10 µs after firing. If an object attempts to trigger events faster than the hardware allows, this saturation flattens the spatial gradient to zero. It correctly models the loss of tracking precision when a pixel becomes paralyzed by a high-frequency signal.
    

### 4. Event Sensor Realities: Dynamic Thresholding & Reset Noise

- **What needs to change:** The variance of the measurement must scale continuously with the number of times the pixel actually fires.
    
- **How to change it:** Add a linearly scaling electronic noise term to the baseline shot noise and quantization variance:
    
    $$\text{Var}_{total} = \text{Var}_{shot} + N_{obs} \cdot \sigma_{reset}^2 + \text{Var}_{quantization}$$
    
- **Why it is necessary:** Event cameras use Lebesgue sampling; the comparator reference voltage physically resets after every threshold crossing. Each reset injects independent $kTC$ thermal noise and comparator jitter. Consequently, high-event-rate signals accumulate more electronic variance over $t_a$.
    

### 5. Statistical Adjustments: Covariance in Overlapping Windows

- **What needs to change:** The zero-covariance assumption in the Delta method must be discarded when accumulation intervals overlap.
    
- **How to change it:** If $t_a$ exceeds the temporal baseline $\tau$, inject the exact covariance term into the variance of the ratio $\frac{X}{Y}$:
    
    $$\text{Var}\left(\frac{X}{Y}\right) \approx \frac{\text{Var}(X)}{\mu_Y^2} + \frac{\mu_X^2 \text{Var}(Y)}{\mu_Y^4} - \frac{2\mu_X}{\mu_Y^3}\text{Cov}(X,Y)$$
    
- **Why it is necessary:** When integration windows overlap, the measurement variables $X$ ($I_t^b$) and $Y$ ($I_{t-\tau}^b$) share the exact same physical photons captured during the overlapping duration. This correlates the noise between the two frames, altering the dispersion of the log-difference.
    

### 6. The Precision Floor: The Quantization Asymptote

- **What needs to change:** The relationship between photon flux, accumulation time, and theoretical precision must hit a hard mathematical floor.
    
- **How to change it:** No explicit code changes are required if the variance derivations above are correctly implemented. As $t_a \to \infty$ and photon flux $\mu, \nu \to \infty$, the Poisson shot noise fractions ($\frac{1}{\mu}, \frac{1}{\nu}$) approach zero.
    
- **Why it is necessary:** In a standard camera, infinite light yields near-infinite precision (until full-well saturation). In an event camera, even with infinite photons, precision asymptotes to a strict limit defined purely by the threshold quantization error ($\frac{1}{3}$) and the accumulated reset noise ($N_{obs} \cdot \sigma_{reset}^2$).