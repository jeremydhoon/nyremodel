#!/usr/bin/env python

import sys

import json
from matplotlib import pyplot
import numpy as np
import pandas as pd
from sklearn.metrics import explained_variance_score, mean_squared_error, median_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, LabelBinarizer
from xgboost.sklearn import XGBRegressor

import compass
import dcf


MAX_PRICE_DOLLARS = 15000
#MAX_PRICE_DOLLARS = 3000000
FEATURE_COLUMNS = [
    "neighborhood",
    "sq_ft",
    "beds",
    "baths",
    "year_opened",
    "building_units",
    "unit_type",
    "parking_spaces",
    "amenity",
]

COMMON_AMENITIES = (
    'Elevator',
    'Laundry in Building',
    'Dishwasher',
    'Full-Time Doorman',
    'Gym',
    'Concierge',
    'Washer / Dryer in Unit',
    'Common Roof Deck',
    'Bike Room',
    'High Ceilings',
    'Garage',
    'Voice Intercom',
    'Hardwood Floors',
    'Common Outdoor Space',
    'Pet Friendly',
    'Doorman',
    'Walk Up',
    'Roof Deck',
    'Private Outdoor Space',
    'Oversized Windows',
)

def label_encode(df, feature):
    enc = LabelBinarizer()
    enc.fit(df[feature])
    out_df = pd.DataFrame(enc.transform(df[feature]))
    col_names = [feature + "_" + cls for cls in enc.classes_]
    return out_df.rename(columns=dict(enumerate(col_names)))

def add_amenities(df):
    amenities_set = df["amenities"].map(lambda x: set(json.loads(x)) if isinstance(x, str) else set())
    return pd.DataFrame(
        dict(
            ("amenity_" + amenity, amenities_set.map(lambda x: float(amenity in x)))
            for amenity in COMMON_AMENITIES
        )
    )

def clean_features(df):
    #categorical_cols = ["neighborhood", "unit_type"]
    categorical_cols = []
    drop_cols = ["neighborhood", "unit_type"]
    cols = [
        label_encode(df, col)
        for col in categorical_cols
    ]
    out = pd.concat([df, *cols, add_amenities(df)], axis=1).drop(columns=categorical_cols + drop_cols)
    return out

def compute_model_metrics(targets, predicted_targets):
    return {
        "explained variance": explained_variance_score(targets, predicted_targets),
        "RMS error": np.sqrt(mean_squared_error(targets, predicted_targets)),
        "Median absolute error:": median_absolute_error(targets, predicted_targets),
    }

def is_feature_col(col_name):
    return any([col_name.startswith(feature_name) for feature_name in FEATURE_COLUMNS])

def count_sum(acc, lst):
    for el in lst:
        acc[el] = acc.get(el, 0) + 1
    return acc

def select_feature_columns(df):
    return [col for col in df.columns if is_feature_col(col)]


def train(raw_df):
    #df = raw_df[raw_df["neighborhood"].isin(set([loc["name"] for loc in compass.BK_LOCATIONS]))]
    df = raw_df
    df = clean_features(df)
    df = df[df["price_dollars"] < MAX_PRICE_DOLLARS]
    df = df[df["address"] != "117 Underhill Avenue"]
           
    features = df[select_feature_columns(df)]
    targets = df["price_dollars"]
    features_train, features_test, targets_train, targets_test = train_test_split(features, targets, test_size=0.10)

    reg = XGBRegressor(
        #eta=0.1,
        max_depth=2,
        colsample_bytree=0.25,
    )
    reg.fit(features_train, targets_train)

    predicted_train_targets = reg.predict(features_train)
    print("Training metrics:")
    print(compute_model_metrics(targets_train, predicted_train_targets))

    predicted_test_targets = reg.predict(features_test)
    print("Test metrics:")
    print(compute_model_metrics(targets_test, predicted_test_targets))
    
    return reg

def zero_if_nan(f):
    return 0 if np.isnan(f) else f

def get_irr(row):
    # permalink,address,neighborhood,latitude,longitude,price_dollars,original_price_dollars,sq_ft,beds,baths,year_opened,building_id,building_units,monthly_sales_charges,monthly_sales_charges_incl_taxes,unit_type,first_listed,parking_spaces,amenities
    # =if(K6014>=2010,200,if(K6014>=2000,300,400))*if(G6014>=2000000,1.5,1)*if(I6014<=2,1,2)
    year_built = row["year_opened"]
    capital_reserve = (
        (200 if year_built >= 2010 else 300 if year_built >= 2000 else 400) *
        (1.5 if row["price_dollars"] >= 2000000 else 1) *
        (2 if row["beds"] >= 2 else 1)
    )
    try:
        return dcf.get_unlevered_returns(
            purchase_price_dollars=1575000,
            sq_ft=row["sq_ft"],
            closing_costs_pct=0.04,
            initial_downtime_months=3,
            interim_downtime_months=1,
            lease_length_months=36,
            annual_rent_growth_pct=0.02,
            annual_expense_growth_pct=0.02,
            monthly_rent_dollars=row["predicted_rent"],
            monthly_utilities_rent_pct=0.025,
            monthly_tax_dollars=zero_if_nan(row["monthly_sales_charges_incl_taxes"]) - zero_if_nan(row["monthly_sales_charges"]),
            monthly_common_charges_dollars=zero_if_nan(row["monthly_sales_charges"]),
            monthly_homeowners_insurance_dollars=100,
            monthly_capital_reserve_dollars=capital_reserve,
            hold_period_months=60,
            exit_cap_pct=0.035,
            exit_sq_ft_price_ceiling_dollars=3000,
            exit_costs_pct=0.08,
        ).irr_pct
    except Exception as error:
        import pdb; pdb.set_trace()
        raise
    

def regress(sales_df, reg):
    clean_df = clean_features(sales_df)
    df = clean_df[select_feature_columns(clean_df)]
    sales_df["predicted_rent"] = reg.predict(df)
    sales_df["irr"] = np.array([get_irr(r) for _, r in sales_df.iterrows()])


def main(argv):
    rentals_df = pd.read_csv(argv[1])
    sales_df = pd.read_csv(argv[2])
    reg = train(rentals_df)
    regress(sales_df, reg)
    sales_df.to_csv(argv[3])
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
