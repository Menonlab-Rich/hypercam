#!/usr/bin/env bash

# Use hyphens instead of colons for time formatting to maintain filesystem compatibility
now=$(date '+%Y-%m-%d_%H-%M-%S')
output_dir=$HOME/Projects/hypercam/data/raw

# Ensure output directories exist
mkdir -p "$output_dir/spectra"
mkdir -p "$output_dir/evt3"

thorcct --output "$output_dir/spectra/$now.parquet" --no-amplitude-correction -e 1000 -a 10 
triton-capture --output "$output_dir/evt3/$now" -d "5" --no-date
