import json
import uvicorn

from fastapi import FastAPI, Request, Response, Header

app = FastAPI()

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


def fetch_external_data():
    with open("data.json") as f:
        data = json.load(f)
        return data


@app.get("/greeting")
def greet(name: str = "World"):
    return f"Hello, {name}! "


@app.post("/v3/discovery:{resource_type}")
async def resouces(request: Request, resource_type: str, host = Header()):
    fake_api_data = fetch_external_data()

    cluster_resources = clusters(fake_api_data)
    route_config_resource = route_config(fake_api_data)
    listener_resources = [
        listener(resource["name"], resource["port"], resource["route_config"], host)
        for resource in fake_api_data
        if resource["type"] == "listener"
    ]


    if resource_type == "clusters":
        return {"version_info": "0", "resources": cluster_resources}
    elif resource_type == "listeners":
        return {"version_info": "0", "resources": listener_resources}
    elif resource_type == "routes":
        return {"version_info": "0", "resources": route_config_resource}
    else:
        return Response(
            "Unsupported resource type", media_type="text/plain", status_code=400
        )


if __name__ == "__main__":
    uvicorn.run(app, port=8050)