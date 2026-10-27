import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from pathlib import Path
    import polars as pl
    import matplotlib.pyplot as plt
    from scipy.interpolate import interp1d
    from scipy.signal import medfilt, savgol_filter
    import numpy as np



    return Path, pl, plt, savgol_filter


@app.cell
def _(Path, pl, plt, savgol_filter):
    data_dir = Path("/home/user/Projects/hypercam/data/raw/spectra/")
    parquet_files = sorted(data_dir.glob("2026*.parquet"))

    signal_lf = pl.scan_parquet(parquet_files[55])
    ref_lf = pl.scan_parquet(data_dir / "reference.parquet").select(
        "wavelength_nm",
        ref_intensity=pl.col("intensity_counts"),
    )


    lazy_df = (
        signal_lf.join(ref_lf, on="wavelength_nm", how="inner")
        .sort("wavelength_nm")
        .filter(pl.col("wavelength_nm").is_between(420, 680))
        .with_columns(
            transmittance=pl.col("intensity_counts") / pl.col("ref_intensity")
        )
        .with_columns(
            t_norm=pl.col("transmittance") / pl.col("transmittance").max()
        )
        .with_columns(
            t_filtered=pl.col("transmittance").rolling_median(
                window_size=3, center=True, min_samples=1
            )
        )
        .with_columns(
            t_smoothed=pl.col("t_filtered").map_batches(
                lambda s: savgol_filter(s.to_numpy(), window_length=40, polyorder=2),
                return_dtype=pl.Float64,
            )
        )

        .with_columns(t_smoothed=pl.col('t_smoothed') / pl.col('t_smoothed').max())
    )

    df = lazy_df.collect()
    print(df.count())
    plt.plot(df["wavelength_nm"], df["t_smoothed"])
    plt.show()
    return


if __name__ == "__main__":
    app.run()
