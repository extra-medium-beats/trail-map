from flask import Flask, request, jsonify, render_template
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/trails')
def get_osm_trails():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    trail_type = request.args.get('trail_type', 'all')

    if not lat or not lon:
        return jsonify({'error': 'Missing lat/lon'}), 400

    if trail_type == 'nature':
        query = f"""
        [out:json];
        (
          way["leisure"~"park|forest|recreation_ground|nature_reserve"](around:20000,{lat},{lon});
          relation["leisure"~"park|forest|recreation_ground|nature_reserve"](around:20000,{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
    elif trail_type == 'bike':
        query = f"""
        [out:json];
        (
          way["highway"~"path|track|cycleway"]["bicycle"!~"no"](around:20000,{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
    else:
        query = f"""
        [out:json];
        (
          way["highway"~"path|track|cycleway"]["bicycle"!~"no"](around:20000,{lat},{lon});
          way["leisure"~"park|forest|recreation_ground|nature_reserve"](around:20000,{lat},{lon});
          relation["leisure"~"park|forest|recreation_ground|nature_reserve"](around:20000,{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """

    overpass_url = "http://overpass-api.de/api/interpreter"
    response = requests.post(overpass_url, data=query.encode('utf-8'))
    data = response.json()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)


# Trail detail endpoint
@app.route('/api/trail/<int:trail_id>')
def get_trail(trail_id):
    query = f"""
    [out:json];
    way({trail_id});
    (._;>;);
    out body;
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    response = requests.get(overpass_url, params={"data": query})
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch trail data"}), 500

    data = response.json()

    nodes = {}
    coordinates = []
    name = ""
    surface = ""
    length = ""
    lat_sum = 0
    lon_sum = 0

    for el in data.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = {"lat": el["lat"], "lon": el["lon"]}

    for el in data.get("elements", []):
        if el["type"] == "way" and el["id"] == trail_id:
            tags = el.get("tags", {})
            name = tags.get("name", "")
            surface = tags.get("surface", "")
            length = tags.get("length", "")
            node_ids = el.get("nodes", [])
            for nid in node_ids:
                if nid in nodes:
                    coord = nodes[nid]
                    coordinates.append(coord)
                    lat_sum += coord["lat"]
                    lon_sum += coord["lon"]

    if not coordinates:
        return jsonify({"error": "Trail not found or missing geometry"}), 404

    center = {
        "lat": lat_sum / len(coordinates),
        "lon": lon_sum / len(coordinates)
    }

    return jsonify({
        "id": trail_id,
        "name": name,
        "surface": surface,
        "length": length,
        "center": center,
        "coordinates": coordinates
    })