#!/usr/bin/env python

import collections
import csv
import datetime
import json
import re
import requests
import sys

LISTING_TYPE_RENTAL = "rental"
LISTING_TYPE_SALE = "sale"

CompassListing = collections.namedtuple(
    "CompassListing",
    (
        "permalink",
        "address",
        "neighborhood",
        "latitude",
        "longitude",
        "price_dollars",
        "original_price_dollars",
        "sq_ft",
        "beds",
        "baths",
        "year_opened",
        "building_id",
        "building_units",
        "monthly_sales_charges",
        "monthly_sales_charges_incl_taxes",
        "unit_type",
        "first_listed",
        "parking_spaces",
        "amenities",
    )
)

AUSTIN_LOCATIONS = [
    {"id": 44159,
     "name": "Travis County",
     "seoId": "travis-county-tx",},
]

LONG_ISLAND_LOCATIONS = [
    {"id": 185000,
     "name": "Nassau County",
     "seoId": "nassau-county-ny",},
]

BK_LOCATIONS = [
    {"id": 21531,
     "name": "DUMBO",
     "seoId": "dumbo-brooklyn-ny",},

    # {"id": 162107,
    #  "name": "Northwestern Brooklyn",
    #  "seoId": "northwestern-brooklyn-brooklyn-ny",},    

    {"id": 21432,
     "name": "Columbia Street Waterfront",
     "seoId": "columbia-street-waterfront-brooklyn-ny",},
    
    {"id": 21435,
     "name": "Downtown Brooklyn",
     "seoId": "downtown-brooklyn-brooklyn-ny",},

    {"id": 21446,
     "name": "Cobble Hill",
     "seoId": "cobble-hill-brooklyn-ny",},
    
    # {"id": 161941,
    #  "name": "South Brooklyn",
    #  "seoId": "south-brooklyn-brooklyn-ny",},

    {"id": 21555,
     "name": "Boerum Hill",
     "seoId": "boerum-hill-brooklyn-ny",},   

    # {"id": 190271,
    #  "name": "Downtown Manhattan",
    #  "seoId": "downtown-manhattan-manhattan-ny",},

    {"id": 21558,
     "name": "Financial District",
     "seoId": "financial-district-manhattan-ny",},
    

    {"id": 21462,
     "name": "Lower East Side",
     "seoId": "lower-east-side-manhattan-ny",},
    

    {"id": 161852,
     "name": "Two Bridges",
     "seoId": "two-bridges-manhattan-ny",},
    

    {"id": 21459,
     "name": "Vinegar Hill",
     "seoId": "vinegar-hill-brooklyn-ny",},
    

    {"id": 21447,
     "name": "Carroll Gardens",
     "seoId": "carroll-gardens-brooklyn-ny",},
    

    {"id": 21536,
     "name": "Navy Yard",
     "seoId": "navy-yard-brooklyn-ny",},  

    {"id": 21537,
     "name": "TriBeCa",
     "seoId": "tribeca-manhattan-ny",},

    # {"id": 162104,
    #  "name": "Civic Center",
    #  "seoId": "civic-center-manhattan-ny",},

    {"id": 21556,
     "name": "Fort Greene",
     "seoId": "fort-greene-brooklyn-ny",},

    {"id": 21548,
     "name": "Red Hook",
     "seoId": "red-hook-brooklyn-ny",},

    {"id": 21492,
     "name": "Gowanus",
     "seoId": "gowanus-brooklyn-ny",},
    
    # {"id": 21474,
    #  "name": "Chinatown",
    #  "seoId": "chinatown-manhattan-ny",},

    {"id": 21452,
     "name": "Brooklyn Heights",
     "seoId": "brooklyn-heights-brooklyn-ny",},

    {"id": 21523,
     "name": "Upper West Side",
     "seoId": "upper-west-side-manhattan-ny",},

    {"id": 21443,
     "name":
     "Upper East Side",
     "seoId": "upper-east-side-manhattan-ny",},

    {"id": 21509,
     "name": "Chelsea",
     "seoId": "chelsea-manhattan-ny",},

    {"id": 21468,
     "name": "West Village",
     "seoId": "west-village-manhattan-ny",},

    {"id": 21489,
     "name": "Prospect Heights",
     "seoId": "prospect-heights-brooklyn-ny",},

    {"id": 21508,
     "name": "Long Island City",
     "seoId": "long-island-city-queens-ny",},

    {"id": 21455,
     "name": "Park Slope",
     "seoId": "park-slope-brooklyn-ny",},
]

def query_compass(listing_type, locations):
    # locs = [
    #     {"id": 21462,
    #      "name": "Lower East Side",
    #      "seoId": "lower-east-side-manhattan-ny",},
    # ]   
    for bkl in locations:
    # for bkl in locs:
        for result in query_bk_location(bkl, listing_type):
            yield result

def query_bk_location(bk_location, listing_type):
    # curl invocation:
    # curl -s 'https://www.compass.com/for-rent/brooklyn-heights-brooklyn-ny/' -H 'content-type: application/json'    --data-binary '{"rawLolSearchQuery":{"listingTypes":[0],"rentalStatuses":[7,5],"num":20,"sortOrder":115,"start":290,"locationIds":[21452],"schoolNames":[],"facetFieldNames":["contributingDatasetList","compassListingTypes","comingSoon"]}, "purpose":"search"}'

    listing_params = (
        {"listingTypes": [2], "saleStatuses": [12, 9]} if listing_type == LISTING_TYPE_SALE else
        {"listingTypes": [0], "rentalStatuses": [7, 5]} if listing_type == LISTING_TYPE_RENTAL else
        None
    )
    url_slug = (
        "homes-for-sale" if listing_type == LISTING_TYPE_SALE else
        "for-rent" if listing_type == LISTING_TYPE_RENTAL else
        None
    )
    if listing_params is None:
        raise ValueError("Invalid listing type: {}".format(listing_type))
    
    start = 0
    stride = 20
    totalItems = -1
    while totalItems < 0 or start < totalItems:
        resp = requests.post(
            "https://www.compass.com/{}/{}{}".format(
                url_slug,
                bk_location["seoId"],
                "/start={}/".format(start) if start > 0 else "",
            ),
            json={
                "rawLolSearchQuery": {
                    #"listingTypes": [0],
                    #"rentalStatuses": [7,5],
                    "num": stride,
                    "sortOrder": 115,
                    "start": start,
                    "locationIds": [bk_location["id"]],
                    "schoolNames": [],
                    "facetFieldNames": ["contributingDatasetList","compassListingTypes","comingSoon"],
                    **listing_params
                },
                "purpose": "search",
            },               
        )

        response_json = resp.json()
        if not response_json["lolResults"]["data"]:
            break

        totalItems = response_json["lolResults"]["totalItems"]
        stride = len(response_json["lolResults"]["data"])
        start += stride

        for result in extract_listings_from_response(response_json):
            yield result

def extract_unit_type(raw_type):
    # {'Condo', 'Multi Family', 'Other', 'Co-op', 'Single Family', 'Townhouse', 'Condop', 'Non-Residential', 'Land', 'Mixed Use'}
    if "Townhouse" in raw_type:
        return "townhouse"
    elif "Condop" in raw_type:
        return "condop"
    elif "Condo" in raw_type:
        return "condo"
    elif "Co-op" in raw_type:
        return "coop"
    else:
        return "other"

def extract_listings_from_response(response_json):
    listing_dicts = [e["listing"] for e in response_json["lolResults"]["data"]]
    for ld in listing_dicts:
        try:
            price = ld["price"]
            size = ld["size"] if "size" in ld else {}
            location = ld["location"]
            building = ld["buildingInfo"]
            details = ld["detailedInfo"]
            yield CompassListing(
                permalink=ld["canonicalPageLink"],
                address=location["prettyAddress"],
                neighborhood=location["neighborhood"],
                latitude=location["latitude"],
                longitude=location["longitude"],
                price_dollars=price["lastKnown"],
                original_price_dollars=price.get("listed", 0),
                sq_ft=(size.get("squareFeet") or size.get("lotSizeInSquareFeet")),
                beds=size.get("bedrooms"),
                baths=size.get("totalBathrooms"),
                year_opened=building.get("buildingYearOpened"),
                building_id=building.get("id"),
                building_units=building.get("buildingUnits"),
                monthly_sales_charges=price.get("monthlySalesCharges"),
                monthly_sales_charges_incl_taxes=price.get("monthlySalesChargesInclTaxes"),
                unit_type=extract_unit_type(details["propertyType"]["masterType"]["GLOBAL"]),
                first_listed=(
                    "events" in ld and
                    ld["events"] and
                    "timetstamp" in ld["events"][0] and
                    datetime.datetime.fromtimestamp(ld["events"][0]["timestamp"] / 1000.0).strftime("%Y-%m-%d")
                    or None
                ),
                parking_spaces=details.get("totalParkingSpaces"),
                amenities=json.dumps(details.get("amenities")),
            )
        except KeyError:
            continue

def main(argv):
    import argparse
    parser = argparse.ArgumentParser(description="Pull listing data from Compass")
    parser.add_argument("--sales", action="store_true")
    parser.add_argument("--long-island", action="store_true")
    parser.add_argument("--austin", action="store_true")

    parsed = parser.parse_args(argv[1:])
    listing_type = LISTING_TYPE_SALE if parsed.sales else LISTING_TYPE_RENTAL
    locations = LONG_ISLAND_LOCATIONS if parsed.long_island else AUSTIN_LOCATIONS if parsed.austin else BK_LOCATIONS

    writer = csv.writer(sys.stdout)    
    writer.writerow(CompassListing._fields)
    for result in query_compass(listing_type, locations):
        writer.writerow(result)
    return 0


    with open("/home/jhoon/compass.json") as infile:
        writer.writerows(extract_listings_from_response(json.load(infile)))

if __name__ == "__main__":
    sys.exit(main(sys.argv))
