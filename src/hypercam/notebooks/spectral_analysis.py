import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path
    import polars as pl
    import matplotlib.pyplot as plt
    import random

    return Path, pl, plt, random


@app.cell
def _(Path, pl):
    # Scan all normalized parquet files
    data_dir = Path("data/raw/spectra/normalized")
    lazy_df = pl.scan_parquet(data_dir / "*.parquet")

    # Aggregate across all files per wavelength
    df_summary = (
        pl.scan_parquet("data/raw/spectra/normalized/*.parquet")
        .filter(
            (pl.col("wavelength_nm") >= 320) & (pl.col("wavelength_nm") <= 720)
        )
        .group_by("wavelength_nm")
        .agg(
            median=pl.col("reflectance").median(),
            p05=pl.col("reflectance").quantile(0.05),
            p95=pl.col("reflectance").quantile(0.95),
            p25=pl.col("reflectance").quantile(0.25),
            p75=pl.col("reflectance").quantile(0.75),
        )
        .sort("wavelength_nm")
        .collect()
    )


    return (df_summary,)


@app.cell
def _(df_summary, plt):
    fig, ax = plt.subplots(figsize=(10, 5))

    wavelengths = df_summary["wavelength_nm"].to_numpy()

    # Shaded 90% interval (P05 - P95)
    ax.fill_between(
        wavelengths,
        df_summary["p05"].to_numpy(),
        df_summary["p95"].to_numpy(),
        color="tab:blue",
        alpha=0.15,
        label="5th–95th Percentile Range",
    )

    # Shaded Interquartile Range (P25 - P75)
    ax.fill_between(
        wavelengths,
        df_summary["p25"].to_numpy(),
        df_summary["p75"].to_numpy(),
        color="tab:blue",
        alpha=0.35,
        label="IQR (25th–75th Percentile)",
    )

    # Median Spectrum
    ax.plot(
        wavelengths,
        df_summary["median"].to_numpy(),
        color="tab:blue",
        linewidth=1.5,
        label="Median Spectrum",
    )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Normalized Reflectance")
    ax.set_title("Spectral Distribution Across Recordings")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right")

    plt.tight_layout()
    plt.show()
    return


@app.cell
def _(Path, pl, plt, random):
    def _():
        data_dir = Path("data/raw/spectra/normalized")
        # Get list of all parquet files
        all_files = sorted(list(data_dir.glob("*.parquet")))
    
        # Pick 5 random files (or set a seed for reproducibility)
        random.seed(42)
        sample_files = random.sample(all_files, min(2, len(all_files)))
    
        fig, ax = plt.subplots(figsize=(10, 5))
    
        for file_path in sample_files:
            df = pl.read_parquet(file_path).filter(
                (pl.col("wavelength_nm") >= 320) & (pl.col("wavelength_nm") <= 720)
            )
    
            # If each file contains multiple spectra, take the first one (spectrum_index == 0)
            if "spectrum_index" in df.columns:
                first_index = df["spectrum_index"].min()
                df = df.filter(pl.col("spectrum_index") == first_index)
    
            ax.plot(
                df["wavelength_nm"].to_numpy(),
                df["reflectance"].to_numpy(),
                alpha=0.8,
                linewidth=1.2,
                label=file_path.stem,
            )
    
        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("Reflectance")
        ax.set_title("5 Random Individual Spectral Signatures")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", fontsize="small")
    
        plt.tight_layout()
        plt.show()

    _()
    return


if __name__ == "__main__":
    app.run()
