from flask import Flask, request, jsonify, render_template
import requests
import math

print("Starting Flask app, registering routes")

app = Flask(__name__)

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 3958.8  # Earth radius in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@app.route('/')
def index():
    return render_template('index.html')


# Add a trail detail page route that renders a template with HTML elements needed for JS map
@app.route('/trail/<int:trail_id>')
def trail_detail(trail_id):
    return render_template('trail_detail.html', trail_id=trail_id)

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

# Test route for trail API
@app.route('/api/trail/test')
def trail_test():
    print("Trail test route called")
    return jsonify({"message": "Trail test route works"})

# Trail detail endpoint supporting both ways and relations
@app.route('/api/trail/<int:trail_id>')
def get_trail(trail_id):
    import sys
    print(f"Received request for trail_id={trail_id}")
    sys.stdout.flush()

    query = f"""
[out:json];
(
  way({trail_id});
  relation({trail_id});
);
(._;>;);
out body;
"""
    overpass_url = "http://overpass-api.de/api/interpreter"
    response = requests.post(overpass_url, data=query.encode('utf-8'))
    print("Overpass status code:", response.status_code)
    print("Overpass response text:", response.text[:500])  # print first 500 chars
    sys.stdout.flush()

    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch trail data"}), 500

    try:
        data = response.json()
    except Exception as e:
        print("JSON decode error:", e)
        sys.stdout.flush()
        return jsonify({"error": "Invalid JSON response from Overpass API"}), 500

    import pprint
    print(f"\n==== Trail ID: {trail_id} ====")
    sys.stdout.flush()
    if "elements" in data:
        print("Overpass returned elements:")
        sys.stdout.flush()
        pp = pprint.PrettyPrinter(indent=2)
        pp.pprint(data["elements"])
    else:
        print("No 'elements' key found in Overpass response.")
        sys.stdout.flush()

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

    trail_element = None
    for el in data.get("elements", []):
        if (el["type"] == "way" or el["type"] == "relation") and el["id"] == trail_id:
            trail_element = el
            break

    if not trail_element:
        return jsonify({"error": "Trail not found"}), 404

    tags = trail_element.get("tags", {})
    name = tags.get("name", "")
    surface = tags.get("surface", "")
    length = tags.get("length", "")

    node_ids = []
    if trail_element["type"] == "way":
        node_ids = trail_element.get("nodes", [])
    elif trail_element["type"] == "relation":
        for member in trail_element.get("members", []):
            if member["type"] == "way":
                way_id = member["ref"]
                way_el = next((e for e in data["elements"] if e["type"] == "way" and e["id"] == way_id), None)
                if way_el:
                    node_ids.extend(way_el.get("nodes", []))

    print("Node IDs in trail_element:", node_ids)
    sys.stdout.flush()
    print("Available node keys:", list(nodes.keys()))
    sys.stdout.flush()

    for nid in node_ids:
        if nid in nodes:
            coord = nodes[nid]
            coordinates.append(coord)
            lat_sum += coord["lat"]
            lon_sum += coord["lon"]

    if not coordinates:
        return jsonify({"error": "Trail geometry not found"}), 404

    center = {
        "lat": lat_sum / len(coordinates),
        "lon": lon_sum / len(coordinates)
    }

    length_miles = 0
    for i in range(len(coordinates) - 1):
        length_miles += haversine_distance(
            coordinates[i]["lat"], coordinates[i]["lon"],
            coordinates[i+1]["lat"], coordinates[i+1]["lon"]
        )

    length_miles = round(length_miles, 2)  # round to 2 decimals
    length = f"{length_miles} miles"

    return jsonify({
        "id": trail_id,
        "name": name if name else None,
        "surface": surface if surface else None,
        "length": length if length else None,
        "center": center,
        "coordinates": coordinates
    })


if __name__ == '__main__':
    app.run(debug=True)