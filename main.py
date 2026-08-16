import json
import uvicorn
import  threading
import time
import socket

from pathlib import Path
from fastapi import FastAPI, Request, Response, Header

app = FastAPI()
DATA = {}
VERSION = 0

def cluster(name:str):
    return {
        "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster", 
        "name": name, 
        "type": "EDS",
        "eds_cluster_config": {
            "eds_config": {
                "api_config_source": {
                    "api_type": "REST",
                    "transport_api_version": "V3",
                    "cluster_names": ["controlplane"],
                    "refresh_delay": "5s"
                }
            }
        }
    }


def endpoint(name:str, addr: str, port: int):
    return {
        "@type": "type.googleapis.com/envoy.config.endpoint.v3.ClusterLoadAssignment", 
        "cluster_name": name, 
        "endpoints": [
            {
                "lb_endpoints": [
                    {
                        "endpoint": {
                            "address": {
                                "socket_address": {
                                    "address": addr,
                                    "port_value": port,
                                }
                            }
                        }
                    }
                ]
            }
        ]
    }


def clusters(services):
    ret = []
    for service in services:
        if service.get("type") != "service":
            continue
        backend = service["backend"]
        ret.append(
            cluster(service["name"] + "-cluster") 
        )
    return ret


def endpoints(services, resource_names=None):
    ret = []
    for service in services:
        if service.get("type") != "service":
            continue

        backend = service["backend"]
        cluster_name = service["name"] + "-cluster"

        if resource_names and cluster_name not in resource_names:
            continue
        
        ret.append(
            endpoint(service["name"] + "-cluster", backend["addr"], backend["port"])
        )
    return ret


def route_config(services):
    virtual_hosts = []
    for service in services:
        if service.get("type") != "service":
            continue
        routes = []
        for index, route in enumerate(service["routes"]):
            routes.append(
                {
                    "name": f"route-{index}",
                    "match": route["match"],
                    "route": {"cluster": service["name"] + "-cluster"}
                }
            )
        virtual_hosts.append(
            {
                "name": service["name"],
                "domains": service["domains"],
                "routes": routes,
            }
        )
    return [
        {
        "@type": "type.googleapis.com/envoy.config.route.v3.RouteConfiguration",
        "name": "backends",
        "virtual_hosts": virtual_hosts
        }
    ]


def listener(name: str, port: int, route_config_name: str, controlplane: str):
    return {
        "@type": "type.googleapis.com/envoy.config.listener.v3.Listener",
        "name": name,
        "address": {"socket_address": {"address": "0.0.0.0","port_value":port}},
        "filter_chains": [
            {
                "filters": [        # [FILTER] robust to downstream (clients) data but not upstream (you)
                    {
                        "name": "http traffic",
                        "typed_config": {       
                            "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
                            "stat_prefix": "backends",
                            "access_log": [
                                {
                                    "name": "envoy.access.stdout",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog",
                                        "log_format": {
                                            "text_format_source": {
                                                "inline_string": "[%START_TIME%] \"%REQ(:METHOD)% %REQ(X-ENVOY-ORIGINAL-PATH?:PATH)% %PROTOCOL%\" %RESPONSE_CODE% %RESPONSE_FLAGS% upstream:%UPSTREAM_HOST% cluster:%UPSTREAM_CLUSTER%\n"
                                            }
                                        }
                                    }
                                }
                            ],
                            "http_filters": [
                                {
                                    "name": "routing", 
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
                                    }
                                }
                            ],
                            "rds": {
                                "route_config_name": route_config_name,
                                "config_source": {
                                    "api_config_source": {
                                        "api_type": "REST",
                                        "cluster_names": [controlplane],
                                        "refresh_delay": "5s"
                                    },
                                }
                            }
                        },
                    }
                ]
            }
        ]
    }


def resolve_addr(addr: str) -> str:
    try:
        return socket.gethostbyname(addr)
    except socket.gaierror:
        return addr


def fetch_loop():   # Data File Version Control 
    global DATA
    global VERSION
    while True:
        try:
            new_data = fetch_external_data()
            for service in new_data:
                if service.get("type") == "service":
                    service["backend"]["addr"] = resolve_addr(service["backend"]["addr"])
            if new_data == DATA:
                continue
            else:
                DATA = new_data
                VERSION += 1
                print(f"New data detected, version:{VERSION}")

        except Exception as e:
            print(f"fetch_loop error: {e}")
            continue

        finally:
            time.sleep(3)


def fetch_external_data():      # Instruction file on how to respond to requests by envoy
    return json.loads(Path("data.json").read_text())            


@app.get("/greeting")           # For testing the connection (else, useless)
def greet(name: str = "World") -> str:
    return f"Hello, {name}! "


@app.post("/v3/discovery:{resource_type}")
async def resources(request: Request, resource_type: str, host = Header()):
    request_json = await request.json()
    client_version = request_json.get("version_info", "unset")
    resource_names = request_json.get("resource_names", [])

    resource_mapping = {
        "clusters": clusters(DATA),
        "routes": route_config(DATA),
        "listeners": [
            listener(resource["name"], resource["port"], resource["route_config"], host)
            for resource in DATA
            if resource["type"] == "listener"
        ],
        "endpoints": endpoints(DATA, resource_names)
    }

    try:
        resources = resource_mapping[resource_type]
    except KeyError:
        return Response(
            "Unsupported resource type", media_type="text/plain", status_code=400
        )
    
    if str(VERSION) == client_version:
        return Response("", status_code=304)
    return {"version_info": str(VERSION), "resources": resources}


if __name__ == "__main__":
    fetcher = threading.Thread(target=fetch_loop).start()
    uvicorn.run(app, host="0.0.0.0", port=8050)