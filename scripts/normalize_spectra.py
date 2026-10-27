from pathlib import Path
import polars as pl


def normalize_directory(data_dir: Path | str) -> None:
    data_dir = Path(data_dir)
    ref_path = data_dir / "reference_white.parquet"

    if not ref_path.exists():
        raise FileNotFoundError(f"Reference file not found: {ref_path}")

    output_dir = data_dir / "normalized"
    output_dir.mkdir(exist_ok=True)

    # Read reference and select only join keys and reference intensity
    ref_df = pl.read_parquet(ref_path).select(
        [
            pl.col("wavelength_nm"),
            pl.col("intensity_counts").alias("ref_intensity"),
        ]
    )

    # Find all parquet files excluding reference and anything in subdirectories
    parquet_files = [p for p in data_dir.glob("*.csv")]

    for file_path in parquet_files:
        df = pl.read_parquet(file_path)

        # Join on wavelength and divide intensity by reference
        df_normalized = (
            df.join(ref_df, on="wavelength_nm", how="left")
            .with_columns(
                (pl.col("intensity_counts") / pl.col("ref_intensity")).alias(
                    "reflectance"
                )
            )
            .drop("ref_intensity")
        )

        df_normalized = df_normalized.with_columns(
            reflectance=pl.col("reflectance") / pl.col("reflectance").max()
        )

        output_path = output_dir / f"{file_path.stem}.parquet"
        df_normalized.write_parquet(output_path)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    # Replace with path to your directory
    normalize_directory("./data/raw/spectra")
