import json
import boto3
import time
import sys

def get_current_rate(db, uniqueId, default):
  ## Connect to the database, find our meta data table and get the rate
  ## for capture assigned during provisioning.
  rate = default
  try:
      rname = 'rate'
      map_name = 'data'
      response = db.list_tables()
      tables = response['TableNames']
      for table in tables:
          if (table.index('MetaData') >= 0):
              item = db.get_item(TableName=table,
                                 Key={'key': {'S': uniqueId}})
              entry = item['Item'][map_name]['M']
              if (rname in entry.keys()):
                  rate = int(entry[rname]['S'], 10)
              break
  except:
      pass
  return rate

## Unique ID assocated with camera that was assigned during provisioning.
uniqueId = 'PiCamera' if (len(sys.argv) <= 1) else sys.argv[1]

## Prepare for sending capture trigger
db = boto3.client('dynamodb')
client = boto3.client('iot-data')
payload = json.dumps({'kstream': uniqueId})

## Continually loop sending capture trigger
while True:
    print("Sending capture message for " + uniqueId)
    sys.stdout.flush()
    client.publish(topic='deepgauge_model/capture', payload=payload)
    delay = get_current_rate(db, uniqueId, 300)
    print("Waiting " + str(delay) + " seconds... ", end='')
    sys.stdout.flush()
    time.sleep(delay)

