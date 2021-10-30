#!/usr/bin/env python

import collections
import csv
import numpy as np
import numpy_financial as npf
import pandas as pd
import pdb
import re
import sys

UnleveredReturn = collections.namedtuple(
    "UnleveredReturn",
    ('irr_pct', 'gross_sale_price_dollars', 'moic_pct', 'equity_dollars', 'profit_dollars', 'gross_sale_price_sq_ft_dollars'),
)

Listing = collections.namedtuple(
    "Listing",
    (
        "permalink",
        "address",
        "status",
        "price",
        "property_type",
        "neighborhood",
        "beds",
        "baths",
        "sq_ft",
        "maintenance_common_charges",
        "real_estate_taxes",
    ),
)

DIGITS = re.compile(r'[^\d]+')
def to_i(s):
    f = float(DIGITS.sub('', s) or 0)
    return 0.0 if np.isnan(f) else f


def get_unlevered_returns(
        purchase_price_dollars,
        sq_ft,
        closing_costs_pct,
        initial_downtime_months,
        interim_downtime_months,
        lease_length_months,
        # Annual growth trends,
        annual_rent_growth_pct,
        annual_expense_growth_pct,
        # Monthly fees (pcts are of monthly_rent_dollars)
        monthly_rent_dollars,
        monthly_utilities_rent_pct,
        monthly_tax_dollars,
        monthly_common_charges_dollars,
        monthly_homeowners_insurance_dollars,
        monthly_capital_reserve_dollars,
        # Asset disposition conditions (pct of sales price)
        hold_period_months,
        exit_cap_pct,
        exit_sq_ft_price_ceiling_dollars,
        exit_costs_pct):


    modeled_month_count = hold_period_months * 2
    columns = (
        "rent",
        "vacancy",
        "utilities",
        "monthly_taxes",
        "common_charges",
        "homeowners_insurance",
        "noi",
        "capital_reserve",
        "free_cash_flow",
        "total_purchase_price",
        "net_sales_proceeds",
        "unlevered_cash_flow",
    )
    start_date_str = "2021-01-01"
    months = np.arange(0, modeled_month_count, 1, dtype=np.int64)
    index = pd.period_range(start_date_str, freq='M', periods=modeled_month_count)
    df = pd.DataFrame(
        columns=columns,
        index=index,
        dtype=np.float64,        
    )
    expense_growth = np.power(1.0 + annual_expense_growth_pct, months // 12)
    df.loc[:, "rent"] = (
        monthly_rent_dollars *
        np.power(1.0 + annual_rent_growth_pct, months // 12)
    )
    # TODO: add interim vacancy
    df.loc[:, "vacancy"] = (
        -monthly_rent_dollars *
        np.logical_or(months // initial_downtime_months == 0, False)
    )
    df.loc[:, "utilities"] = (
        -monthly_utilities_rent_pct * monthly_rent_dollars *
        expense_growth
    )
    df.loc[:, "monthly_taxes"] = -monthly_tax_dollars * expense_growth
    df.loc[:, "common_charges"] = (
        -monthly_common_charges_dollars *
        expense_growth
    )
    df.loc[:, "homeowners_insurance"] = (
        -monthly_homeowners_insurance_dollars *
        expense_growth
    )
    df.loc[:, "noi"] = np.sum(
        [
            df.loc[:, col]  for col in
            (
                "rent",
                "vacancy",
                "utilities",
                "monthly_taxes",
                "common_charges",
                "homeowners_insurance",
            )
        ],
        axis=0,
        dtype=np.float64
    )
    df.loc[:, "capital_reserve"] = (
        -monthly_capital_reserve_dollars *
        expense_growth
    )
    df.loc[:, "free_cash_flow"] = np.sum(
        [df.loc[:, "noi"], df.loc[:, "capital_reserve"]],
        axis=0,
    )
    df.loc[:, "total_purchase_price"] = np.zeros(months.shape, dtype=np.float64)
    df.loc[pd.Period(start_date_str, freq='M'), "total_purchase_price"] = (
        -purchase_price_dollars * (1.0 + closing_costs_pct)
    )
    df.loc[:, "net_sales_proceeds"] = np.zeros(months.shape, dtype=np.float64)

    end_date = pd.Period(start_date_str, freq='M') + pd.offsets.MonthEnd(hold_period_months)
    gross_sales_price = np.min((
        np.finfo(float).max if np.isnan(sq_ft) else float(exit_sq_ft_price_ceiling_dollars * sq_ft),
        np.sum(df.loc[end_date + pd.offsets.MonthEnd(1) : end_date + pd.offsets.MonthEnd(12), "noi"]) / exit_cap_pct,
    ))
    net_sales_proceeds = gross_sales_price * (1.0 - exit_costs_pct)
    assert not np.isnan(net_sales_proceeds), "Failed to compute net sales proceeds"
    df.loc[end_date, "net_sales_proceeds"] = net_sales_proceeds

    df.loc[:, "unlevered_cash_flow"] = np.sum(
        [df.loc[:, c] for c in ("free_cash_flow", "total_purchase_price", "net_sales_proceeds")],
        axis=0,
    )
    irr = (1.0 + npf.irr(df.loc[:end_date, "unlevered_cash_flow"]))**12 - 1
        
    equity = -np.sum(df.loc[:end_date, "unlevered_cash_flow"][df.loc[:end_date, "unlevered_cash_flow"] < 0])
    profit = np.sum(df.loc[:end_date, "unlevered_cash_flow"])
    return UnleveredReturn(
        irr_pct=irr,
        gross_sale_price_dollars=gross_sales_price,
        equity_dollars=equity,
        profit_dollars=profit,
        moic_pct=1 + profit/float(equity),
        gross_sale_price_sq_ft_dollars=gross_sales_price/float(sq_ft),
    )

def compute_returns_for_scrapes(infile):
    reader = csv.reader(infile)
    writer = csv.writer(sys.stdout)
    writer.writerow(
        "permalink price sq_ft irr gross_sale_price moic equity profit gross_sale_price_sq_ft_dollars rent".split()
    )
    
    for line in reader:
        l = Listing(*(line + ([""] * (10 - len(line)))))
        if not to_i(l.sq_ft):
            continue
        monthly_rent_dollars = to_i(l.price) * 0.04 / 12.0
        ret = get_unlevered_returns(
            purchase_price_dollars=to_i(l.price),
            sq_ft=to_i(l.sq_ft),
            closing_costs_pct=0.04,
            initial_downtime_months=3,
            interim_downtime_months=1,
            lease_length_months=36,
            annual_rent_growth_pct=0.02,
            annual_expense_growth_pct=0.02,
            monthly_rent_dollars=monthly_rent_dollars,
            monthly_utilities_rent_pct=0.025,
            monthly_tax_dollars=to_i(l.real_estate_taxes),
            monthly_common_charges_dollars=to_i(l.maintenance_common_charges),
            monthly_homeowners_insurance_dollars=100,
            monthly_capital_reserve_dollars=500,
            hold_period_months=60,
            exit_cap_pct=0.03,
            exit_sq_ft_price_ceiling_dollars=(to_i(l.price) * 1.5 / to_i(l.sq_ft)),
            exit_costs_pct=0.08,
        )
        writer.writerow((
            l.permalink,
            l.price,
            l.sq_ft,
            ret.irr_pct,
            ret.gross_sale_price_dollars,
            ret.moic_pct,
            ret.equity_dollars,
            ret.profit_dollars,
            ret.gross_sale_price_sq_ft_dollars,
            monthly_rent_dollars,
        ))

def compute_irr_for_shortlist(infile):
    reader = csv.reader(infile)
    writer = csv.writer(sys.stdout)

    for line in reader:
        if len(line) < 15 or not to_i(line[3]):
            extra = "IRR gross_sale_price moic equity profit sale_price_sq_ft".split() if line[1].strip().lower() == "address" else [""] * 6
            writer.writerow(line + extra)
            continue
        _, _, _, rent, cap_reserve, _, _, price, _, _, _, _, sq_ft, maintenance, taxes = line
        ret = get_unlevered_returns(
            purchase_price_dollars=to_i(price),
            sq_ft=to_i(sq_ft),
            closing_costs_pct=0.04,
            initial_downtime_months=3,
            interim_downtime_months=1,
            lease_length_months=36,
            annual_rent_growth_pct=0.02,
            annual_expense_growth_pct=0.02,
            monthly_rent_dollars=to_i(rent),
            monthly_utilities_rent_pct=0.025,
            monthly_tax_dollars=to_i(taxes),
            monthly_common_charges_dollars=to_i(maintenance),
            monthly_homeowners_insurance_dollars=100,
            monthly_capital_reserve_dollars=500,
            hold_period_months=60,
            exit_cap_pct=0.03,
            exit_sq_ft_price_ceiling_dollars=(to_i(price) * 1.5 / to_i(sq_ft)) if to_i(sq_ft) else to_i(price),
            exit_costs_pct=0.08,
        )
        writer.writerow(line + [ret.irr_pct, ret.gross_sale_price_dollars, ret.moic_pct, ret.equity_dollars, ret.profit_dollars, ret.gross_sale_price_sq_ft_dollars])
        

def main(argv):
    with open("re-shortlist.csv") as infile:
        compute_irr_for_shortlist(infile)
    return 0

    with open('scrapes-20200718.csv', 'r') as infile:
        compute_returns_for_scrapes(infile)
    return 0
    rets = get_unlevered_returns(
        purchase_price_dollars=1575000,
        sq_ft=1758,
        closing_costs_pct=0.04,
        initial_downtime_months=3,
        interim_downtime_months=1,
        lease_length_months=36,
        annual_rent_growth_pct=0.02,
        annual_expense_growth_pct=0.02,
        monthly_rent_dollars=10000,
        monthly_utilities_rent_pct=0.025,
        monthly_tax_dollars=1000,
        monthly_common_charges_dollars=500,
        monthly_homeowners_insurance_dollars=100,
        monthly_capital_reserve_dollars=500,
        hold_period_months=60,
        exit_cap_pct=0.035,
        exit_sq_ft_price_ceiling_dollars=1200,
        exit_costs_pct=0.08,
    )
    print(rets)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
