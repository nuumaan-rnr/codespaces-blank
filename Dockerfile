# RackVerify (by Racks & Rollers) - deployment image.
#
# Persistent app data (projects/masters/users - flat JSON/pickle files, not
# a database) is NOT baked into the image. Mount a persistent volume at
# /data and the container runs with that as its working directory, so
# rack15512's ProjectStore("projects") / MasterStore("masters") /
# UserStore("users") - all relative paths - resolve under /data and survive
# restarts and redeploys. An empty /data on first boot is fine: each store
# creates its own root directory automatically.
FROM python:3.11-slim

# openseespy's compiled extension needs these system libraries (verified
# against the actual runtime this app was developed/tested in).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libblas3 liblapack3 libgfortran5 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

RUN mkdir -p /data
WORKDIR /data

EXPOSE 8501
# $PORT is honoured when the platform assigns one (e.g. Render); otherwise
# falls back to Streamlit's default.
CMD ["sh", "-c", "streamlit run /app/app_streamlit.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
