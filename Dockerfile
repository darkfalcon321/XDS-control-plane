FROM python:3.12-slim

WORKDIR /controlplane

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen

COPY . .

EXPOSE 8050

CMD ["uv", "run", "python", "main.py"]