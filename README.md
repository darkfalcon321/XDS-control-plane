# XDS-control-plane

## How to start
Have 2 terminals, one is the envoy sending request and the other is the control plane receiving and replying. 

For the envoy, run the `make run-envoy` command. In the docker container, change directory to /host. Start the envoy with `envoy -c envoy.yaml` command.

For the control plane, simply run the command `make run-controlplane` or `uv run python main.py`

### Creation Logs
- Created a mock control plane exposing a REST endpoint `/v3/discovery:{resource_type}` that receives Envoy's discovery requests and returns cluster, listener, and route resource definitions based on the requested type.

- The Envoy bootstrap structure is defined in `envoy.yaml`, with cds_config and lds_config instructing Envoy to dynamically fetch clusters and listeners from the control plane via REST.

- cluster() — builds a cluster definition served by the control plane for a given backend
- listener() — defines a listener (port 8082) with an HTTP Connection Manager filter to accept client traffic

- Added rds (Route Discovery Service) to the listener config, so routing changes don't require the listener itself to be reloaded/drained

- Added versioning — a background thread polls data.json, and increments a version counter only when the data actually changes. The control plane compares Envoy's submitted version against its own: returns 304 (Not Modified) if unchanged, 200 with the new resources and version if changed, and 400 if an unsupported resource type is requested
