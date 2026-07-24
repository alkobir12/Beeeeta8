#!/bin/bash
# Create test data on alkobir.com
BASE="https://alkobir.com"
LOGIN=$(curl -sS -X POST $BASE/api/auth/login -H "Content-Type: application/json" -d '{"username":"مدير","pin":"123123"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "TOKEN_LEN=${#TOKEN}"
H="Authorization: Bearer $TOKEN"

# Create vehicle (which auto-creates/links customer)
t0=$(date +%s.%N)
VEH=$(curl -sS -X POST $BASE/api/vehicles -H "$H" -H "Content-Type: application/json" -d '{
  "plate":"TEST-000",
  "make":"TEST-DO-NOT-USE",
  "model":"TEST-DO-NOT-USE",
  "year":2020,
  "customer_name":"TEST - DO NOT USE",
  "customer_phone":"0599999123",
  "customerName":"TEST - DO NOT USE",
  "customerPhone":"0599999123"
}')
t1=$(date +%s.%N)
echo "CREATE_VEHICLE_TIME=$(python3 -c "print($t1-$t0)")"
echo "VEHICLE_RESP=$VEH"
VID=$(echo "$VEH" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('id') or d.get('vehicle_id') or d.get('_id') or '')")
CID=$(echo "$VEH" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('customer_id') or d.get('customerId') or '')")
echo "VID=$VID"
echo "CID=$CID"

# Create visit
t0=$(date +%s.%N)
VIS=$(curl -sS -X POST $BASE/api/visits -H "$H" -H "Content-Type: application/json" -d "{
  \"vehicle_id\":\"$VID\",
  \"notes\":\"TEST\",
  \"items\":[{\"description\":\"TEST item 1\",\"quantity\":1,\"unit_price\":100,\"total\":100},{\"description\":\"TEST item 2\",\"quantity\":2,\"unit_price\":50,\"total\":100}]
}")
t1=$(date +%s.%N)
echo "CREATE_VISIT_TIME=$(python3 -c "print($t1-$t0)")"
echo "VISIT_RESP=$VIS"
VISID=$(echo "$VIS" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('id') or d.get('visit_id') or '')")
echo "VISID=$VISID"

# Template resolves
for T in invoice diagnosis quote; do
  t0=$(date +%s.%N)
  R=$(curl -sS "$BASE/api/document-templates/resolve?document_type=$T" -H "$H")
  t1=$(date +%s.%N)
  echo "RESOLVE_${T}_TIME=$(python3 -c "print($t1-$t0)")"
  echo "RESOLVE_${T}=$(echo "$R" | python3 -c "import sys,json;d=json.load(sys.stdin);print({k:d.get(k) for k in ['id','name','version','selection_reason']})")"
done

# Save vars
echo "$VID" > /tmp/vid.txt
echo "$CID" > /tmp/cid.txt
echo "$VISID" > /tmp/visid.txt
echo "$TOKEN" > /tmp/tok.txt
