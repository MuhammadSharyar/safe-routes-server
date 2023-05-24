from flask import Flask, request
from flask_cors import CORS, cross_origin
import openrouteservice as ors
import folium
import pandas as pd
import pickle
import sklearn
import spacy

app = Flask(__name__)
CORS(app)

client = ors.Client(key="5b3ce3597851110001cf6248d57d3cd626fd436dbe83521a22cd0c20")

with open("svm_news_classifier.pkl", "rb") as f:
    model = pickle.load(f)

nlp = spacy.load("en_core_web_lg")

df = pd.read_csv("coordinated_dataset.csv")


@app.route("/iframe", methods=["POST"])
def iframe():
    request.get_json(force=True)

    if request.json["pickup"] and request.json["dropoff"]:
        m = folium.Map(
            location=[51.4898, -0.0882], tiles="CartoDB dark_matter", zoom_start=11
        )

        coordinates = [request.json["pickup"], request.json["dropoff"]]

        route = client.directions(
            coordinates=coordinates,
            profile="driving-car",
            format="geojson",
            validate=False,
        )

        tooltip = "Click me!"

        folium.Marker(
            [request.json["pickup"][1], request.json["pickup"][0]],
            popup="<i>Mt. Hood Meadows</i>",
            tooltip=tooltip,
        ).add_to(m)

        folium.Marker(
            [request.json["dropoff"][1], request.json["dropoff"][0]],
            popup="<i>Mt. Hood Meadows</i>",
            tooltip=tooltip,
        ).add_to(m)

        coordinates = (
            df["coordinates"]
            .str.replace("(", "")
            .str.replace(")", "")
            .str.split(",", expand=True)
            .astype(float)
        )

        coordinates.rename(columns={0: "lon", 1: "lat"}, inplace=True)

        for index, row in coordinates.iterrows():
            folium.Marker(
                [row["lon"], row["lat"]],
                popup="<i>Mt. Hood Meadows</i>",
                tooltip=tooltip,
                icon=folium.Icon(color="red"),
            ).add_to(m)

        folium.PolyLine(
            locations=[
                list(reversed(coord))
                for coord in route["features"][0]["geometry"]["coordinates"]
            ]
        ).add_to(m)

    else:
        m = folium.Map(
            location=[51.4898, -0.0882], tiles="CartoDB dark_matter", zoom_start=11
        )

    tooltip = "Click me!"

    coordinates = (
        df["coordinates"]
        .str.replace("(", "")
        .str.replace(")", "")
        .str.split(",", expand=True)
        .astype(float)
    )
    coordinates.rename(columns={0: "lon", 1: "lat"}, inplace=True)

    for index, row in coordinates.iterrows():
        folium.Marker(
            [row["lon"], row["lat"]],
            popup="<i>Mt. Hood Meadows</i>",
            tooltip=tooltip,
            icon=folium.Icon(color="red"),
        ).add_to(m)

    m.get_root().width = "100%"
    m.get_root().height = "100%"
    iframe = m.get_root()._repr_html_()

    return iframe


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


if __name__ == "__main__":
    app.run(debug=True)