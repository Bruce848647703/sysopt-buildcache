from __future__ import annotations

import pytest

BUILD_LOG = """\
#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 512B done
#1 DONE 0.0s
#2 [1/6] FROM python:3.12-slim
#2 CACHED
#3 [2/6] RUN apt-get update && apt-get install -y curl
#3 DONE 4.2s
#4 [3/6] COPY . .
#4 DONE 0.1s
#5 [4/6] RUN pip install -r requirements.txt
#5 DONE 12.0s
#6 [5/6] RUN curl -sSL https://example.com/install.sh | sh
#6 DONE 1.0s
#7 [6/6] ADD https://example.com/app.tar.gz /opt/
#7 CACHED
"""


@pytest.fixture
def build_log() -> str:
    return BUILD_LOG