# [START gae_python37_render_template]
from flask import Flask, Response, request, json, render_template, current_app, redirect
import boto3
import base64, json, logging, os
from config import db, app, connex_app
from models import *
from datetime import datetime
from PIL import Image
from apscheduler.schedulers.background import BackgroundScheduler

# Read the swagger.yml file to configure the endpoints
connex_app.add_api("swagger.yml")

# The bucket in which gauge images are stored/uploaded
bucket = 'ocideepgauge-images'

# The default region
region = 'us-east-2'

scheduler = BackgroundScheduler()

default_device_settings = {'type': 'Gauge',
                           'frame_rate': '15',
                           'refresh_rate': '30'
                          }
class GaugeImage:
    def __init__(self):
        self.image_dir = 'static/img'

    def get_local_name(self, device_id):
        return self.image_dir + '/live_device' + str(device_id) + '.png'

    def get_name(self, device_id):
        return '/' + self.get_local_name(device_id)

    def create(self, device_id, size, value):
        background = Image.open(self.image_dir + '/gauge_' + str(size) + '.png')
        needle = Image.open(self.image_dir + '/needle.png')
        needle = needle.rotate(132 - (value * 18))
        background.paste(needle, (0, 0), needle)
        background.save(self.get_local_name(device_id))

    def delete(self, device_id):
        os.remove(self.get_local_name(device_id))

class RemoteDevice:
    def __init__(self):
        self.db = boto3.client('dynamodb')
        self.kinesis = boto3.client('kinesis')
        self.item_name = 'Item'
        self.map_name = 'data'
        self.rate_name = 'rate'

    def get_dynamodb_entry(self, name):
        response = self.db.list_tables()
        tables = response['TableNames']
        for tname in tables:
            if (tname.index('MetaData') >= 0):
                item = self.db.get_item(TableName=tname,
                                        Key={'key': {'S': name}})
                return tname, item
        return None, None

    def get_refresh_rate(self, name):
        rate = 300
        try:
            dbinfo = self.get_dynamodb_entry(name)
            tname = dbinfo[0]
            item = dbinfo[1]
            if tname is not None:
                entry = item[self.item_name][self.map_name]['M']
                if (self.rate_name in entry.keys()):
                    rate = int(entry[self.rate_name]['S'])
        except:
            pass
        return rate

    def set_refresh_rate(self, name, rate):
        try:
            dbinfo = self.get_dynamodb_entry(name)
            tname = dbinfo[0]
            item = dbinfo[1]
            if tname is not None:
                entry = item[self.item_name][self.map_name]['M']
                if (self.rate_name in entry.keys()):
                    entry[self.rate_name]['S'] = str(rate)
                    self.db.put_item(TableName=tname,
                                     Item=item[self.item_name])
        except Exception as err:
            print(err)
            pass
        return rate

    def get_readings(self, name):
        readings = {}
        if name is None or name is "":
          return readings

        try:
            timestamp = datetime.today().strftime('%Y-%m-%dT00:00:00')
            shard_it = self.kinesis.get_shard_iterator(StreamName=name,
                                                       ShardId='shardId-000000000000',
                                                       ShardIteratorType='AT_TIMESTAMP',
                                                       Timestamp=timestamp)['ShardIterator']
            while True:
                out = self.kinesis.get_records(ShardIterator=shard_it)

                for o in out["Records"]:
                    key = o["ApproximateArrivalTimestamp"]
                    jdat = json.loads(o["Data"])
                    value = jdat['id']
                    percent = jdat['score']
                    readings[key] = [value, percent]

                if (out["MillisBehindLatest"] == 0):
                    break
                else:
                    shard_it = out["NextShardIterator"]
        except Exception as err:
          print(err)
          pass

        return readings

    def update_live(self, name):
        if name is None or name is "":
          return [0, 0]

        ## Get reading from Kinesis Data Stream
        value = 0
        percent = 0

        try:
            ## There isn't an easy way to get the last entry in a Kinesis
            ## Data Stream.  So, we are going to iterate over the values for the
            ## day and take the last one we find.
            timestamp = datetime.today().strftime('%Y-%m-%dT00:00:00')
            shard_it = self.kinesis.get_shard_iterator(StreamName=name,
                                                       ShardId='shardId-000000000000',
                                                       ShardIteratorType='AT_TIMESTAMP',
                                                       Timestamp=timestamp)['ShardIterator']
            while True:
                out = self.kinesis.get_records(ShardIterator=shard_it)

                for o in out["Records"]:
                    jdat = json.loads(o["Data"])
                    value = jdat['id']
                    percent = jdat['score']

                if (out["MillisBehindLatest"] == 0):
                    break
                else:
                    shard_it = out["NextShardIterator"]
        except Exception as err:
          print(err)
          pass

        return [value, percent]

    def get_kinesis_streams(self):
        streams = []
        try:
          response = self.kinesis.list_streams()
          for name in response['StreamNames']:
            streams.append(name)
        except Exception as err:
            print(err)
            pass

        return streams

gauge_image = GaugeImage()
remote_device = RemoteDevice()


def pull_reading(device):
    update_device = Device.query.filter(Device.id == device).one_or_none()
    if update_device is None:
        ## If we cannot find the device, there's nothing to do
        return

    ## Get the last reading from the device and create the image
    gauge_size = 15
    name = update_device.name
    values = remote_device.update_live(name)
    gauge_image.create(device, gauge_size, values[0])

    ## Check the thresholds and send an SMS message, if necessary
    message = None
    if (values[0] > update_device.high_threshold):
        message = "{0} reading, {1}, is above {2}".format(update_device.name,
                                                          values[0],
                                                          update_device.high_threshold)
    if (values[0] < update_device.low_threshold):
        message = "{0} reading, {1}, is below {2}".format(update_device.name,
                                                          values[0],
                                                          update_device.low_threshold)
    if (message is not None):
        user = User.query.filter(User.id == update_device.id_user).one_or_none()
        if (user is not None):
            try:
                ## Create an SNS client in the us-east-1 region.
                ## This service is not available in us-east-2.
                client = boto3.client('sns',
                                      region_name='us-east-1')
                client.publish(PhoneNumber=user.cell_number,
                               Message=message)
            except Exception as err:
               print(err)
               pass

    prediction = "psi " + str(values[0])
    accuracy = str(values[1]) + "%"

    schema = ReadingSchema()
    reading = Reading(
        id_device   = device,
        prediction  = prediction,
        accuracy    = accuracy,
        body        = '[{}]'
    )
    db.session.add(reading)
    db.session.commit()

    if update_device is not None:
        update_device.prediction = prediction.replace("_"," ").upper()
        update_device.updated = datetime.today()
        db.session.commit()

def make_database():
    create_initial_device = True

    # Delete database file if it exists currently
    # Keep for running the database locally
    # if os.path.exists("deepgauge.db"):
    #     os.remove("deepgauge.db")

    # Create the database
    db.create_all()

    # Data to initialize database with
    if (create_initial_device):
        dev_name = 'PiCamera'
        d = Device(
            id_user         = 1,
            name            = dev_name,
            image           = '',
            bucket          = "s3://{0}".format(bucket),
            type            = "RaspberryPi",
            location        = "St. Louis",
            prediction      = "PSI 0",
            frame_rate      = default_device_settings['frame_rate'],
            refresh_rate    = remote_device.get_refresh_rate(dev_name),
            notes           = "Camera attached to a RaspberryPi",
            high_threshold  = 15,
            low_threshold   = 0
        )

        db.session.add(d)

    u = User(
        user_name       = "Technician",
        display_name    = "Technician Name",
        cell_number     = "+13145550100",
        company         = "Technicians Company",
        thumbnail       = "https://jobs.centurylink.com/sites/century-link/images/sp-technician-img.jpg"
    )

    db.session.add(u)

    db.session.commit()

    if (create_initial_device):
        ## Once the device is created, the id has been populated
        d.image = gauge_image.get_name(d.id)
        db.session.commit()

        ## This should be done for all real devices.  The device name corresponds
        ## to the name provided during provisioning.
        pull_reading(d.id)
        scheduler.add_job(func=lambda: pull_reading(d.id),
                          trigger="interval", seconds=int(d.refresh_rate),
                          id=str(d.id))

    return True

# Flask lets you create a test request to initialize an app.
with app.test_request_context():
     make_database()

@app.route('/')
def root():
    query = Device.query.order_by(Device.id_user).all()

    # Serialize the data for the response
    schema = DeviceSchema(many=True)
    data = schema.dump(query)
    for idx, d in enumerate(data):
        date_time_obj = datetime.strptime(data[idx]['updated'], '%Y-%m-%dT%H:%M:%S.%f')
        data[idx]['updated'] = date_time_obj.strftime('%B %d, %Y, %H:%M:%S')

    return render_template('dashboard.html', devices=data)


@app.route('/setting', methods=['GET', 'POST'])
def setting():
    query = Setting.query.one_or_none()
    if request.method == 'POST':
        type = request.form.get('device_type')
        frame_rate = request.form.get('frame_rate')
        refresh_rate = request.form.get('refresh_rate')

        ## Store settings in local database
        if query is None:
            settings = Setting(id = 0,
                               id_user = 1,
                               type = type,
                               frame_rate = frame_rate,
                               refresh_rate = refresh_rate,
                               updated = datetime.today()
                              )
            db.session.add(settings)
        else:
            query.type = type
            query.frame_rate = frame_rate
            query.refresh_rate = refresh_rate
            query.updated = datetime.today()

        db.session.commit()
        return redirect('/')
    else:
        ## Query local database to get defaults
        data = default_device_settings
        if query is not None:
            schema = SettingSchema()
            data = schema.dump(query)

        return render_template('setting.html', settings=data)

@app.route('/user', methods=['GET', 'POST'])
def user():
    query = User.query.filter(User.id == 1).one_or_none()

    if request.method == 'POST':
        user_name = request.form.get('user_name')
        display_name = request.form.get('display_name')
        cell_number = request.form.get('cell_number')
        company = request.form.get('company')

        ## Store settings in local database
        if query is None:
            user = User(user_name    = user_name,
                        display_name = display_name,
                        cell_number  = cell_number,
                        company      = company,
                        thumbnail    = '')
            db.session.add(user)
        else:
            query.user_name = user_name
            query.display_name = display_name
            query.cell_number = cell_number
            query.company = company
            query.updated = datetime.today()

        db.session.commit()
        return redirect('/')
    else:
        # Serialize the data for the response
        schema = UserSchema()
        data = schema.dump(query)

        return render_template('user.html', user=data)

@app.route('/device/new')
def new_device():
    ## Get the defaults from the database
    settings = default_device_settings
    query = Setting.query.one_or_none()
    if query is not None:
      settings['frame_rate'] = query.frame_rate
      settings['refresh_rate'] = query.refresh_rate

    # Create a new Device entry
    schema = DeviceSchema()
    device = Device(
        id_user         = 1, #TODO request this from the Flask auth session - not implemented
        name            = "",
        image           = '',
        bucket          = "s3://{0}".format(bucket),
        type            = "Gauge",
        prediction      = "",
        location        = "",  #TODO detect or update value from geo service
        frame_rate      = settings['frame_rate'],
        refresh_rate    = settings['refresh_rate'],
        notes           = "",
        high_threshold  = 15,
        low_threshold   = 0
    )

    # Add the device to the database
    db.session.add(device)
    db.session.commit()

    ## Once the device is created, the id has been populated
    device.image = gauge_image.get_name(device.id)
    device.name = 'Device' + str(device.id)
    db.session.commit()

    ## This should be done for all real devices.  The device name
    ## corresponds to the name provided during provisioning.
    pull_reading(device.id)
    scheduler.add_job(func=lambda: pull_reading(device.id),
                      trigger="interval", seconds=int(device.refresh_rate),
                      id=str(device.id))

    # Redirect to the device page.
    return redirect("/device/setting/{}".format(device.id), code=302)

@app.route('/device/<int:device_id>')
def one_device(device_id):
    query = Device.query.filter(Device.id == device_id).one()

    # Serialize the data for the response
    schema = DeviceSchema()
    data = schema.dump(query)

    ## Pull the readings from the remote device and pass them to the
    ## rendering engine.
    first = True
    rdata = {'date': '',
             'readings': {}}
    readings = remote_device.get_readings(query.name)
    for timestamp in readings:
      if (first):
          first = False
          rdata['date'] = timestamp.strftime('%B %d, %Y')
      key = timestamp.strftime('%H:%M:%S')
      rdata['readings'][key] = str(readings[timestamp][0])

    query_reading = Reading.query.filter(Reading.id_device == device_id).all()
    if query_reading is not None and len(query_reading) > 0:

        # Serialize the data for the response
        schema = ReadingSchema()
        index = len(query_reading) - 1
        reading = schema.dump(query_reading[index])

    # Otherwise, nope, didn't find that reading
    else:
        reading = []

    return render_template('one_device.html',
                           device=data, reading=reading, rdata=rdata)

@app.route('/device/setting/<int:device_id>', methods=['GET', 'POST'])
def show_device_setting(device_id):
    if request.method == 'POST':
        query = Device.query.filter(Device.id == device_id).one_or_none()
        delete = request.form.get('delete')
        if (delete == None):
            ## Save the values in the local database
            name = request.form.get('name')
            type = request.form.get('device_type')
            frame_rate = request.form.get('frame_rate')
            refresh_rate = request.form.get('refresh_rate')
            notes = request.form.get('notes')
            high_threshold = request.form.get('high_threshold')
            low_threshold = request.form.get('low_threshold')

            ## Store settings in local database
            if query is None:
                ## This should never happen
                return 'Invalid Device Id', 417
            else:
                query.name = name
                query.type = type
                query.frame_rate = frame_rate
                query.refresh_rate = refresh_rate
                query.notes = notes
                query.high_threshold = high_threshold
                query.low_threshold = low_threshold
                query.updated = datetime.today()

            db.session.commit()

            # Update the refresh rate in the remote device
            remote_device.set_refresh_rate(query.name, refresh_rate)
            return redirect("/device/{}".format(device_id))
        else:
            gauge_image.delete(device_id)
            scheduler.remove_job(str(device_id))
            if query is not None:
                db.session.delete(query)
                db.session.commit()
            return redirect("/")
    else:
        query = Device.query.filter(Device.id == device_id).one_or_none()

        # Did we find a device?
        if query is None:
            ## This should never happen
            return 'Invalid Device Id', 417
        else:
            # Serialize the data for the response
            schema = DeviceSchema()
            data = schema.dump(query)

        names = remote_device.get_kinesis_streams()
        return render_template('setting_device.html', device=data, names=names)

# [START push]
@app.route('/pubsub/push', methods=['POST'])
def pubsub_push():
    if (request.args.get('token', '') !=
            current_app.config['PUBSUB_VERIFICATION_TOKEN']):
        return 'Invalid request', 400

    envelope = json.loads(request.get_data().decode('utf-8'))
    payload = base64.b64decode(envelope['message']['data'])

    payload_json = payload.decode('utf8').replace("'", '"')
    payload_data = json.loads(payload_json)
    for d in payload_data:
        for cl in d['class_label']:
            prediction = cl
        for ci in d['class_ids']:
            acc = d['probabilities'][ci]*100

    schema = ReadingSchema()
    reading = Reading(
        id_device   = envelope['message']['attributes']['device'],
        prediction  = prediction,
        accuracy    = acc,
        body        = payload_json
    )
    # Add to the database
    db.session.add(reading)
    db.session.commit()

    # Update the Device model with the prediction
    id_device = envelope['message']['attributes']['device']
    update_device = Device.query.filter(Device.id == id_device).one_or_none()

    if update_device is not None:
        update_device.prediction = prediction.replace("_"," ").upper()
        db.session.commit()

    # Serialize and return the newly created person in the response
    data = schema.dump(reading)

    # Returning any 2xx status indicates successful receipt of the message.
    return 'OK', 200
# [END push]


@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


scheduler.start()

#atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True, use_reloader=False)
# [START gae_python37_render_template]
