FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary aur shapely dono manylinux prebuilt wheels ke saath
# aate hain — isliye GDAL/GEOS jaisi heavy system libraries apt-get se
# install NAHI karni padtin. Hackathon ke liye build time seconds mein.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
COPY ./frontend ./frontend

EXPOSE 8000

# --reload production/Docker mein use nahi karte (dev-only feature,
# container ke andar file-watching unpredictable behave karta hai).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]