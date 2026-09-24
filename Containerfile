# Containerfile — packages the untracked experiment data and analysis results
# as a container image.
#
# The image has no base layer at all (FROM scratch): it exists purely to
# transport the contents that are too large for GitHub — the data/ directory
# (EVT3 recordings and CAD models) and the results/ directory (analysis
# outputs). One image is built per commit and tagged with the commit SHA, so
# a data+results snapshot can always be mapped back to the exact source state
# that produced it.
#
# Build context is a staging directory assembled by scripts/data_image_build.sh
# (hard-linked copies of the real subtrees, so nothing is duplicated on disk
# and the data may live outside the repo checkout). The COPY paths below are
# relative to that staging context. See scripts/data_image_build.sh for the
# canonical build/publish flow and scripts/data_image_mount.sh for pulling
# and mounting an image on a machine without local data.
#
# Note on architecture: the image is data-only, so the recorded platform is
# irrelevant; it is pulled and mounted on any host.
#
# ==============================================================================
# Author:        Richard G. Baird
# Date Modified: 2026-09-24
# Notice:        This file was authored or modified with the assistance of
#                Kilo (GLM, z-ai/glm-5.3-flash).
# ==============================================================================

# OCI metadata supplied by scripts/data_image_build.sh (or the CI workflow).
ARG SOURCE_COMMIT=unknown
ARG SOURCE_URL=https://github.com/richbai90/hypercam
ARG BUILT_AT=unknown

FROM scratch

# The experiment data and analysis results. Keep this list in sync with
# data/README.md and results/README.md; each entry becomes its own layer, so
# an unchanged subtree is not re-uploaded to the registry when only another
# subtree changed.
COPY raw/ /data/raw/
COPY cad_models/ /data/cad_models/
COPY results/ /data/results/

ARG SOURCE_COMMIT
ARG SOURCE_URL
ARG BUILT_AT
LABEL org.opencontainers.image.title="hypercam experiment data" \
      org.opencontainers.image.description="EVT3 recordings, trigger logs, exported videos and CAD models backing the hypercam spectral-correlation analysis" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.created="${BUILT_AT}"
