import json
from flask import Flask
from flask import Response
from flask_cors import CORS, cross_origin

import geojson
from geojson import FeatureCollection, Feature, LineString, Point

from flexishuttle import get_traffic_data

import threading, time
import psycopg2

conn = psycopg2.connect(database='flexishuttle', user='postgres', password='postgres')
curs = conn.cursor()


def get_traffic_data():
    bus_routes = []
    curs.execute("SELECT id, ST_AsGeoJSON(geom), ST_AsGeoJSON(current_location) FROM \"Bus\";")
    for row in curs.fetchall():
        feature = Feature(geometry=geojson.loads(row[1]))
        feature['properties'] = {'id':'bus-'+str(row[0])}

        location = Feature(geometry=geojson.loads(row[2]))
        location['properties'] = {'id':'bus-location-'+str(row[0])}

        bus_routes.append(feature)
        bus_routes.append(location)

    request_points = []
    curs.execute("SELECT id, ST_AsGeoJSON(origin), ST_AsGeoJSON(dest) FROM \"Request\";")
    for row in curs.fetchall():
        if row[1] is not None:
            feature_origin = Feature(geometry=geojson.loads(row[1]))
            feature_origin['properties'] = {'id': 'point-origin-'+str(row[0])}
            request_points.append(feature_origin)
        if row[2] is not None:
            feature_dest = Feature(geometry=geojson.loads(row[2]))
            feature_dest['properties'] = {'id': 'point-dest-'+str(row[0])}
            request_points.append(feature_dest)

        

    my_other_feature = Feature(geometry=Point((-80.234,-22.532)))
    my_other_feature['properties'] = {'id':'person'}

    feature_collection = FeatureCollection(bus_routes+request_points)

    return feature_collection

app = Flask(__name__)
app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy   dog'
app.config['CORS_HEADERS'] = 'Content-Type'

cors = CORS(app, resources={r"/flexishuttle": {"origins": "http://localhost:5000"}})

@app.route('/flexishuttle')
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def flexishuttle():
    data = get_traffic_data()
    print(data)
    return Response(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )

def function1():
    print("HEYYY")
    time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=function1).start()
    app.run(host= '0.0.0.0')