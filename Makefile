run-envoy:
	docker run --network=host -it -v .:/host docker.io/envoyproxy/envoy:v1.38.0 bash
