FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0
ENV PORT=5050
ENV OPEN_ALL_PHASES_BY_DEFAULT=1

EXPOSE 5050

CMD ["python", "-m", "skillsync_ai.app"]
