# XDS-control-plane

### Creation Logs
Created a mock control plane exposing a REST endpoint. It receives envoy's discovery req and returns cluster resource definitions. 

A cluster definition cluster() that would be served by the control plane

A listener at 8080 for client to connect to along with a http connection manager as the filter. 

