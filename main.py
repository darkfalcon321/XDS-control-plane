import json
import uvicorn
import  threading
import time

from pathlib import Path
from fastapi import FastAPI, Request, Response, Header

app = FastAPI()
DATA = {}
VERSION = 0

def cluster(name:str, addr: str, port: int):
    return {
        "@type": "types.googleapis.com/envoy.config.cluster.v3.Cluster", 
        "name": name, 
        "type": "STATIC",
        "connection_timeout": "5s",
        "load_assignment": {
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
    }


CLUSTERS = [
    cluster("example", "127.0.0.1", 8050)
]

def clusters(services):
    ret = []
    for service in services:
        if service["type"] != "service":
            continue
        backend = service["backend"]
        ret.append(
            cluster(service["name"] + "-cluster", backend["addr"], backend["port"])
        )
    return ret



def route_config(services):
    virtual_hosts = []
    for service in services:
        if service["type"] != "service":
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
    return {
        "@type": "type.googleapis.com/envoy.config.route.v3.RouteConfiguration",
        "name": "backends",
        "virtual_hosts": virtual_hosts
    }

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


def fetch_loop():
    global DATA
    global VERSION
    while True:
        try:
            new_data = fetch_external_data()
            if new_data == DATA:
                continue
            else:
                DATA = new_data
                VERSION += 1
                print(f"New data detected, version:{VERSION}")
        except Exception:
            continue
        time.sleep(3)


def fetch_external_data():
    return json.loads(Path("data.json").read_text())


@app.get("/greeting")
def greet(name: str = "World"):
    return f"Hello, {name}! "


@app.post("/v3/discovery:{resource_type}")
async def resources(request: Request, resource_type: str, host = Header()):
    request_json = await request.json()
    client_version = request_json.get("version_info", "unset")

    resource_mapping = {
        "clusters": clusters(DATA),
        "routes": route_config(DATA),
        "listeners": [
            listener(resource["name"], resource["port"], resource["route_config"], host)
            for resource in DATA
            if resource["type"] == "listener"
        ],
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
    uvicorn.run(app, port=8050)