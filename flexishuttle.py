def get_traffic_data():
    data = dict(type='FeatureCollection')

    features = dict(type='Feature', properties={})

    geometry = dict(type='LineString')

    coordinates = [[10.47821044921875, 48.24845457730629], [10.52490234375, 48.039528693690556], [10.923156738281248, 48.15509285476017]]

    geometry['coordinates'] = coordinates

    features['geometry'] = geometry

    data['features'] = [features]

    #geometry = dict()
    #geometry['type'] = "Point"
    #geometry['coordinates'] = [43.62118950136609+(i/100.0), 41.543074784381815]
    #data = dict(geometry=geometry)
    #data['type'] = "Feature"
    #data['properties'] = {}
    return data

# {"geometry": {"type": "Point", "coordinates": [43.62118950136609, 41.543074784381815]}, "type": "Feature", "properties": {}}
# {"geometry": {"type": "Point", "coordinates": [37.80860017472639, 43.64671001256747]}, "type": "Feature", "properties": {}}
# {"geometry": {"type": "Point", "coordinates": [43.62118950136609, 41.543074784381815]}, "type": "Feature", "properties": {}}
