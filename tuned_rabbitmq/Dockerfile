FROM rabbitmq:alpine

RUN rabbitmq-plugins enable --offline rabbitmq_management
RUN apk add curl

ADD rabbitmq.config /etc/rabbitmq/
ADD definitions.json /etc/rabbitmq/
RUN chown rabbitmq:rabbitmq /etc/rabbitmq/rabbitmq.config /etc/rabbitmq/definitions.json

EXPOSE 5672 15672 15671

CMD ["rabbitmq-server"]

