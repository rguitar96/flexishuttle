'''
postgresql commands:
--INSERT INTO "Bus" (id, name, geom) VALUES (1, 'LineString', 'LINESTRING(0 0, 1 1, 2 1, 2 2)');
--CREATE TABLE "Request" (origin geometry, dest geometry);
--ALTER TABLE "Request" ADD COLUMN id SERIAL PRIMARY KEY;
--INSERT INTO "Request" (id, origin, dest) VALUES (1, 'POINT(0 0)','POINT(1 0)')
'''
# osmconvert spain-latest.osm -b=-3.38,40.475,-3.34,40.5

# 40.497138, -3.375946      40.498248, -3.347021
# 40.480166, -3.373199      40.484148,-3.340068

# 40.480, 40.498
# -3.373, -3.347

from pyroutelib3 import Router # Import the router
import random, time, math, threading, queue
import psycopg2

import geojson
from geojson import FeatureCollection, Feature, LineString, Point

conn = psycopg2.connect(database='flexishuttle', user='postgres', password='postgres')
curs = conn.cursor()

print("Deleting previous db records.")

curs.execute("DELETE FROM \"Bus\";")
curs.execute("DELETE FROM \"Request\";")
conn.commit()

print("All records were removed\n\n")

router = Router("car", "alcala.osm")

def distance(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371 # km
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c
    return d

def route_distance(route):
    d = 0
    first = route[0]
    for coordinate in route:
        d = d + distance(first,coordinate)
        first = coordinate
    return d

class Bus:
    def __init__(self, lat_spawn, lon_spawn):
        self.location = Point((lat_spawn, lon_spawn))
        self.route = LineString([(lat_spawn, lon_spawn), (lat_spawn, lon_spawn)])
        self.id = -1
        self.request_list = []
        self.point_list = []
        self.router_list = []
        self.start_thread()
    def _bus_thread(self):
        # THIS THREAD MAKES THE BUS MOVE FROM THE FIRST POINT ON THE ROUTE TO THE NEXT ONE
        curs = conn.cursor()
        while True:
            if len(self.route['coordinates']) > 2:
                #print("[Bus ",self.id,"] New route.")
                if (str(self.route['coordinates'][0]) == str(self.route['coordinates'][1])):
                    print("[Bus ",self.id,"] Deleting first repeated element of route")
                    self.route['coordinates'].pop(0)
                else:
                    #print("[Bus ",self.id,"] Going from: "+str(self.route['coordinates'][0]))
                    #print("[Bus ",self.id,"] to:         "+str(self.route['coordinates'][1]))
                    dst = distance(self.route['coordinates'][0],self.route['coordinates'][1])
                    #print("[Bus ",self.id,"] Distance: "+str(dst))
                    diff_lat = self.location['coordinates'][0] - self.route['coordinates'][1][0]
                    diff_lon = self.location['coordinates'][1] - self.route['coordinates'][1][1]
                    #diff_lat = self.route['coordinates'][0][0] - self.route['coordinates'][1][0]
                    #diff_lon = self.route['coordinates'][0][1] - self.route['coordinates'][1][1]

                    velocity = 0.005
                    n_ticks = dst / velocity

                    # TODO: need a new way of moving that is a real constant velocity

                    while(abs(distance(self.route['coordinates'][1], self.location['coordinates'])) > 0.005):
                        #print("New tick")
                        #print("New distance: ")
                        #print(abs(distance(self.route['coordinates'][1], self.location['coordinates'])))
                        self.location['coordinates'][0] = self.location['coordinates'][0] - (diff_lat / n_ticks)
                        self.location['coordinates'][1] = self.location['coordinates'][1] - (diff_lon / n_ticks)

                        # pass by request point
                        flip_location = []
                        flip_location.append(self.location['coordinates'][1])
                        flip_location.append(self.location['coordinates'][0])
                        for req in self.request_list:
                            if req.origin is not None and abs(distance(req.origin['coordinates'], self.location['coordinates'])) < 0.01:
                                # picked up
                                #print("[Bus ",self.id,"] Picking up")
                                self.point_list.remove(req.origin['coordinates'])
                                self.router_list.remove(req.router_start)
                                req.origin = None
                                curs.execute("UPDATE \"Request\" SET origin = NULL WHERE id = "+str(req.id)+";")
                            if req.end is not None and req.origin is None and abs(distance(req.end['coordinates'], self.location['coordinates'])) < 0.01:
                                # dropped off
                                #print("[Bus ",self.id,"] Dropping off")
                                self.request_list.remove(req)
                                self.point_list.remove(req.end['coordinates'])
                                self.router_list.remove(req.router_end)
                                request_list.remove(req)
                                req.end = None
                                curs.execute("UPDATE \"Request\" SET dest = NULL WHERE id = "+str(req.id)+";")

                        query = "UPDATE \"Bus\" SET current_location = (ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(self.location)+"'))))) WHERE id=" + str(self.id)
                        curs.execute(query)
                        conn.commit()
                        time.sleep(0.02)
                    #print("Next Point!")
                    self.location['coordinates'][0] = self.route['coordinates'][1][0]
                    self.location['coordinates'][1] = self.route['coordinates'][1][1]
                    self.route['coordinates'].pop(0)
                    query = "UPDATE \"Bus\" SET current_location = (ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(self.location)+"'))))), geom = (ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(self.route)+"'))))) WHERE id=" + str(self.id)
                    curs.execute(query)
                    conn.commit()
                    time.sleep(0.02)


    def start_thread(self):
        self.bus_thread = threading.Thread(target=self._bus_thread)
        self.bus_thread.daemon = True
        self.bus_thread.start()

class Request:
    def __init__(self, lat_start, lon_start, lat_end, lon_end):
        self.router_start = router.findNode(lat_start, lon_start)
        self.router_end = router.findNode(lat_end, lon_end)
        closest_location = list(map(router.nodeLatLon, [self.router_start, self.router_end]))
        self.origin = Point((closest_location[0][0], closest_location[0][1]))
        self.end = Point((closest_location[1][0], closest_location[1][1]))
        self.id = -1

def generate_random_request():
    # TODO: Check if it is possible to go from origin to end
    curs = conn.cursor()

    lat_start = random.uniform(40.480,40.498)
    lon_start = random.uniform(-3.373,-3.347)
    lat_end = random.uniform(40.480,40.498)
    lon_end = random.uniform(-3.373,-3.347)

    request = Request(lat_start, lon_start, lat_end, lon_end)

    query = "INSERT INTO \"Request\" (origin,dest) VALUES (ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(request.origin)+"')))), ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(request.end)+"'))))) RETURNING id"
    curs.execute(query)
    if curs.rowcount == 0:
        print("Not retrieved results from: ",query)
        conn.rollback()
        return None
    for row in curs.fetchall():
        request.id = row[0]
        conn.commit()
        return request
    return None

def spawn_bus():
    curs = conn.cursor()

    lat_start = random.uniform(40.480,40.498)
    lon_start = random.uniform(-3.373,-3.347)

    bus = Bus(lat_start, lon_start)

    query = "INSERT INTO \"Bus\" (geom, current_location) VALUES (ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(bus.route)+"')))),ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(bus.location)+"'))))) RETURNING id"
    curs.execute(query)
    if curs.rowcount == 0:
        print("Not retrieved results from: ",query)
        conn.rollback()
        return None
    for row in curs.fetchall():
        bus.id = row[0]
        conn.commit()
        return bus

    return None
    
def alter_route(bus):
    curs = conn.cursor()

    print("Altering route of bus ", bus.id, " to points: ", bus.point_list)
    print("Len of router_list: ", len(bus.router_list))

    routeLatLons = []

    #bus_lat = bus.route['coordinates'][-1][0]
    #bus_lon = bus.route['coordinates'][-1][1]
    bus_lat = bus.location['coordinates'][0]
    bus_lon = bus.location['coordinates'][1]
    prev_point = router.findNode(bus_lat, bus_lon)

    for point in bus.router_list:
        status, route = router.doRoute(prev_point, point)
        
        if status == 'success':
            routeLatLons = routeLatLons + list(map(router.nodeLatLon, route))

        prev_point = point
    
    if not routeLatLons:
        return
    bus.location['coordinates'][0] = routeLatLons[0][0]
    bus.location['coordinates'][1] = routeLatLons[0][1]
    bus.route = LineString(routeLatLons + [routeLatLons[-1]])


    query = "UPDATE \"Bus\" SET geom = (ST_FlipCoordinates(ST_GeomFromText(ST_AsText(ST_GeomFromGeoJSON('"+geojson.dumps(bus.route)+"'))))) WHERE id=" + str(bus.id)
    
    curs.execute(query)
    conn.commit()

bus_list = []
request_list = []
global_request_queue = queue.Queue()

MAX_BUSES = 8
MAX_REQUESTS=40

def bus_spawn_thread():
    while (len(bus_list) < MAX_BUSES):
        print("Spawning Bus . . .")
        b = spawn_bus()
        if b is not None: bus_list.append(b)
        #time.sleep(2)

bus_spawn_thread = threading.Thread(target=bus_spawn_thread)
bus_spawn_thread.daemon = True
bus_spawn_thread.start()

time.sleep(1)

#time.sleep(5)

def request_thread():
    while (len(request_list) < MAX_REQUESTS):
        request = generate_random_request()
        if request != None:
            print("Creating new request . . .")
            request_list.append(request)
            global_request_queue.put(request)
        
        time.sleep(random.randint(5,12))

request_thread = threading.Thread(target=request_thread)
request_thread.daemon = True
request_thread.start()

time.sleep(1)

# TODO: instead of distance between points, use doRoute()
def get_point_distances(point_list):
    if not point_list: return 0
    d = 0
    first = point_list[0]
    for coordinate in point_list:
        d = d + distance(first,coordinate)
        first = coordinate
    return d

def optimal_route(bus, request):
    # We have to test every possibility of inserting request.origin and request.end
    # into bus.point_list with request.origin before request.end and compare their distances
    distance = 999999999
    final_point_list = []
    final_router_list = []

    if not bus.point_list:
        final_point_list = [request.origin['coordinates'], request.end['coordinates']]
        final_router_list = [request.router_start, request.router_end]
        distance = get_point_distances([bus.location['coordinates']] + final_point_list)
    else:
        for i in range(len(bus.point_list)):
            for j in range(i+1,len(bus.point_list)):
                point_list_copy = bus.point_list.copy()
                point_list_copy.insert(i, request.origin['coordinates'])
                point_list_copy.insert(j, request.end['coordinates'])

                router_list_copy = bus.router_list.copy()
                router_list_copy.insert(i, request.router_start)
                router_list_copy.insert(j, request.router_end)

                new_distance = get_point_distances([bus.location['coordinates']] + point_list_copy)
                if new_distance < distance:
                    distance = new_distance
                    final_point_list = point_list_copy.copy()
                    final_router_list = router_list_copy.copy()

    print("Optimal distance of bus ", bus.id, " is ", distance)
    return final_point_list, final_router_list, distance

def worker_thread():
    while True:
        request = global_request_queue.get()
        print("Working on new request . . .")
        
        # HERE GOES A MAGIC CHOICE ALGORITHM
        # Right now, the choice is picking the route less affected in distance
        
        lowest_distance = 9999999
        b = bus_list[0]
        pl = []
        rl = []
        for bus in bus_list:
            new_point_list, new_router_list, new_distance = optimal_route(bus, request)
            if (new_distance - get_point_distances(bus.point_list)) < lowest_distance:
                b = bus
                pl = new_point_list
                rl = new_router_list
                lowest_distance = new_distance - get_point_distances(bus.point_list)
        b.request_list.append(request)
        b.point_list = pl
        b.router_list = rl

        print("Request assigned to bus ", b.id)
        alter_route(b)

        global_request_queue.task_done()

worker_thread = threading.Thread(target=worker_thread)
worker_thread.daemon = True
worker_thread.start()

while True:
    time.sleep(1)