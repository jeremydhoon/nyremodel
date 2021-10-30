#!/usr/bin/env bash

set -e

TODAY="`date '+%Y-%m-%d'`"

python compass.py > "compass-rentals-$TODAY.csv" &
RENTALS_PID=$!
python compass.py --sales > "compass-sales-$TODAY.csv" &
SALES_PID=$!

wait $RENTALS_PID
wait $SALES_PID

python rentregress.py "compass-rentals-$TODAY.csv" "compass-sales-$TODAY.csv" "compass-sales-with-rents-$TODAY.csv"

echo "Daily pull complete. Data available in compass-sales-with-rents-$TODAY.csv. Generated `wc -l compass-sales-with-rents-$TODAY.csv | cut -f1 -d' '` records."


