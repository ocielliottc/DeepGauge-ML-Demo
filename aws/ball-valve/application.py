# ******************************************************************
#      Author: Chad Elliott
#        Date: 2/12/2020
# Description: A simple application to continually poll a camera,
#              make a call to process the image using ML and send
#              that information to an AWS kinesis data stream.
# ******************************************************************

# ******************************************************************
# Import Section
# ******************************************************************

import json, boto3, time, sys
from bson import ObjectId
from test_valve import ValveCamera
from datetime import datetime

# ******************************************************************
# Function Section
# ******************************************************************

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

# ******************************************************************
# Main Section
# ******************************************************************

## Unique ID assocated with camera that was assigned during provisioning.
uniqueId = 'BallValveCamera' if (len(sys.argv) <= 1) else sys.argv[1]
cameraURI = 'rtsp://test:testible@172.16.10.158/live' if (len(sys.argv) <= 2) else sys.argv[2]

## Prepare for retieving settings and sending data
db = boto3.client('dynamodb')
kinesis = boto3.client('kinesis')
valveCamera = ValveCamera()

## Continually loop polling the camera and sending the result to our stream
while True:
    print("get: " + cameraURI + ' = ', end='')
    state = valveCamera.checkState(cameraURI)
    print(state)

    result = json.dumps({"id": state, "score": 100})
    kinesis.put_record(StreamName=uniqueId, Data=result,
                       PartitionKey='singleshardkey')

    delay = get_current_rate(db, uniqueId, 300)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S') +
          ": (" + str(delay) + " sec) ", end='')
    sys.stdout.flush()
    time.sleep(delay)

