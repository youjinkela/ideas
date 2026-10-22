FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 IDEA_ECHO_DATA=/data
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY server /app/server
RUN pip install --no-cache-dir --no-deps /app/server && useradd --uid 10001 --create-home app
USER 10001:10001
EXPOSE 8000
CMD ["python","-m","uvicorn","idea_echo.app:create_app","--factory","--host","0.0.0.0","--port","8000","--workers","1","--no-access-log"]
