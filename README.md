# Mobility-on-Demand scenario generation for real-world cities
This repository contains a set of tools to generate Mobility-on-Demand (MoD) scenarios for real-world cities. We provide a set of scripts to generate city-specific map, trip, and demand data, as well as a set of tools to visualize the generated scenarios. The generated scenarios can be used to evaluate different MoD algorithms and policies in a realistic setting. We also provide a list of available public trip datasets that can be used to generate scenarios for different cities.

## Prerequisites
To run the scripts in this repository, you need to install some python packages. To install all required dependencies, run
```bash
pip install -r requirements.txt
```

## Contents
- `network_generator.py`: This script generates the road network map, including nodes, edges, travel time, and predessor matrix for a given city/region.
- `scenario_nyc_tlc_manhattan.py`: This script generates the map and trip data for Manhattan, New York City using the NYC TLC dataset.

## Network generation
The `network_generator.py` script generates the road network map for a given city/region using OpenStreetMap. The city/region can be specified by a center coordination with square radius or a provided region shapefile. The script accepts the following arguments:
```bash
--generate_veh        either generate vehicle data or not (default: 1)
--vehicle             number of vehicles to generate (default: 2000)
--capacity            vehicle capacity (default: 4)
--scenario_shapefile  shapefile that defines the region to be generated if any
--center              city center coordinates (lat, lon) in string format
--radius              radius of the city center in meters. Not necessary if shapefile is provided
--directory           directory to save the generated data files
```
1. To generate the road network map for Chicago with a radius of 5000 meters wihout vehicle file, run the following command:
```bash
python network_generator.py --center "41.8781, -87.6298" --radius 5000 --directory ./data_chicago
```
This will generate the road network map and save it in the `./data_chicago` directory. The generated files include:
- `map/nodes.csv`: A CSV file containing the node data, including node ID, latitude, and longitude.
- `map/edges.csv`: A CSV file containing the edge data, including edge start node ID, end node ID, and travel time.
- `map/times.csv`: A CSV file containing the travel time matrix between nodes.
- `map/times.npy`: An NPY version of the travel time matrix for faster loading.
- `map/pred.csv`: A CSV file containing the predecessor matrix.
- `map/pred.npy`: An NPY version of the predecessor matrix for faster loading.

***Important note:*** The generated node and edge files follow one-based indexing, while the travel time and predecessor matrices follow zero-based indexing. This is important to keep in mind when using the generated files in your own code.

2. To generate the road network map for Chicago with a radius of 5000 meters and vehicle data, run the following command:
```bash
python network_generator.py --center "41.8781, -87.6298" --radius 5000 --directory ./data_chicago --generate_veh 1
```
This will generate the road network map and vehicle data and save it in the `./data_chicago` directory. The generated files include the same files as above, plus:
- `vehicles.csv`: A CSV file containing the vehicle data, including vehicle ID, latitude, longitude, start_time, and capacity. Start time is set to 00:00:00 for all vehicles. The vehicle data is generated randomly within the point set of on the generated map.

3. To generate the road network map for Chicago with a shapefile, run the following command:
```bash
python network_generator.py --scenario_shapefile {shapefile_directory} --directory ./data_chicago
```
This will generate the road network map and save it in the `./data_chicago` directory. The generated files include the same files as above, but the generated map will be limited to the area defined by the shapefile.

## Scenario generation - Manhattan, NYC
The most widely used and well-maintained dataset for MoD is the NYC TLC dataset. The `scenario_nyc_tlc_manhattan.py` script generates the map and trip data for Manhattan, New York City using the NYC TLC dataset. 

### Preparation
To run the script, you need to dowonload the NYC TLC dataset and zone shapefile from this [link](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Follow the following steps to download necessary files:
- Navigate to the year and month of the dataset you want to use, and download the `High Volume For-Hire Vehicle Trip Records` dataset. The metadata for this dataset can be found [here](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf).
- Navigate to the `Taxi Zone Maps and Lookup Tables` section and download the `Taxi zone Shapefile` and `Taxi Zone Lookup Table`. Unzip the taxi zone shaapefile and place the taxi zone lookup table in the same directory as the shapefile. The shapefile should contain the following files: `.cpg`, `.dbf`, `.prj`, `.shp`, and `.shx`.

**Note**: The script is designed to generate scenarios for Manhattan, but it is ready to be used to generate scenarios for other regions in New York City. To do this, you need to change the `zone_id` variable in the script to the desired zone ID. The zone IDs for different regions can be found in the `Taxi Zone Lookup Table` file.

### Usage
Depending on the needs, the script provides the option of generating the scenario on different network granularity: zone-based and arc-based. The script accepts the following arguments:
```bash
--generate_veh        either generate vehicle data or not (default: 1)
--vehicle             number of vehicles to generate (default: 2000)
--capacity            vehicle capacity (default: 4)
--data_path           path to the NYC TLC trip dataset
--zone_path           path to the NYC TLC zone shapefile and lookup file directory
--date                date of the trip to generate in YYYY-MM-DD format
--directory           directory to save the generated data files
--granularity         generated network granularity: 'arc' or 'zone' (default: 'arc')
```
1. To generate the scenario for Manhattan with arc-based granularity, run the following command:
```bash
python scenario_nyc_tlc_manhattan.py --data_path {data_path} --zone_path {zone_path} --date {date} --directory ./data_manhattan_arc
```
This will generate the scenario and save it in the `./data_manhattan_arc` directory. The generated files include map files as described above, plus:
- `request/requests.csv`: A CSV file containing the trip data, including origin node ID, origin node longitude, origin node latitude, destination node ID, destination node longitude, destination node latitude, and request time.

***Important note:*** Similar to [Network generation](#network-generation), the generated node, edge, and request files follow one-based indexing, while the travel time and predecessor matrices follow zero-based indexing. This is important to keep in mind when using the generated files in your own code.

2. To generate the scenario for Manhattan with zone-based granularity, run the following command:
```bash
python scenario_nyc_tlc_manhattan.py --data_path {data_path} --zone_path {zone_path} --date {date} --directory ./data_manhattan_zone --granularity zone
```
This will generate the scenario and save it in the `./data_manhattan_zone` directory. The generated files include:
- `map/nodes.csv`: A CSV file containing the node data, including zone ID, zone centroid latitude, and zone centroid longitude. The node IDs are the zone IDs.
- `map/times.pickle`: A pickle file containing the travel time dictionary between zones. The dictionary keys are the zone ID pairs and the values are the travel times between zones. The travel time are calculated using the shortest road network path between the centroids of the zones.
- `request/requests.csv`: A CSV file containing the trip data, including origin zone ID, destination zone ID, and request time.
- `vehicle/vehicles.csv`: A CSV file containing the vehicle data, including vehicle ID, zone ID, start_time, and capacity. Start time is set to 00:00:00 for all vehicles. The vehicle data is generated randomly within the region set of on the generated map.

## Public trip datasets
The following is a non-exhaustive list of the most up-to-date public ride-hailing trip datasets that can be used to generate realistic scenarios for different cities:
- [NYC TLC dataset](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page): The most widely used and well-maintained dataset for MoD. It contains trip records for yellow taxis, green taxis, and for-hire vehicles in New York City. The origin and destination for the trips are aggregated to the taxi zone level.
- [Chicago Taxi dataset](https://data.cityofchicago.org/Transportation/Taxi-Trips/wrvz-psew): A dataset containing trip records for taxis in Chicago from 2013-2023. The origin and destination for the trips are aggregated to the census tract level, and trip start and end times are rounded to the nearest 15 minutes. The census tract file can be downloaded from the [Chicago Data Portal](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Census-Tracts-2010/5jrd-6zik).
- [Chicago rideshare dataset](https://data.cityofchicago.org/Transportation/Transportation-Network-Providers-Trips-2023-2024-/n26f-ihde/about_data): A dataset containing trip records for rideshare companies in Chicago from 2023. Data in the same format as the Chicago taxi dataset.
- [Washington DC taxi dataset](https://opendata.dc.gov/search?q=taxi%20trips): Datasets containing trip records for taxis in Washington DC from 2016. The trip start and end times are rounded to the nearest 1 hour.
- [Boston rideshare dataset](https://www.kaggle.com/datasets/brllrb/uber-and-lyft-dataset-boston-ma): A dataset containing trip records for ride-hailing trips for 17 days in November and December, 2018 in Boston. The origin and destination are in one of the 12 important locations in Boston.

**Note**: There are other datasets avaiable, but they are either out dated, not actively  maintained, or difficult to customize outside the scope of a particular simulator. This list is under active development and will be updated as new datasets become available.

## Acknowledgements
Some parts of the code have been adapted from [scripts-for-simulator](https://github.com/DMadhuranga/scripts-for-simulator/tree/master). We thank the original authors for their work.