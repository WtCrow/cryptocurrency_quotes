FROM python:3.7.4-alpine
WORKDIR /usr/src/web_app

RUN pip install --upgrade pip

COPY requirements.txt /usr/src/web_app/
RUN pip3 install --no-cache-dir -r /usr/src/web_app/requirements.txt
RUN pip3 install --no-cache-dir gunicorn

COPY . /usr/src/web_app/

EXPOSE 8080

CMD ["gunicorn", "cryptoview.app:create_app",  "--bind",  "0.0.0.0:8080", "--worker-class", "aiohttp.GunicornWebWorker"]
