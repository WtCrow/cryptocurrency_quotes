FROM python:3.8-alpine
WORKDIR /usr/src/crypto_quotes

RUN apk update && apk add build-base
RUN pip3 install --no-cache --upgrade pip setuptools

COPY . /usr/src/crypto_quotes/
RUN pip3 install --no-cache-dir -r /usr/src/crypto_quotes/requirements.txt

ENV RABBIT_MQ_STR_CONN=amqp://market_data_service:passwd_service_quotes@rabbit:5672/
ENV EXCHANGER=topic_logs
ENV QUEUE_THIS_SERVICE=crypto_currency_ms
ENV ERROR_QUEUE=crypto_currency_ms_err
ENV ROUTING_KEY_LISTING=crypto_currency_ms_listing

CMD python3 main.py
