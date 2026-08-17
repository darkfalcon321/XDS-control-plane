# XDS-control-plane


## How to start
Run `docker compose up -d`

*To see the logs*
controlplane : `docker compose logs -f controlplane`
envoy: `docker compose logs -f envoy`

*Send request to a backend server*
`curl -v -H "Host: whoami1.local" http://localhost:10000/`

*configuration admin troubleshoot*
`curl localhost:9000/config_dump`


## REST api vs gRPC
Traditionally, envoy is built with gRPC which ensures faster performance and is popular at hyper-scale — Google or Netflix managing 50,000 proxies, REST xDS is fully supported feature of Envoy. With the REST polling at 5-second interval, the application consumes negligible CPU and works fine. 

Since REST API was used over gRPC, the Envoy resources had to be built manually from scratch allowing more autonomy over it (good for first time learners; brutal otherwise), which are all hidden in pre-built library abstraction in gRPC. 

debugging is far easier compared to gRPC. Special Binary tooling (grpcurl) is needed to debug over a simple POST request JSON response that can be done in CLI (or Postman to be fancier).


## Creation Logs
- Created a mock control plane exposing a REST endpoint `/v3/discovery:{resource_type}` that receives Envoy's discovery requests and returns cluster, listener, and route resource definitions based on the requested type.

- The Envoy bootstrap structure is defined in `envoy.yaml`, with cds_config and lds_config instructing Envoy to dynamically fetch clusters and listeners from the control plane via REST.

- cluster() — builds a cluster definition served by the control plane for a given backend
- listener() — defines a listener (port 8082) with an HTTP Connection Manager filter to accept client traffic

- Added rds (Route Discovery Service) to the listener config, so routing changes don't require the listener itself to be reloaded/drained

- Added versioning — a background thread polls data.json, and increments a version counter only when the data actually changes. The control plane compares Envoy's submitted version against its own: returns 304 (Not Modified) if unchanged, 200 with the new resources and version if changed, and 400 if an unsupported resource type is requested

- Made 2 other backend servers for testing

- Moved the controlplane and envoy to README

- Added extra LDS logs for envoy to see access logs
- Added EDS — routes the traffic to the clusters properly.


