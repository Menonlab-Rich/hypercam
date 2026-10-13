import matplotlib.pyplot as plt
import numpy as np

# Integration time (T) from 10 seconds to 10 microseconds
T = np.logspace(np.log10(10), np.log10(1e-5), 1000)

# Calculate FPS (1 / T)
# Range will be from 0.1 Hz to 100,000 Hz
fps = 1 / T

# Arbitrary baseline constants to illustrate the scaling behaviors
alpha = 1.0       # Proportionality constant for photon-limited scaling
c_floor = 100.0   # Constant variance floor from threshold quantization

# 1. CMOS Lower Bound
# Variance scales as O(1/T) in the photon-limited regime.
# Because FPS = 1/T, the variance increases linearly with FPS.
crlb_cmos = alpha * (1 / T)

# 2. Event Sensor Lower Bound (Frame-based approximation)
# - Long integration (Low FPS): Bounded by a constant quantization floor.
# - Short integration (High FPS): Photon-starved, scaling reverts to the O(1/T) limit.
crlb_event = c_floor + alpha * (1 / T)

# Plot generation
plt.figure(figsize=(10, 6))

plt.loglog(fps, crlb_event, label='Event Sensor Bound (Constant Floor to Photon-Starved)', color='red', linewidth=2.5)
plt.loglog(fps, crlb_cmos, label='Ideal CMOS Bound (Photon-Limited)', linestyle='--', color='blue', linewidth=2)

# Axis labels and formatting
plt.title('Fundamental Localization Limits: CMOS vs Frame-Based Event Sensors')
plt.xlabel('FPS (1/T) [Hz]')
plt.ylabel('Cramér-Rao Lower Bound (Variance Error)')
ax = plt.gca()
ax.invert_yaxis()
plt.grid(True, which="both", ls="--", alpha=0.3)
plt.legend()

plt.tight_layout()
plt.show()
