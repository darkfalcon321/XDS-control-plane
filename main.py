import uvicorn

from fastapi import FastAPI, Request, Response

app = FastAPI()

def cluster(name:str, addr: str, port: int):
    return {
        "@type": "types.googleapis.com/envoy.config.cluster.v3.Cluster", 
        "name": name, 
        "type": "STATIC",
        "load_assignment": {
            "cluster_name": name,
            "endpoints": [
                {"lb_endpoints": [
                    {"endpoint": {
                        "address": {
                            "socket_address": {
                                "address": addr,
                                "port_value": port,
                            }
                        }
                    }}
                ]}
            ]
        }
    }


CLUSTERS = [
    cluster("example", "127.0.0.1", 8050)
]

LISTENER = {
    "@type": "type.googleapis.com/envoy.config.listener.v3.Listener",
    "name": "example",
    "address": {
        "socket_address":{
            "address": "127.0.0.1",
            "port_value":8080
        }
    },
    "filter_chains": [
        {
            "filters": [        # [FILTER] robust to downstream (clients) data but not upstream (you)
                {
                    "name": "http traffic",
                    "typed_config": {       
                        "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
                        "stat_prefix": "backends",
                        "route_config": {
                            "name": "routes",
                            "virtual_hosts": [
                                {
                                    "name": "example vh",
                                    "domains": ['*'],
                                    "routes": [
                                        {
                                            "name": "catchall",
                                            "match": {"prefix": "/"},
                                            "route": {"clusters": "example"}
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                }
            ]
        }
    ]
}



@app.get("/greeting")
def greet(name: str):
    return f"Hello, {name}! "


@app.post("/v3/discovery:{resource_type}")
async def clusters(request: Request, resource_type: str):
    # print(await request.json())
    if resource_type == "clusters":
        return {"version_info": "0", "resources": CLUSTERS}
    elif resource_type == "listeners":
        return {"version_info": "0", "resources": LISTENER}
    else:
        return Response(
            "Unsupported resource type", media_type="text/plain", status_code=400
        )


if __name__ == "__main__":
    uvicorn.run(app, port=8050)