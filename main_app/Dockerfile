FROM python:3.7.4-alpine
WORKDIR /usr/src/web

RUN apk add build-base
RUN pip install --upgrade pip

COPY requirements.txt /usr/src/web/
RUN pip install --no-cache-dir -r /usr/src/web/requirements.txt

COPY . /usr/src/web/

EXPOSE 8080

RUN adduser -D new_user
USER new_user

CMD ["gunicorn", "cryptoview.app:create_app",  "--bind",  "0.0.0.0:8080", "--worker-class", "aiohttp.GunicornWebWorker"]

