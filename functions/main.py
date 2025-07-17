from firebase_functions import scheduler_fn, https_fn
from firebase_functions.options import set_global_options
from firebase_admin import initialize_app
from google.cloud import firestore
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime
import os, requests, re, json

credentials = "firebase-key.json"
if os.path.exists(credentials): os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials

set_global_options(max_instances=3)

initialize_app()

db = firestore.Client()

ENDPOINT = "https://api.monobank.ua/bank/currency"
USD = 840
EUR = 978
UAH = 980
CURRENCY_CODE_URL = "https://www.iban.com/currency-codes"

@dataclass
class Currency:
    number: int
    code: str
    currency: str

@dataclass
class CurrencyRate:
    currencyCodeA: int
    currencyCodeB: int
    date: int
    rateBuy: Optional[float] = None
    rateSell: Optional[float] = None
    rateCross: Optional[float] = None
    timestamp: str = field(init=False)

    def __post_init__(self):
        dt = datetime.fromtimestamp(self.date)
        self.timestamp = dt.isoformat()

    def dict(self, requested: str = None) -> dict:
        d = asdict(self)
        d.pop("rateCross", None)
        d["requested"] = requested
        return d

@https_fn.on_request()
def populate_currencies(request) -> https_fn.Response:
    currencies = fetch_currency_codes()
    batch = db.batch()

    for currency in currencies:
        batch.set(db.collection('currency').document(currency.code), asdict(currency))

    try:
        batch.commit()
        return https_fn.Response(
            json.dumps({"message": "Batch write completed successfully! All currencies added."}),
            status=200,
            content_type="application/json"
        )
    except Exception as e:
        return https_fn.Response(
            json.dumps({"error": f"An error occurred during batch write: {e}"}),
            status=400,
            content_type="application/json"
        )

@scheduler_fn.on_schedule(schedule="every 1 hours", timezone="Europe/Kyiv")
def fetch_and_store_data(event):
    print(f"[{datetime.now()}] Starting hourly data fetch...")
    try:
        print(f"Calling endpoint: {ENDPOINT}")
        response = requests.get(ENDPOINT)
        response.raise_for_status()
        if response.status_code == 200:
            json = response.json()
            currency_rates = parse_currency_rates(json)
            usd_uah = get_usd_rate(currency_rates)
            eur_uah = get_eur_rate(currency_rates)
            eur_usd = get_eur_usd_rate(currency_rates)
            print(f"USD-UAH Rate: {usd_uah}")
            print(f"EUR-UAH Rate: {eur_uah}")
            print(f"EUR-USD Rate: {eur_usd}")
        else:
            print(f"Request failed with status code {response.status_code}")

        now = datetime.now()
        daytime_str = now.strftime("%Y%m%d_%H%M%S")
        day_str = now.strftime("%Y%m%d")
        usd_uah = usd_uah.dict(now)
        eur_uah = eur_uah.dict(now)
        eur_usd = eur_usd.dict(now)
        db.collection("currency").document("usd_uah").set(usd_uah)
        db.collection("currency").document("eur_uah").set(eur_uah)
        db.collection("currency").document("eur_usd").set(eur_usd)
        db.collection("currency", "usd_uah", day_str).add(usd_uah, daytime_str)
        db.collection("currency", "eur_uah", day_str).add(eur_uah, daytime_str)
        db.collection("currency", "eur_usd", day_str).add(eur_usd, daytime_str)
        db.collection("currency", "usd_uah", day_str).document(day_str).set(usd_uah)
        db.collection("currency", "eur_uah", day_str).document(day_str).set(eur_uah)
        db.collection("currency", "eur_usd", day_str).document(day_str).set(eur_usd)
        print("Data successfully stored in Firestore at ", now)
    except requests.exceptions.RequestException as e:
        print(f"Error making HTTP request: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    print("Hourly data fetch completed.")

def fetch_currency_codes() -> List[Currency]:
    response = requests.get(CURRENCY_CODE_URL)
    response.raise_for_status()
    html = response.text

    # Find the table rows using regex
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
    currencies = {}
    for row in rows[1:]:  # Skip header
        cols = re.findall(r"<td>(.*?)</td>", row, re.DOTALL)
        if len(cols) >= 4:
            number = cols[3].strip()
            code = cols[2].strip()
            currency_name = cols[1].strip()
            if number and code and currency_name and number not in currencies:
                currencies[number] = Currency(number=number, code=code, currency=currency_name)
    return list(currencies.values())

def parse_currency_rates(json_data: list) -> List[CurrencyRate]:
    allowed = {f.name for f in CurrencyRate.__dataclass_fields__.values()}
    return [
        CurrencyRate(**{k: v for k, v in item.items() if k in allowed})
        for item in json_data
    ]

def get_usd_rate(rates: List[CurrencyRate]) -> Optional[CurrencyRate]:
    return get_rate(rates, USD, UAH)

def get_eur_rate(rates: List[CurrencyRate]) -> Optional[CurrencyRate]:
    return get_rate(rates, EUR, UAH)

def get_eur_usd_rate(rates: List[CurrencyRate]) -> Optional[CurrencyRate]:
    return get_rate(rates, EUR, USD)

def get_rate(rates: List[CurrencyRate], codeA: int, codeB: int) -> Optional[CurrencyRate]:
    return next(
        (rate for rate in rates if rate.currencyCodeA == codeA and rate.currencyCodeB == codeB), None
    )
