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

CURRENCY_RATE_URL = "https://api.monobank.ua/bank/currency"
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

    def currencyA(self, currencies: list[Currency]) -> Optional[Currency]:
        return next((c for c in currencies if c.number == str(self.currencyCodeA)), None)

    def currencyB(self, currencies: list[Currency]) -> Optional[Currency]:
        return next((currency for currency in currencies if currency.number == str(self.currencyCodeB)), None)

    def dict(self, currencies: list[Currency], requested: str = None) -> dict:
        d = asdict(self)
        d.pop("rateCross", None)
        d["requested"] = requested
        currencyA = self.currencyA(currencies)
        currencyB = self.currencyB(currencies)
        if currencyA is not None and currencyB is not None:
            d["currencyA"] = currencyA.code
            d["currencyB"] = currencyB.code
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
        print(f"Calling endpoint: {CURRENCY_RATE_URL}")
        response = requests.get(CURRENCY_RATE_URL)
        response.raise_for_status()
        currencies = [Currency(**currency.to_dict()) for currency in db.collection("currency").stream()]
        if response.status_code == 200:
            json = response.json()
            currency_rates = parse_currency_rates(json)
            print(f"USD-UAH Rate: {get_rate_by_code(currency_rates, currencies, "USD", "UAH")}")
            print(f"EUR-UAH Rate: {get_rate_by_code(currency_rates, currencies, "EUR", "UAH")}")
            print(f"EUR-USD Rate: {get_rate_by_code(currency_rates, currencies, "EUR", "USD")}")
        else:
            print(f"Request failed with status code {response.status_code}")

        now = datetime.now()
        daytime_str = now.strftime("%Y%m%d_%H%M%S")
        day_str = now.strftime("%Y%m%d")
        for currency_rate in currency_rates:
            currency_rate_dict = currency_rate.dict(currencies, now)
            currencyA = currency_rate.currencyA(currencies)
            currencyB = currency_rate.currencyB(currencies)
            if currencyA is None or currencyB is None: continue
            document_id = f"{currencyA.code}_{currencyB.code}"
            db.collection("rate").document(document_id).set(currency_rate_dict)
            db.collection("rate", document_id, day_str).add(currency_rate_dict, daytime_str)
            db.collection("rate", document_id, day_str).document(day_str).set(currency_rate_dict)
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

def parse_currency_rates(json_data) -> List[CurrencyRate]:
    allowed = {field.name for field in CurrencyRate.__dataclass_fields__.values()}
    return [
        CurrencyRate(**{k: v for k, v in item.items() if k in allowed})
        for item in json_data
    ]

def get_rate_by_code(rates: List[CurrencyRate], currencies: List[Currency], currencyA: str, currencyB: str) -> Optional[CurrencyRate]:
    currencyCodeA = next((c.number for c in currencies if c.code == currencyA), None)
    currencyCodeB = next((c.number for c in currencies if c.code == currencyB), None)
    if currencyCodeA is None or currencyCodeB is None: return None
    return get_rate_by_number(rates, int(currencyCodeA), int(currencyCodeB))

def get_rate_by_number(rates: List[CurrencyRate], currencyCodeA: int, currencyCodeB: int) -> Optional[CurrencyRate]:
    return next(
        (rate for rate in rates if rate.currencyCodeA == currencyCodeA and rate.currencyCodeB == currencyCodeB), None
    )
