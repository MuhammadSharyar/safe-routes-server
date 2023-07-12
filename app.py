from flask import Flask, request
from flask_cors import CORS
import openrouteservice as client
import folium
import pandas as pd
import pickle
import spacy
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import pyproj
from shapely.geometry import Polygon, mapping, MultiPolygon, LineString, Point
from shapely.ops import cascaded_union

cred = credentials.Certificate("saferoutesdb-firebase-adminsdk-z9nor-1ef39f3997.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)
CORS(app)

ors = client.Client(key="5b3ce3597851110001cf6248d57d3cd626fd436dbe83521a22cd0c20")

with open("svm_news_classifier.pkl", "rb") as f:
    model = pickle.load(f)

nlp = spacy.load("en_core_web_lg")

# df = pd.read_csv("coordinated_dataset.csv")

# coordinates = (
#     df["coordinates"]
#     .str.replace("(", "")
#     .str.replace(")", "")
#     .str.split(",", expand=True)
#     .astype(float)
# )

# print(coordinates)

# coordinates.rename(columns={0: "lon", 1: "lat"}, inplace=True)

# for index, row in coordinates.iterrows():
#     db.collection("avoid_coordinates").document().set(
#         {
#             "lon": row["lon"],
#             "lat": row["lat"],
#         }
#     )


docs = db.collection("avoid_coordinates").get()

avoid_coordinates = []
coordinates = []

for doc in docs:
    coord = doc.to_dict()
    avoid_coordinates.append([coord["lon"], coord["lat"]])


@app.route("/classify-news", methods=["POST"])
async def classify_news():
    request.get_json(force=True)
    vector = nlp(request.json["news"]).vector
    prediction = model.predict([vector])
    match prediction:
        case 0:
            resp = "Burglary"
        case 1:
            resp = "Criminal Damage"
        case 2:
            resp = "Drugs"
        case 3:
            resp = "Fraud or Forgery"
        case 4:
            resp = "Other Notifiable Offences"
        case 5:
            resp = "Robbery"
        case 6:
            resp = "Sexual Offences"
        case 7:
            resp = "Theft and Handling"
        case 8:
            resp = "Violence Against the Person"

    return str(resp)


# Function to create buffer around area point geometries and transform it to the needed coordinate system (WGS84)
def CreateBufferPolygon(point_in, resolution=2, radius=20):
    sr_wgs = pyproj.Proj(init="epsg:4326")  # WGS84
    sr_utm = pyproj.Proj(init="epsg:32632")  # UTM32N
    point_in_proj = pyproj.transform(
        sr_wgs, sr_utm, *point_in
    )  # Unpack list to arguments
    point_buffer_proj = Point(point_in_proj).buffer(
        radius, resolution=resolution
    )  # 20 m buffer

    # Iterate over all points in buffer and build polygon
    poly_wgs = []
    for point in point_buffer_proj.exterior.coords:
        poly_wgs.append(
            pyproj.transform(sr_utm, sr_wgs, *point)
        )  # Transform back to WGS84

    return poly_wgs


# Function to request directions with avoided_polygon feature
def CreateRoute(avoided_point_list, coordinates, n=0):
    print("COORDINATES:////")
    print(coordinates)
    route_request = {
        "coordinates": coordinates,
        "format_out": "geojson",
        "profile": "driving-car",
        "preference": "shortest",
        "instructions": False,
        "options": {"avoid_polygons": mapping(MultiPolygon(avoided_point_list))},
    }
    route_directions = ors.directions(**route_request)

    return route_directions


# Function to create buffer around requested route
def CreateBuffer(route_directions):
    line_tup = []
    for line in route_directions["features"][0]["geometry"]["coordinates"]:
        tup_format = tuple(line)
        line_tup.append(tup_format)

    new_linestring = LineString(line_tup)
    dilated_route = new_linestring.buffer(0.001)

    return dilated_route


def style_function(color):  # To style data
    return lambda feature: dict(color=color)


@app.route("/iframe", methods=["POST"])
def iframe():
    request.get_json(force=True)

    m = folium.Map(
        tiles="CartoDB dark_matter", location=([33.6941, 73.0653]), zoom_start=11
    )

    docs = db.collection("avoid_coordinates").get()

    avoid_coordinates = []
    temp_coords = []

    for doc in docs:
        coord = doc.to_dict()
        temp_coords.append([coord["lon"], coord["lat"]])

    # avoid_coordinates = temp_coords[-15:]
    avoid_coordinates = temp_coords

    # print(avoid_coordinates)

    if request.json["pickup"] and request.json["dropoff"]:
        crime_areas = []
        area_geometry = []
        for data in avoid_coordinates:
            folium.Marker([data[0], data[1]], icon=folium.Icon(color="red")).add_to(m)

            crime_area = CreateBufferPolygon(
                [data[1], data[0]], resolution=5, radius=40
            )
            crime_areas.append(crime_area)

            poly = Polygon(crime_area)
            area_geometry.append(poly)

        union_poly = mapping(cascaded_union(area_geometry))
        folium.features.GeoJson(
            data=union_poly,
            name="Crime affected areas",
            style_function=style_function("#ffd699"),
        ).add_to(m)

        coordinates = [
            request.json["pickup"],
            request.json["dropoff"],
        ]  # Central Station and Fire Department
        for coord in coordinates:
            folium.map.Marker(list(reversed(coord))).add_to(m)

        # Regular Route
        avoided_point_list = []
        route_directions = CreateRoute(
            avoided_point_list, coordinates
        )  # Create regular route with still empty avoided_point_list

        folium.features.GeoJson(
            data=route_directions,
            name="Regular Route",
            style_function=style_function("#ff5050"),
            overlay=True,
        ).add_to(m)
        print("Generated regular route.")

        dilated_route = CreateBuffer(route_directions)  # Create buffer around route

        try:
            for site_poly in crime_areas:
                poly = Polygon(site_poly)
                if poly.within(dilated_route):
                    avoided_point_list.append(poly)

                    # Create new route and buffer
                    route_directions = CreateRoute(avoided_point_list, coordinates, 1)
                    dilated_route = CreateBuffer(route_directions)

            folium.features.GeoJson(
                data=route_directions,
                name="Alternative Route",
                style_function=style_function("#006600"),
                overlay=True,
            ).add_to(m)
            print("Generated alternative route, which avoids affected areas.")
        except Exception:
            print(
                "Sorry, there is no route available between the requested destination because of too many blocked streets."
            )

        m.add_child(folium.map.LayerControl())
    else:
        m = folium.Map(
            location=[33.6941, 73.0653], tiles="CartoDB dark_matter", zoom_start=11
        )
        crime_areas = []
        area_geometry = []
        for data in avoid_coordinates:
            folium.Marker([data[0], data[1]], icon=folium.Icon(color="red")).add_to(m)

            crime_area = CreateBufferPolygon(
                [data[1], data[0]], resolution=5, radius=40
            )
            crime_areas.append(crime_area)

            poly = Polygon(crime_area)
            area_geometry.append(poly)

        union_poly = mapping(cascaded_union(area_geometry))
        folium.features.GeoJson(
            data=union_poly,
            name="Crime affected areas",
            style_function=style_function("#ffd699"),
        ).add_to(m)

    m.get_root().width = "100%"
    m.get_root().height = "100%"
    iframe = m.get_root()._repr_html_()

    return iframe


if __name__ == "__main__":
    app.run(port=int("5000"), debug=True)
