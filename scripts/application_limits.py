from datetime import datetime
from typing import List, Optional, Tuple
from tap import Tap
import pdfplumber
from pydantic import BaseModel
import re


class Args(Tap):
    """Parse a credit report to identify common credit card issuer limits"""

    file: str  # Path to the credit report file


class Account(BaseModel):
    name: str
    account_number: str
    account_type: str
    open_date: datetime
    balance: int
    is_open: bool

    closed_comments: Optional[str] = None

    @classmethod
    def from_extracted_str(cls, extracted_str: str) -> "Account":
        pattern = r"Account name\s+(?P<name>.+?)\s+Balance\s+(?P<balance>\$[\d,s]*|-)\s+Account number\s+(?P<account_number>[\dA-Z]+)\s+.*?Account type\s+(?P<account_type>.+?)\s+.*?Date opened\s+(?P<open_date>\w+\s+\d+,\s+\d{4})\s+.*?Open/closed\s+(?P<is_open>Open|Closed)"

        match = re.search(pattern, extracted_str, re.DOTALL)
        if not match:
            raise ValueError("Could not parse account information from string")

        data = match.groupdict()
        num_balance = data["balance"].split(",")[0].replace("$", "").replace("-", "0")

        return cls(
            name=data["name"],
            account_number=data["account_number"],
            account_type=data["account_type"],
            open_date=datetime.strptime(data["open_date"], "%b %d, %Y"),
            balance=int(num_balance),
            is_open=data["is_open"].lower() == "open",
        )


def parse_credit_report(file: str):
    credit_accounts = []
    with pdfplumber.open(file) as pdf:
        start_processing = False
        for page in pdf.pages:
            if not start_processing:
                page_text = page.extract_text_simple().lower()

                if "at a glance" in page_text:
                    # Skip section that appears like account info
                    continue

                if "open account" in page_text:
                    start_processing = True

            if not start_processing:
                continue

            page_tables = page.extract_table()
            if len(page_tables) < 2:
                break

            account_info = page_tables[1][0]
            account = Account.from_extracted_str(account_info)

            credit_accounts.append(account)
    return credit_accounts


def extract_5_24(credit_reports: List[Account]):
    beginning_of_month = datetime.now().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    two_years_ago_datetime = beginning_of_month.replace(
        year=beginning_of_month.year - 2
    )
    account_dates = [
        (account.name, account.account_number, account.open_date)
        for account in credit_reports
        if account.is_open and account.open_date >= two_years_ago_datetime
    ][:5]
    return sorted(account_dates, key=lambda x: x[1], reverse=True)


def print_5_24_summary(five_24_accounts: List[Tuple[str, str, datetime]]):
    HEADER_ACCOUNT_NAME = "Account Name"
    HEADER_ACCOUNT_NUMBER = "Account #"
    HEADER_OPEN_DATE = "Open Date"

    count = len(five_24_accounts)
    print(f"\n5/24 Status: {count}/5 slots used\n")

    if count == 0:
        print("No accounts opened in the last 24 months.")
        return

    name_width, acct_width, date_width = (
        len(HEADER_ACCOUNT_NAME),
        len(HEADER_ACCOUNT_NUMBER),
        len(HEADER_OPEN_DATE),
    )
    for name, account_number, open_date in five_24_accounts:
        name_width = max(name_width, len(name))
        acct_width = max(acct_width, len(account_number))
        date_width = max(date_width, len(open_date.strftime("%Y-%m-%d")))

    header = f"{HEADER_ACCOUNT_NUMBER:<{name_width}}  {HEADER_ACCOUNT_NAME:<{acct_width}}  {HEADER_OPEN_DATE:<{date_width}}"
    print(header)
    print("-" * len(header))

    for name, account_number, open_date in five_24_accounts:
        print(
            f"{name:<{name_width}}  {account_number:<{acct_width}}  {open_date.strftime('%Y-%m-%d'):<{date_width}}"
        )


if __name__ == "__main__":
    args = Args().parse_args()
    credit_accounts = parse_credit_report(args.file)
    five_24_accounts = extract_5_24(credit_accounts)
    print_5_24_summary(five_24_accounts)
