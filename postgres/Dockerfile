FROM postgres:latest

ENV POSTGRES_USER=james
ENV POSTGRES_PASSWORD=1234
ENV POSTGRES_DB=nba_db

EXPOSE 5432

ENTRYPOINT ["docker-entrypoint.sh"]

CMD ["postgres"]