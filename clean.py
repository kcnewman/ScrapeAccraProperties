import ast
import re
from pathlib import Path

import pandas as pd

SALE_PATTERNS = [
    "for sale",
    "on sale",
    "sale",
    "sale only",
    "selling",
    "sell",
    "sold",
    "property for sale",
    "house for sale",
    "apartment for sale",
    "buy",
    "buyer",
    "title deed",
    "deed",
    "closing",
    "escrow",
    "transfer",
    "down payment",
    "mortgage",
    "loan",
    "financing",
    "cash only",
    "investment",
    "roi",
    "yield",
    "capital gain",
    "airbnb",
    "air bnb",
    "booking.com",
    "vrbo",
]

PERIOD_PATTERNS = [
    "per night",
    "nightly",
    "per day",
    "daily",
    "by the day",
    "short term",
    "short-term",
    "weekly",
    "per week",
    "weekend",
    "airbnb",
    "air bnb",
    "business short",
    "holidays",
    "short stay",
    "holiday rental",
    "vacation rental",
    "tourist rental",
    "guesthouse",
    "guest house",
]

LOCALITY_REPLACEMENTS = {
    "Dworwulu": "Dzorwulu",
    "Lartebiokoshie": "Lartebiokorshie",
    "Ashongman Estate": "Ashongman",
    "Ashoman Estate": "Ashongman",
    "Old Ashongman": "Ashongman",
    "Old Ashoman": "Ashongman",
    "Ashoman": "Ashongman",
    "Greater Accra": "Other",
    "Ledzokuku-Krowor": "Teshie",
    "South Shiashie": "East Legon",
    "Okponglo": "East Legon",
    "Little Legon": "East Legon",
    "Abofu": "Achimota",
    "Akweteyman": "Achimota",
    "Banana Inn": "Dansoman",
    "South La": "Labadi",
    "Bubuashie": "Kaneshie",
}

LOC_REPLACEMENTS = {
    "Circle": "Nkrumah Circle",
    "Anyaa": "Anyaa Market",
    "Ridge": "North Ridge",
    "Dome": "Dome Market",
    "Abokobi": "Abokobi Station",
    "Nungua": "Nungua Central",
    "Other": "Accra Metropolitan",
}

FINAL_COLUMNS = [
    "url",
    "fetch_date",
    "house_type",
    "bathrooms",
    "bedrooms",
    "price",
    "locality",
    "Condition",
    "Furnishing",
    "Property Size",
    "24-hour Electricity",
    "Air Conditioning",
    "Apartment",
    "Balcony",
    "Chandelier",
    "Dining Area",
    "Dishwasher",
    "Hot Water",
    "Kitchen Cabinets",
    "Kitchen Shelf",
    "Microwave",
    "Pop Ceiling",
    "Pre-Paid Meter",
    "Refrigerator",
    "TV",
    "Tiled Floor",
    "Wardrobe",
    "Wi-Fi",
    "loc",
]

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_JIJI_INPUT = PROJECT_ROOT / "outputs" / "data" / "jiji_data.csv"
DEFAULT_RAW_OUTPUT = PROJECT_ROOT / "outputs" / "data" / "raw.csv"


def extract_locality(location):
    parts = str(location).split(",")
    return parts[1].strip() if len(parts) >= 3 else parts[0].strip()


def expand_column(df, col, sep=None):
    if sep:
        encoded = df[col].str.strip().str.get_dummies(sep=sep)
        encoded.columns = encoded.columns.str.strip()
    else:
        encoded = df[col].apply(ast.literal_eval).apply(pd.Series)
    return df.join(encoded).drop(columns=[col])


def clean(df):
    df = df.copy()

    df["locality"] = df["location"].apply(extract_locality)
    df = df.drop(columns=["location"])

    df["house_type"] = df["house_type"].fillna("Bedsitter")

    df = df.dropna(subset=["bathrooms", "bedrooms"])
    for col in ["bathrooms", "bedrooms"]:
        df[col] = df[col].str.split().str[0]

    df["price"] = (
        df["price"]
        .str.replace("GH₵ ", "", regex=False)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

    df = expand_column(df, "properties")
    df = expand_column(df, "amenities", sep=",")

    if "Facilities" in df.columns:
        facilities = df["Facilities"].str.strip().str.get_dummies(sep=",")
        facilities.columns = facilities.columns.str.strip()
        for col in facilities.columns:
            if col in df.columns:
                df[col] = df[[col]].join(facilities[[col]], rsuffix="_new").max(axis=1)
            else:
                df[col] = facilities[col]
        df = df.drop(columns=["Facilities"])

    regex = "|".join(re.escape(p) for p in SALE_PATTERNS + PERIOD_PATTERNS)
    text = (df["title"].fillna("") + " " + df["description"].fillna("")).str.lower()
    df = df[~text.str.contains(regex, na=False)]

    df["locality"] = df["locality"].replace(LOCALITY_REPLACEMENTS)
    df["loc"] = df["locality"].replace(LOC_REPLACEMENTS)

    df = df[[col for col in FINAL_COLUMNS if col in df.columns]].copy()

    return df


def clean_jiji_csv(
    input_csv: str | Path = DEFAULT_JIJI_INPUT,
    output_csv: str | Path = DEFAULT_RAW_OUTPUT,
) -> pd.DataFrame:
    input_path = Path(input_csv)
    output_path = Path(output_csv)

    df = pd.read_csv(input_path)
    cleaned_df = clean(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(output_path, index=False)

    return cleaned_df


if __name__ == "__main__":
    clean_jiji_csv()
