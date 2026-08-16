run-envoy:
	docker run --network=host -it -v .:/host docker.io/envoyproxy/envoy:v1.39.0 bash

run-controlplane:
	uv run python main.py
