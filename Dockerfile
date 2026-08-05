FROM kbase/sdkpython:3.8.0
LABEL maintainer="ac.shahnam"
USER root

# ------------------------------------------------------------
# 1) System dependencies
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl bzip2 ca-certificates git \
    diamond-aligner prodigal && \
    rm -rf /var/lib/apt/lists/*

RUN pip install jsonrpcbase

# ------------------------------------------------------------
# 2) micromamba bootstrap
# ------------------------------------------------------------
ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV MAMBA_NO_BANNER=1
ENV MAMBA_DOCKERFILE_ACTIVATE=0

ADD https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64 /usr/local/bin/micromamba
RUN chmod +x /usr/local/bin/micromamba

# ------------------------------------------------------------
# 3) Create CheckM2 conda environment
# ------------------------------------------------------------
COPY env-checkm2.yml /tmp/env-checkm2.yml
RUN micromamba create -y -n checkm2 -f /tmp/env-checkm2.yml

RUN /opt/conda/envs/checkm2/bin/pip install --no-cache-dir \
        "numpy<1.24" \
        "pandas==1.5.3"

RUN /opt/conda/envs/checkm2/bin/pip install --no-cache-dir \
        "tensorflow-cpu==2.13.*" \
        "keras==2.13.*"

RUN /opt/conda/envs/checkm2/bin/pip install --no-cache-dir \
        "CheckM2>=1.0.0"

RUN micromamba clean -a -y
#RUN conda install -c bioconda multiqc

# ------------------------------------------------------------
# 4) Verify CheckM2 installation (build-time sanity check)
# ------------------------------------------------------------
RUN /opt/conda/envs/checkm2/bin/python -c "\
import os, checkm2; \
from importlib.metadata import version; \
p = os.path.join(os.path.dirname(checkm2.__file__), 'models'); \
print('CheckM2', version('CheckM2')); \
print('models_dir', p); \
print('models_exists', os.path.isdir(p)); \
print('models_contents', os.listdir(p)[:200] if os.path.isdir(p) else 'N/A')"

#RUN /opt/conda/envs/checkm2/bin/python -c \
    #"import tensorflow as tf, keras; print('tf', tf.__version__); print('keras', keras.__version__)"

RUN /opt/conda/envs/checkm2/bin/checkm2 --version

# ------------------------------------------------------------
# 5) Set database path - database is downloaded at registration
#    time via entrypoint.sh init into /data (mounted volume)
# ------------------------------------------------------------
ENV CHECKM2DB=/data/checkm2_db/CheckM2_database/CheckM2_database.dmnd

# NOTE: PATH is intentionally NOT modified here.
# Always call checkm2 via /opt/conda/envs/checkm2/bin/checkm2 in impl.py

# ------------------------------------------------------------
# 6) Copy module and finalize
# ------------------------------------------------------------
COPY ./ /kb/module
RUN mkdir -p /kb/module/work
RUN chmod -R a+rw /kb/module

WORKDIR /kb/module
RUN make all

ENTRYPOINT [ "./scripts/entrypoint.sh" ]
CMD [ ]
