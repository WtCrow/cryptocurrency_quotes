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

ENV RABBIT_MQ_STR_CONN=amqp://main_web:passwd_web@rabbit:5672/
ENV EXCHANGER=topic
ENV ROUTING_KEY_LISTING=crypto_currency_ms_listing
ENV ERROR_QUEUE=crypto_currency_ms_err
ENV QUEUE_SERVICE_CRYPTO_QUOTES=crypto_currency_ms

CMD ["gunicorn", "cryptoview.app:create_app",  "--bind",  "0.0.0.0:8080", "--worker-class", "aiohttp.GunicornWebWorker"]

