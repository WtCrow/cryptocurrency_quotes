FROM rabbitmq:alpine

RUN rabbitmq-plugins enable --offline rabbitmq_management
RUN apk add curl 

ADD rabbitmq.config /etc/rabbitmq/
ADD definitions.json /etc/rabbitmq/
RUN chown rabbitmq:rabbitmq /etc/rabbitmq/rabbitmq.config /etc/rabbitmq/definitions.json

EXPOSE 4369 5671 5672 25672 15671 15672

CMD ["rabbitmq-server"]
