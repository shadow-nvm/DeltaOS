# Reproducible DeltaOS ISO builder.
#   docker build -t deltaos-builder build/
#   docker run --rm --privileged -v "$PWD:/work" deltaos-builder
FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        live-build \
        debootstrap \
        squashfs-tools \
        xorriso \
        dosfstools \
        mtools \
        cpio \
        rsync \
        curl \
        ca-certificates \
        python3 \
        python3-pil \
        xz-utils \
        zstd \
        git \
        grub-common \
        grub-pc-bin \
        grub-efi-amd64-bin \
        fonts-dejavu-core \
        memtest86+ \
        libarchive-tools \
    && rm -rf /var/lib/apt/lists/*

# live-build refuses to run as a plain user for chroot and loop setup.
WORKDIR /work
CMD ["bash", "./build/build-iso.sh", "core"]
