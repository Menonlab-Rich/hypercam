import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 1. Load results and calculate metrics
df = pd.read_csv('crlb_results.csv')
df['metric_x'] = df['sigma_x'] / df['z']
df['metric_y'] = df['sigma_y'] / df['z']
df['metric_z'] = df['sigma_z'] / df['z']
df['fps'] = 1.0 / df['dt'] # FPS as 1/dt

# --- Reference Benchmarks (Traced & Extrapolated to 10kHz) ---
ref_fps = np.logspace(-2, 4, 500)
crlb_line = 4.2e-5 * (ref_fps**0.5)
info_line = 5.2e-3 * (ref_fps**0.35)
trad_line = 0.18 * (ref_fps**0.15)

metrics = ['metric_x', 'metric_y', 'metric_z']
labels = ['X', 'Y', 'Z']
all_zs = sorted(df['z'].unique())

# --- Plot 1: Broken out by Z ---
fig1, axes1 = plt.subplots(3, 1, figsize=(11, 16))
colors = plt.cm.viridis(np.linspace(0, 0.8, len(all_zs)))

for i, ax in enumerate(axes1):
    if labels[i] == 'Z':
        ax.plot(ref_fps, crlb_line, color='#6a329f', linestyle='--', label='Cramér-Rao bound')
        ax.plot(ref_fps, info_line, color='#3182bd', linestyle='--', label='Spatial/Spectral/Temporal')
        ax.plot(ref_fps, trad_line, color='#636363', linestyle='--', label='Traditional Imaging')
        ax.set_ylim(1e-5, 1)
    else:
        ax.set_ylim(0.1, 1000)
    
    for idx, z in enumerate(all_zs):
        subset = df[df['z'] == z].sort_values('fps')
        ax.plot(subset['fps'], subset[metrics[i]], marker='o', markersize=4, color=colors[idx], label=f'z={z}m')

    ax.set_ylabel(fr'Metric {labels[i]} ($\sigma_{labels[i].lower()}$ / z)')
    ax.set_xlabel('Update rate (Hz)')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(0.01, 10000)
    ax.invert_yaxis()
    ax.grid(True, which="both", ls="-", alpha=0.2)
    ax.legend(fontsize='x-small', bbox_to_anchor=(1.02, 1), loc='upper left')

axes1[0].set_title('Positional Accuracy vs Update Rate (By Distance)')
fig1.tight_layout()
fig1.savefig('crlb_broken_out.png', bbox_inches='tight')

# --- Plot 2: Geometric Mean Trend Line ---
trend_df = df.groupby('fps')[metrics].apply(
    lambda x: np.exp(np.log(x).mean())
).reset_index()

fig2, axes2 = plt.subplots(3, 1, figsize=(11, 16))
for i, ax in enumerate(axes2):
    if labels[i] == 'Z':
        ax.plot(ref_fps, crlb_line, color='#6a329f', linestyle='--', label='Cramér-Rao bound')
        ax.plot(ref_fps, info_line, color='#3182bd', linestyle='--', label='Spatial/Spectral/Temporal')
        ax.plot(ref_fps, trad_line, color='#636363', linestyle='--', label='Traditional Imaging')
        ax.set_ylim(1e-5, 1)
    else:
        ax.set_ylim(0.1, 1000)
    
    ax.plot(trend_df['fps'], trend_df[metrics[i]], marker='s', linewidth=2, color='#FF9933', label='Geometric Mean')

    ax.set_ylabel(fr'Metric {labels[i]} ($\sigma_{labels[i].lower()}$ / z)')
    ax.set_xlabel('Update rate (Hz)')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(0.01, 10000)
    ax.invert_yaxis()
    ax.grid(True, which="both", ls="-", alpha=0.2)
    ax.legend(fontsize='x-small', bbox_to_anchor=(1.02, 1), loc='upper left')

axes2[0].set_title('Positional Accuracy vs Update Rate (Geometric Mean)')
fig2.tight_layout()
fig2.savefig('crlb_trend.png', bbox_inches='tight')
