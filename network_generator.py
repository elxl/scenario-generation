import math
import random
import datetime
import argparse
import os
import pandas as pd
import numpy as np
import osmnx as ox
import networkx as nx
import geopandas as gpd

def get_nx_graph(scenario_shapefile, city_center,radius):
    """Create a graph centered at city_center with a radius of radius or from the scenario shapefile."""
    if scenario_shapefile != "None":
        # Create a graph from the regions defined by the shapefile
        shapefile_map = gpd.read_file(scenario_shapefile)
        if shapefile_map.crs != "EPSG:4326":
            shapefile_map = shapefile_map.to_crs("EPSG:4326")
        geometry = shapefile_map.union_all()
        G = ox.graph_from_polygon(geometry,
                                    network_type="drive")
    else:
        # Create a graph from openstreetmap data
        G = ox.graph.graph_from_point(city_center,dist=radius,
                                dist_type = "bbox",
                                network_type='drive',
                                simplify=True,
                                truncate_by_edge=True,
                                retain_all=False)
    
    return G

def osmnx_routing_graph(G):
    """Get nodes and edges data using OSMnx."""

    # remove disconnected components
    G = ox.truncate.largest_component(G, strongly=True)

    # add edge speeds
    G = ox.add_edge_speeds(G)

    # add edge travel time
    G = ox.add_edge_travel_times(G)
    for n1, n2, k in G.edges(keys=True):
        G[n1][n2][k]['travel_time'] = math.ceil(G[n1][n2][k]['travel_time'])

    nodes, edges = ox.graph_to_gdfs(G)

    # format nodes
    nodes['osmid'] = nodes.index
    nodes.index = range(len(nodes))
    nodes['node_id'] = nodes.index
    nodes['lon'] = nodes['x']
    nodes['lat'] = nodes['y']
    nodes = nodes[['node_id', 'osmid', 'lat', 'lon']]
    nodes['node_id'] = nodes['node_id'].astype(int)
    nodes['osmid'] = nodes['osmid'].astype(int)
    nodes['lat'] = nodes['lat'].astype(float)
    nodes['lon'] = nodes['lon'].astype(float)
    nodes['node_id'] = nodes['node_id'].apply(lambda x: x + 1)

    # format edges
    edges = edges.reset_index()
    edges['source_osmid'] = edges['u']
    edges['target_osmid'] = edges['v']
    edges['source_node'] = edges['source_osmid'].apply(lambda x: nodes.loc[nodes['osmid']==x, 'node_id'].values[0])
    edges['target_node'] = edges['target_osmid'].apply(lambda x: nodes.loc[nodes['osmid']==x, 'node_id'].values[0])
    edges = edges.sort_values(by=['travel_time'])
    edges = edges.drop_duplicates(subset=['source_node', 'target_node'])
    edges = edges[['source_osmid', 'target_osmid', 'source_node', 'target_node', 'travel_time']]
    edges['source_osmid'] = edges['source_osmid'].astype(int)
    edges['target_osmid'] = edges['target_osmid'].astype(int)
    edges['source_node'] = edges['source_node'].astype(int)
    edges['target_node'] = edges['target_node'].astype(int)
    edges['travel_time'] = edges['travel_time'].astype(int)
    # format edge types
    print(f"Number of nodes: {len(nodes)}, number of edges: {len(edges)}")
    return G, nodes, edges

def create_directory(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def generateMap(G,nodes,edges,main_directory):
    """Generate the map for the scenario."""

    OUTPUT_DIR = main_directory+"map/"
    create_directory(OUTPUT_DIR)

    node_to_osmid_map = {}
    for _,node in nodes.iterrows():
        node_to_osmid_map[int(node.node_id)] = node.osmid

    osmid_to_node_map = {}
    for _,node in nodes.iterrows():
        osmid_to_node_map[node.osmid] = int(node.node_id)

    with open(OUTPUT_DIR+"pred.csv", 'a+') as pred_file:
        with open(OUTPUT_DIR+"times.csv", 'a+') as times_file:
            for origin in range(1,len(nodes)+1):
                travel_times = []
                predecessors = []
                origin_osmid = node_to_osmid_map[origin]
                pred,travel_time=nx.dijkstra_predecessor_and_distance(G, origin_osmid,weight='travel_time')
                for destination in range(1,len(nodes)+1):
                    destination_osmid = node_to_osmid_map[destination]
                    travel_times.append(int(travel_time[destination_osmid]))
                    if destination == origin:
                        predecessor = origin - 1
                    else:
                        predecessor = osmid_to_node_map[pred[destination_osmid][0]] - 1
                    predecessors.append(predecessor)
                pred_file.write(",".join([str(i) for i in predecessors])+"\n")
                times_file.write(",".join([str(i) for i in travel_times])+"\n")

    def read_matrix(filename,num_lines):
        delimiter = ','
        dtype = np.uint16
        def iter_func():
            with open(filename, 'r') as infile:
                for line in infile:
                    line = line.rstrip().split(delimiter)
                    for item in line:
                        yield dtype(item)

        data = np.fromiter(iter_func(), dtype=dtype)
        data = data.reshape((-1, num_lines))
        return data

    times = read_matrix(OUTPUT_DIR+'times.csv',len(nodes))
    with open(OUTPUT_DIR +"times.npy", 'wb') as f:
        np.save(f, times)

    pred = read_matrix(OUTPUT_DIR+'pred.csv',len(nodes))
    with open(OUTPUT_DIR +"pred.npy", 'wb') as f:
        np.save(f, pred)

    nodes = nodes[['node_id', 'lat', 'lon']]
    nodes.to_csv(OUTPUT_DIR+'nodes.csv', index=False)

    edges['travel_time'] = edges['travel_time'].apply(lambda x: math.ceil(x))
    edges = edges[['source_node', 'target_node', 'travel_time']]
    edges.to_csv(OUTPUT_DIR+'edges.csv', index=False)

    print(f"Map generated under {OUTPUT_DIR}.")

def generateVehicles(nodes,vehicle_num,vehicle_capacity,main_directory):
    """Generate vehicles randomly from the nodes in the graph."""

    nodes = nodes[['node_id', 'lat', 'lon']]
    vehicles = pd.DataFrame()
    # randomly generate starting points 
    start_node = random.sample(nodes.index.to_list(), vehicle_num)

    for n in start_node:
        vehicles = pd.concat([vehicles, nodes.iloc[[n]]], ignore_index=True)

    vehicles.columns = ['node', 'lat', 'lon']
    vehicles['id'] = list(range(1, vehicle_num+1))
    vehicles['start_time'] = datetime.time(0,0,0)
    vehicles['capacity'] = vehicle_capacity

    # formatting
    vehicles['node'] = vehicles['node'].astype('int')
    vehicles = vehicles[['id', 'node', 'lat', 'lon', 'start_time', 'capacity']]
    vehicle_directory = main_directory + "vehicles/"
    create_directory(vehicle_directory)
    vehicles.to_csv(vehicle_directory+'vehicles.csv', index = False)

def generate_scenario(main_directory, scenario_shapefile, city_center, radius, vehicle_num, vehicle_capacity):
    """Main function to generate the scenario map and vehicles."""
    # Create the main directory if it doesn't exist
    create_directory(main_directory)

    # Generate the routing graph
    G = get_nx_graph(scenario_shapefile, city_center,radius)
    G, nodes, edges = osmnx_routing_graph(G)

    # Generate the map
    generateMap(G,nodes,edges,main_directory)
    print("Map generated successfully.")


if __name__ == "__main__":
    random.seed(42)

    parser = argparse.ArgumentParser(description='Generate scenario map.')
    parser.add_argument("--generate_veh",
                        type=int,
                        default=1,
                        help="Generate vehicles.")
    parser.add_argument("--scenario_shapefile",
                        type=str,
                        default="None",
                        help="Scenario shapefile.")
    parser.add_argument("--center",
                        type=str,
                        default="41.881978735974656, -87.6301110441199",
                        help="City center coordinates (lat, lon) in string format.")
    parser.add_argument("--radius",
                        type=int,
                        default=5000,
                        help="Radius in meters.")
    parser.add_argument("--vehicles",
                        type=int,
                        default=2000,
                        help="Number of vehicles to generate.")
    parser.add_argument("--capacity",
                        type=int,
                        default=4,
                        help="Vehicle capacity.")
    parser.add_argument("--directory",
                        type=str,
                        default="data/",
                        help="Main directory to save the generated data.")

    args = parser.parse_args()
    # Set the parameters from command line arguments
    scenario_shapefile = args.scenario_shapefile
    city_center = tuple(map(float, args.center.split(',')))
    radius = args.radius
    vehicle_num = args.vehicles
    vehicle_capacity = args.capacity
    main_directory = args.directory

    generate_scenario(main_directory, scenario_shapefile, city_center, radius, vehicle_num, vehicle_capacity)

# atlanta downtown 33.75508,-84.38869 #15km
# chicago downtown 41.881978735974656, -87.6301110441199 #16km
# boston downtown 42.36018755809968, -71.05892310513804 #12km
# houston downtown 29.74235,-95.37086 #12km
# la downtown 34.04529,-118.24996 #12km #11771