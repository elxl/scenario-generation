import argparse
import pickle
import random
import datetime
import pandas as pd
import geopandas as gpd
import osmnx as ox
import networkx as nx
from network_generator import create_directory, osmnx_routing_graph, generateMap, generateVehicles


def get_trip_node(merged_nodes, row):
    """Sample a node from the origin and destination zones."""
    pickup_id = row['PULocationID']
    dropoff_id = row['DOLocationID']
    pickup_node = merged_nodes[merged_nodes['LocationID'] == pickup_id].sample(1)[['node_id','lat','lon']].iloc[0]
    dropoff_node = merged_nodes[merged_nodes['LocationID'] == dropoff_id].sample(1)[['node_id','lat','lon']].iloc[0]

    return {
        'origin_node'     : pickup_node['node_id'],
        'origin_lat' : pickup_node['lat'],
        'origin_lon' : pickup_node['lon'],
        'destination_node': dropoff_node['node_id'],
        'dest_lat'   : dropoff_node['lat'],
        'dest_lon'   : dropoff_node['lon']
    }

def process_trip_arc(data_path, zone_path, date, directory, generate_veh, vehicle_num, vehicle_capacity):
    """Process trip data and generate map network for arc-based granularity."""
    
    # Read the taxi zone data and get the Manhattan zone
    taxi_zones = gpd.read_file(zone_path+"/taxi_zones.shp")
    lookup = pd.read_csv(zone_path+"/taxi_zone_lookup.csv")
    manhattan_id = lookup[lookup['Borough'] == 'Manhattan']['LocationID'].values
    manhattan_zone = taxi_zones[taxi_zones['LocationID'].isin(manhattan_id)]

    # Generate Manhattan map    
    if manhattan_zone.crs != "EPSG:4326":
        manhattan_zone = manhattan_zone.to_crs("EPSG:4326")
    geometry = manhattan_zone.union_all()
    G = ox.graph_from_polygon(geometry, network_type="drive")
    G, nodes, edges = osmnx_routing_graph(G)
    generateMap(G, nodes, edges, directory)

    # Get geometry of the nodes in map
    nodes = nodes[['node_id', 'lat', 'lon']]
    gdf_nodes = gpd.GeoDataFrame(nodes, geometry=gpd.points_from_xy(nodes.lon, nodes.lat), crs="EPSG:4326")
    merged_nodes = gpd.sjoin(gdf_nodes, manhattan_zone[['LocationID','geometry']], how="left", predicate="within")
    merged_nodes = merged_nodes[['node_id','lat','lon','LocationID']]

    # Process the trip data within Manhattan area of the specified date
    trips = pd.read_parquet(data_path)
    trips = trips[['request_datetime','PULocationID',"DOLocationID"]]
    trips = trips[(trips['PULocationID'].isin(merged_nodes['LocationID'])) & (trips['DOLocationID'].isin(merged_nodes['LocationID']))]
    trips['date'] = pd.to_datetime(trips['request_datetime']).dt.date.astype(str)
    trips['request_time'] = pd.to_datetime(trips['request_datetime']).dt.time.astype(str)
    trips_day = trips[trips['date'] == date]

    # Sample a node from the origin and destination zones
    trips_day_nodes = trips_day.apply(lambda row: get_trip_node(merged_nodes, row), axis=1, result_type='expand')
    trips_day_nodes['origin_node'] = trips_day_nodes['origin_node'].astype(int)
    trips_day_nodes['destination_node'] = trips_day_nodes['destination_node'].astype(int)
    trips_day_nodes = pd.concat([trips_day,trips_day_nodes], axis=1)

    # Rename and reorder columns
    trips = trips_day_nodes[['origin_node','origin_lon','origin_lat', 'destination_node','dest_lon','dest_lat','request_time']].reset_index(drop=True)
    
    request_directory = directory + "requests/"
    create_directory(request_directory)
    trips.to_csv(request_directory + 'requests.csv', index=False)
    print(f"Trip data processed and saved to {request_directory}requests.csv")

    # Generate vehicles
    if generate_veh:
        generateVehicles(nodes,vehicle_num,vehicle_capacity,directory)
        print(f"Vehicles generated and saved to {directory}vehicles/vehicles.csv")

def process_trip_zone(data_path, zone_path, date, directory, generate_veh, vehicle_num, vehicle_capacity):
    """Process trip data and generate map network for zone-based granularity."""

    # Get Manhattan zone
    taxi_zones = gpd.read_file(zone_path+"/taxi_zones.shp")
    lookup = pd.read_csv(zone_path+"/taxi_zone_lookup.csv")
    manhattan_id = lookup[lookup['Borough'] == 'Manhattan']['LocationID'].values
    manhattan_zone = taxi_zones[taxi_zones['LocationID'].isin(manhattan_id)]
    if manhattan_zone.crs != "EPSG:4326":
        manhattan_zone = manhattan_zone.to_crs("EPSG:4326")

    # Get centroid
    projected = manhattan_zone.to_crs(epsg=2263)
    projected["centroid"] = projected.geometry.centroid
    projected = projected.set_geometry("centroid")
    projected = projected.to_crs(epsg=4326)
    manhattan_zone['centroid'] = projected.geometry

    geometry = manhattan_zone.union_all()
    G = ox.graph_from_polygon(geometry, network_type="drive")
    centroids = manhattan_zone['centroid'].to_list()
    ids = manhattan_zone['LocationID'].to_list()
    centroid_nodes = ox.distance.nearest_nodes(G, X=[c.x for c in centroids], Y=[c.y for c in centroids])

    # Format zone centroid nodes
    lats = [G.nodes[c].y for c in centroid_nodes]
    lons = [G.nodes[c].x for c in centroid_nodes]
    zones = pd.DataFrame({'zone': ids, 'centroid_lat': lats, 'centroid_lon': lons})

    # Compute pairewise drive time using Dijkstra
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    drive_time_dict = dict()
    for i, node1 in zip(ids, centroid_nodes):
        for j, node2 in zip(ids, centroid_nodes):
            if i == j:
                drive_time_dict[(i,j)] = 0
            else:
                try:
                    t = nx.shortest_path_length(G,
                                                source=node1,
                                                target=node2,
                                                weight="travel_time")
                    drive_time_dict[(i, j)] = round(t / 60,2)  # convert to minutes
                except nx.NetworkXNoPath:
                    continue  # no route
    map_directory = directory + "map/"
    create_directory(map_directory)
    zones.to_csv(map_directory + 'nodes.csv', index=False)
    with open(map_directory + 'times.pickle', 'wb') as f:
        pickle.dump(drive_time_dict, f)
    print(f"Map saved to {map_directory}")

    # Process the trip data within Manhattan area of the specified date
    trips = pd.read_parquet(data_path)
    trips = trips[['request_datetime','PULocationID',"DOLocationID"]]
    trips['date'] = pd.to_datetime(trips['request_datetime']).dt.date.astype(str)
    trips['request_time'] = pd.to_datetime(trips['request_datetime']).dt.time.astype(str)
    trips = trips[trips['date'] == date]
    trips.rename(columns={'PULocationID': 'origin_zone', 'DOLocationID': 'destination_zone'}, inplace=True)
    trips = trips[['origin_zone', 'destination_zone', 'request_time']].reset_index(drop=True)

    request_directory = directory + "requests/"
    create_directory(request_directory)
    trips.to_csv(request_directory + 'requests.csv', index=False)
    print(f"Trip data processed and saved to {request_directory}requests.csv")

    # Generate vehicles
    if generate_veh:
        zones = manhattan_zone[['LocationID']]
        vehicles = pd.DataFrame()
        # randomly generate starting points 
        start_node = random.sample(zones.to_list(), vehicle_num)

        vehicles['zone'] = start_node
        vehicles['id'] = list(range(1, vehicle_num+1))
        vehicles['start_time'] = datetime.time(0,0,0)
        vehicles['capacity'] = vehicle_capacity

        # formatting
        vehicles = vehicles[['id', 'zone', 'start_time', 'capacity']]
        vehicle_directory = directory + "vehicles/"
        create_directory(vehicle_directory)
        vehicles.to_csv(vehicle_directory+'vehicles.csv',index=False)
        print(f"Vehicles generated and saved to {vehicle_directory}vehicles.csv")

def generate_manhattan(data_path, zone_path, date, directory, granularity, generate_veh, vehicle_num, vehicle_capacity):

    create_directory(directory)
    
    # Process the trip data
    if granularity == 'arc':
        process_trip_arc(data_path, zone_path, date, directory, generate_veh, vehicle_num, vehicle_capacity)
    elif granularity == 'zone':
        process_trip_zone(data_path, zone_path, date, directory, generate_veh, vehicle_num, vehicle_capacity)
    else:
        raise ValueError("Invalid granularity. Choose 'arc' or 'zone'.")
   

if __name__ == "__main__":
    random.seed(42)

    parser = argparse.ArgumentParser(description='Process trip data for NYC TLC dataset.')
    parser.add_argument("--generate_veh",
                        type=int,
                        default=1,
                        help="Generate vehicles.")
    parser.add_argument("--vehicle",
                        type=int,
                        default=2000,
                        help="Number of vehicles to generate.")
    parser.add_argument("--capacity",
                        type=int,
                        default=4,
                        help="Capacity of each vehicle.")
    parser.add_argument("--data_path",
                        type=str,
                        default="./fhvhv_tripdata_2024-05.parquet",
                        help="Path to the original dataset.")
    parser.add_argument("--zone_path",
                        type=str,
                        default="./taxi_zones",
                        help="Path to the zone files.")
    parser.add_argument("--date",
                        type=str,
                        default="2024-05-15",
                        help="Date to process the data.")
    parser.add_argument("--directory",
                        type=str,
                        default="data/",
                        help="Directory to save the processed data.")
    parser.add_argument("--granularity",
                        type=str,
                        default="arc",
                        help="Granularity of the network. Options: 'arc', 'zone'.")

    args = parser.parse_args()
    # Set the parameters from command line arguments
    vehicle_num = args.vehicle
    vehicle_capacity = args.capacity
    generate_veh = args.generate_veh
    data_path = args.data_path
    zone_path = args.zone_path
    date = args.date
    directory = args.directory
    granularity = args.granularity

    generate_manhattan(data_path, zone_path, date, directory, granularity, generate_veh, vehicle_num, vehicle_capacity)