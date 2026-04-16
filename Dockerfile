FROM python:3.11-slim

WORKDIR /app

RUN adduser --disabled-password --gecos "" wheelbarrow

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R wheelbarrow:wheelbarrow /app
USER wheelbarrow

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
