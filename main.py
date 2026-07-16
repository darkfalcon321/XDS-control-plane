import uvicorn

from fastapi import FastAPI, Request

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

@app.get("/greeting")
def greet(name: str):
    return f"Hello, {name}! "


@app.post("/v3/discovery:clusters")
async def clusters(request: Request):
    print(await request.json())
    return {"version_info": "0","resources": CLUSTERS}


if __name__ == "__main__":
    uvicorn.run(app, port=8050)