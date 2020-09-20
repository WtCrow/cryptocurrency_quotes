FROM python:3.8-alpine
WORKDIR /usr/src/web

RUN apk update && apk add --no-cache supervisor nginx build-base
RUN pip3 install --no-cache --upgrade pip setuptools

COPY . /usr/src/web/
COPY cryptoview/static /usr/src/web/static
RUN pip install --no-cache-dir -r /usr/src/web/requirements.txt

ENV RABBIT_MQ_STR_CONN=amqp://main_web:passwd_web@rabbit:5672/
ENV EXCHANGER=topic_logs
ENV ROUTING_KEY_LISTING=crypto_currency_ms_listing
ENV ERROR_QUEUE=crypto_currency_ms_err
ENV QUEUE_SERVICE_CRYPTO_QUOTES=crypto_currency_ms

ENV PORT=8080
EXPOSE $PORT

COPY nginx.conf /etc/nginx/nginx.conf
RUN mkdir -p /run/nginx

COPY supervisord.conf /etc/supervisord.conf
CMD sed -i -e 's/$PORT/'"$PORT"'/g' /etc/nginx/nginx.conf && /usr/bin/supervisord -c /etc/supervisord.conf
