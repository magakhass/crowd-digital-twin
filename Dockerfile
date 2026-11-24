# Image for the live demo, the tests and single simulation runs
# JuPedSim only ships x86-64 Linux wheels, so this is an amd64 image (emulated on Apple silicon)
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg

# JuPedSim's own viewer pulls in PySide6 and VTK (about 1.2 GB) that the simulation never uses,
# so it goes in without its dependencies (same trajectories, checked byte for byte)
COPY requirements.txt .
RUN tr -d '\r' < requirements.txt > /tmp/req.txt \
 && grep -v '^jupedsim' /tmp/req.txt > /tmp/req-core.txt \
 && pip install --no-cache-dir -r /tmp/req-core.txt deprecated \
 && pip install --no-cache-dir --no-deps "$(grep '^jupedsim' /tmp/req.txt | cut -d' ' -f1)"

COPY . .

CMD ["python", "-m", "pytest", "-q", "tests"]
