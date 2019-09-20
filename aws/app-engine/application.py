# [START gae_python37_render_template]
from flask import Flask, Response, request, json, render_template, current_app, redirect
import base64, json, logging, os, boto3, scrypt
from config import db, application, connex_app
from models import *
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from apscheduler.schedulers.background import BackgroundScheduler
from flask_login import LoginManager, login_required, UserMixin, login_user, logout_user, current_user
from ip2geotools.databases.noncommercial import DbIpCity
from digital import Digital
import math
import os.path

# To deploy this on elastic beanstalk, the app needs to be named application.
# But, since this was originally written without AWS in mind, it's referenced
# as app throught this code.
app = application

# Read the swagger.yml file to configure the endpoints
connex_app.add_api("swagger.yml")

## Scheduler to allow polling of the device readings
scheduler = BackgroundScheduler()

## The flask login manager
app.config['SECRET_KEY'] = 'jIikpakjfdia;/jidfoia'
login_manager = LoginManager()
login_manager.init_app(app)

## Default Settings for various parts of the application
default_settings = {
  'bucket': 'ocideepgauge-images',
  'region': 'us-east-2',
  'device': {'type': 'Camera',
             'frame_rate': '15',
             'refresh_rate': '30',
             'dashboard_refresh_rate': '5',
             'gauge_display': 'analog',
            }
}

class ThresholdNotification:
    def __init__(self):
        self.sent = {}

    def send(self, value, device):
        user = User.query.filter(User.id == device.id_user).one_or_none()
        alert = False
        if (user is not None):
            alert = (value > device.high_threshold or value < device.low_threshold)
            if (user.cell_number.strip() and
                (user.id not in self.sent or self.sent[user.id] != value)):
                ## Check the thresholds and send an SMS message, if necessary
                message = None
                if (value > device.high_threshold):
                    message = "{0} reading, {1}, is above {2}".format(device.name,
                                                                      value,
                                                                      device.high_threshold)
                if (value < device.low_threshold):
                    message = "{0} reading, {1}, is below {2}".format(device.name,
                                                                      value,
                                                                      device.low_threshold)
                if (message is not None):
                    try:
                        ## Create an SNS client in the us-east-1 region.
                        ## This service is not available in us-east-2.
                        client = boto3.client('sns',
                                              region_name='us-east-1')
                        client.publish(PhoneNumber=user.cell_number,
                                       Message=message)
                        self.sent[user.id] = value

                        schema = NotificationSchema()
                        notification = Notification(id_user = user.id,
                                                    id_device = device.id,
                                                    text = message) 
                        db.session.add(notification)
                        db.session.commit()
                    except Exception as err:
                       print("ERROR: " + str(err))
                       pass
        return alert

class AppUser(UserMixin):
    def __init__(self, id, display, admin):
        self.id = id
        self.display_name = display
        self.is_admin = admin

    def is_active(self):
        return True

    def get_id(self):
        return self.id

    def get(user_id):
        user = User.query.filter(User.id == user_id).one_or_none()
        if (user is None):
            return None
        else:
            return AppUser(user.id, user.display_name, user.admin)

    def hash_password(password, datalength=64):
        return scrypt.encrypt(os.urandom(datalength), password, maxtime=0.5)

    def verify_password(hashed_password, guessed_password):
        try:
            scrypt.decrypt(hashed_password, guessed_password, encoding=None)
            return True
        except:
            return False

class GaugeImage:
    def __init__(self):
        self.image_dir = 'static/img'
        self.allow_generation = False
        self.digital = False
        self.needle_start = 132
        self.font_offset = 6
        self.arc = 270

    def get_local_name(self, device_id):
        return self.image_dir + '/live_device' + str(device_id) + '.png'

    def get_name(self, device_id):
        return '/' + self.get_local_name(device_id)

    def create_background(self, bname, low, high):
        if (os.path.exists(bname)):
            return Image.open(bname)
        else:
            background = Image.open(self.image_dir + '/gauge.png')
            hw = background.size[0] / 2
            hh = background.size[1] / 2
            draw = ImageDraw.Draw(background)
            font = ImageFont.truetype('Poppins-Regular.ttf', 10)
            for value in range(low, high + 1):
                normalized = abs(value - low)
                radian = ((normalized * self.arc / (abs(high - low) + 1)) +
                         self.needle_start + self.font_offset) * math.pi / 180
                x = int(((hw * 7) / 9) * math.cos(radian)) + hw - 5
                y = int(((hh * 7) / 9) * math.sin(radian)) + hh - 5
                draw.text((x, y), str(value), font=font, fill=(0,0,0))
            background.save(bname)
            return background

    def create(self, device_id, low, high, value, alert_low, alert_high):
        if (self.allow_generation):
            if (self.digital):
                background = Image.open(self.image_dir + '/digital.png')
                if (value == value):
                    text = "{:5.1f}".format(value)
                    tlen = len(text)
                    Digital.height = 46
                    Digital.width = 19 if (tlen <= 5) else int((110 / tlen) - 3)
                    Digital.color = (0,0,0)
                    Digital.line_width = 3
                    Digital.drawNumber(background, 40, 65, text)

                Digital.color = (255,0,0)
                Digital.height = 8
                Digital.width = 4
                Digital.line_width = 1
                Digital.drawNumber(background, 39, 39,
                                   "{:2}".format(alert_high))
                Digital.drawNumber(background, 39, 129,
                                   "{:2}".format(alert_low))
            else:
                ## Check for NaN.
                invalid = (value != value)

                try:
                    ## If it is NaN, we want to have the needle point to
                    ## something below the lowest value, but not too far below.
                    normalized = abs(value - low) if (not invalid) else -.5
                    bname = self.image_dir + '/gauge_{0}-{1}.png'.format(low, high)
                    background = self.create_background(bname, low, high)
                    needle = Image.open(self.image_dir + '/needle.png')
                    needle = needle.rotate(self.needle_start -
                                           (normalized * self.arc / (abs(high - low) + 1)))
                    background.paste(needle, (0, 0), needle)

                    hw = background.size[0] / 2
                    hh = background.size[1] / 2
                    draw = ImageDraw.Draw(background)
                    for value in [ alert_low, alert_high ]:
                        normalized = abs(value - low)
                        angle = ((normalized * self.arc / (abs(high - low) + 1)) +
                                 self.needle_start + self.font_offset)
                        radian = angle * math.pi / 180
                        x = int(hw * math.cos(radian)) + hw
                        y = int(hh * math.sin(radian)) + hh + 1

                        ## Calculate the actual angle based on the x location
                        actual = math.acos((x - hw) / hw) * 180 / math.pi

                        ## Top left
                        if (x < hw and y < hh):
                            xoffset = (180 - actual) / 90
                            lx = x - int(8 * xoffset)
                            ty = y
                            ## For the pieslice angle
                            actual = 360 - actual
                        ## Top right
                        elif (x >= hw and y < hh):
                            xoffset = actual / 90
                            lx = (x - 10) + int(6 * xoffset)
                            ty = y
                            ## For the pieslice angle
                            actual = 360 - actual
                        ## Bottom left
                        elif (x < hw and y >= hh):
                            xoffset = (180 - actual) / 90
                            yoffset = (actual - 90) / 90
                            lx = x + int(2 * xoffset)
                            ty = (y - 10) + int(5 * yoffset)
                        ## Bottom right
                        else:
                            xoffset = actual / 90
                            yoffset = (90 - actual) / 90
                            lx = (x - 10) - int(11 * xoffset)
                            ty = (y - 10) + int(6 * yoffset)

                        rx = lx + 10
                        by = ty + 10
                        draw.pieslice([lx, ty, rx, by], actual - 15,
                                      actual + 15, fill=(255,0,0))
                except Exception as err:
                    print("ERROR: " + err)
                    pass

            background.save(self.get_local_name(device_id))

    def delete(self, device_id):
        try:
            os.remove(self.get_local_name(device_id))
        except:
            pass

class RemoteDevice:
    def __init__(self):
        self.db = boto3.client('dynamodb',
                               region_name=default_settings['region'])
        self.kinesis = boto3.client('kinesis',
                                    region_name=default_settings['region'])
        self.item_name = 'Item'
        self.map_name = 'data'
        self.rate_name = 'rate'
        self.last_reading_time = {}

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
            print("ERROR: " + str(err))
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
          print("ERROR: " + str(err))
          pass

        return readings

    def get_last_reading(self, name):
        value = float('nan')
        percent = 0
        last_time = None

        if name is None or name is "":
          return [value, percent, last_time]

        ## Get reading from Kinesis Data Stream
        try:
            ## There isn't an easy way to get the last entry in a Kinesis
            ## Data Stream.  So, we are going to iterate over the values for the
            ## day and take the last one we find.
            if (name in self.last_reading_time):
                timestamp = self.last_reading_time[name]
            else:
                timestamp = datetime.today().strftime('%Y-%m-%dT00:00:00')
            shard_it = self.kinesis.get_shard_iterator(StreamName=name,
                                                       ShardId='shardId-000000000000',
                                                       ShardIteratorType='AT_TIMESTAMP',
                                                       Timestamp=timestamp)['ShardIterator']
            while True:
                out = self.kinesis.get_records(ShardIterator=shard_it)

                for o in out["Records"]:
                    self.last_reading_time[name] = o["ApproximateArrivalTimestamp"]
                    last_time = o["ApproximateArrivalTimestamp"]
                    jdat = json.loads(o["Data"])
                    value = jdat['id']
                    percent = jdat['score']

                if (out["MillisBehindLatest"] == 0):
                    break
                else:
                    shard_it = out["NextShardIterator"]
        except Exception as err:
          print("ERROR: " + str(err))
          pass

        return [value, percent, last_time]

    def get_kinesis_streams(self):
        streams = []
        try:
          response = self.kinesis.list_streams()
          for name in response['StreamNames']:
            streams.append(name)
        except Exception as err:
            print("ERROR: " + str(err))
            pass

        return streams

gauge_image = GaugeImage()
remote_device = RemoteDevice()
notifier = ThresholdNotification()

def pull_reading(device):
    update_device = Device.query.filter(Device.id == device).one_or_none()
    if update_device is None:
        ## If we cannot find the device, there's nothing to do
        return None

    ## Get the last reading from the device and create the image
    gauge_low = update_device.minimum
    gauge_high = update_device.maximum
    name = update_device.name
    values = remote_device.get_last_reading(name)
    gauge_image.create(device, gauge_low, gauge_high, values[0],
                       update_device.low_threshold,update_device.high_threshold)

    ## Check the thresholds and send an SMS message, if necessary
    alert = notifier.send(values[0], update_device)

    if (values[0] != values[0]):
        prediction = "UNDETERMINED"
    else:
        prediction = str(values[0]) + " " + update_device.units
    accuracy = str(values[1]) + "%"

    schema = ReadingSchema()
    reading = Reading(
        id_device   = device,
        prediction  = prediction,
        accuracy    = accuracy,
        alert       = alert,
        body        = '[{}]',
        timestamp   = values[2]
    )
    db.session.add(reading)
    db.session.commit()

    update_device.prediction = prediction
    update_device.updated = datetime.today()
    db.session.commit()

    ## Return time time of the last reading (could be None)
    return values[2]

def schedule_device(device, delete_image):
    ## Pull the reading from the device
    if (delete_image):
        gauge_image.delete(device.id)
    last_time = pull_reading(device.id)

    if (last_time is None):
        next_start = datetime.now() + timedelta(seconds=int(device.refresh_rate))
    else:
        ## Calculate the next job start time based on the last reading from
        ## the device (with a 5 second buffer).  Including a timezone on the
        ## next_start_time seems to cause issues with apscheduler when the
        ## trigger occurs.
        current_time = datetime.now()
        next_start = datetime(current_time.year, current_time.month,
                              current_time.day, current_time.hour,
                              last_time.minute, last_time.second) + timedelta(seconds=5)
        while(next_start <= current_time):
            next_start = next_start + timedelta(seconds=int(device.refresh_rate))

    if (scheduler.get_job(device.name) is not None):
        scheduler.remove_job(device.name)
    scheduler.add_job(func=lambda: pull_reading(device.id),
                      trigger="interval", seconds=int(device.refresh_rate),
                      next_run_time=next_start, id=device.name)

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
            bucket          = "s3://{0}".format(default_settings['bucket']),
            type            = "RaspberryPi",
            location        = "St. Louis",
            prediction      = "UNDETERMINED",
            frame_rate      = default_settings['device']['frame_rate'],
            refresh_rate    = remote_device.get_refresh_rate(dev_name),
            notes           = "Camera attached to a RaspberryPi",
            high_threshold  = 15,
            low_threshold   = 0,
            maximum         = 15,
            minimum         = 0,
            units           = "psi"
        )

        db.session.add(d)

    u = User(
        admin        = True,
        user_name    = "technician",
        password     = AppUser.hash_password('123'),
        display_name = "Technician Name",
        cell_number  = "+13145550100",
        company      = "Technicians Company",
        thumbnail    = "https://jobs.centurylink.com/sites/century-link/images/sp-technician-img.jpg"
    )

    db.session.add(u)
    db.session.commit()

    if (create_initial_device):
        ## Once the device is created, the id has been populated
        d.image = gauge_image.get_name(d.id)
        db.session.commit()

        schedule_device(d, True)

    return True

# Flask lets you create a test request to initialize an app.
with app.test_request_context():
     make_database()

def get_current_user_settings():
    settings = default_settings['device']
    query = Setting.query.filter(Setting.id_user == current_user.get_id()).one_or_none()
    if query is not None:
        schema = SettingSchema()
        settings = schema.dump(query)
    return settings

@login_manager.user_loader
def load_user(user_id):
    loaded = AppUser.get(user_id)
    gauge_image.allow_generation = (loaded is not None)
    return loaded

auto_login_primary_user = False
@app.route('/')
def root():
    global auto_login_primary_user
    if (auto_login_primary_user):
        auto_login_primary_user = False
        login_user(AppUser.get(1))
        gauge_image.allow_generation = True

    settings = get_current_user_settings()
    gauge_image.digital = (settings['gauge_display'] == 'digital')
    query = Device.query.filter(Device.id_user == current_user.get_id()).order_by(Device.id)

    # Serialize the data for the response
    schema = DeviceSchema(many=True)
    data = schema.dump(query)
    for idx, d in enumerate(data):
        date_time_obj = datetime.strptime(data[idx]['updated'], '%Y-%m-%dT%H:%M:%S.%f')
        data[idx]['updated'] = date_time_obj.strftime('%B %d, %Y, %H:%M:%S')

    return render_template('dashboard.html', devices=data, settings=settings)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_name = request.form['user_name']
        password = request.form['password']

        query = User.query.filter(User.user_name == user_name).one_or_none()
        if (query is None or not AppUser.verify_password(query.password, password)):
            return render_template('login.html',
                                   message='Unknown user or incorrect password')

        login_user(AppUser(query.id, query.display_name, query.admin))
        gauge_image.allow_generation = True

        query = Device.query.filter(Device.id_user == current_user.get_id()).all()
        for device in query:
            schedule_device(device, False)

        return redirect('/')
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    gauge_image.allow_generation = False
    return redirect('/')

@app.route('/setting', methods=['GET', 'POST'])
@login_required
def setting():
    query = Setting.query.filter(Setting.id_user == current_user.get_id()).one_or_none()
    if request.method == 'POST':
        type = request.form.get('device_type')
        frame_rate = request.form.get('frame_rate')
        refresh_rate = request.form.get('refresh_rate')
        dashboard_refresh_rate = request.form.get('dashboard_refresh_rate')
        gauge_display = request.form.get('gauge_display')

        current_display = query.gauge_display if (query is not None) else default_settings['device']['gauge_display']
        if (current_display != gauge_display):
            devs = Device.query.filter(Device.id_user == current_user.get_id())
            for dev in devs:
                gauge_image.delete(dev.id)

        ## Store settings in local database
        if query is None:
            settings = Setting(id_user = current_user.get_id(),
                               type = type,
                               frame_rate = frame_rate,
                               refresh_rate = refresh_rate,
                               dashboard_refresh_rate = dashboard_refresh_rate,
                               gauge_display = gauge_display,
                               updated = datetime.today()
                              )
            db.session.add(settings)
        else:
            query.type = type
            query.frame_rate = frame_rate
            query.refresh_rate = refresh_rate
            query.dashboard_refresh_rate = dashboard_refresh_rate
            query.gauge_display = gauge_display
            query.updated = datetime.today()

        db.session.commit()
        return redirect('/')
    else:
        ## Query local database to get defaults
        data = default_settings['device']
        if query is not None:
            schema = SettingSchema()
            data = schema.dump(query)

        return render_template('setting.html', settings=data)

@app.route('/user', methods=['GET', 'POST'])
@login_required
def user():
    query = User.query.filter(User.id == current_user.get_id()).one_or_none()

    if request.method == 'POST':
        user_name = request.form.get('user_name')
        display_name = request.form.get('display_name')
        cell_number = request.form.get('cell_number')
        company = request.form.get('company')

        ## Store settings in local database
        if query is None:
            ## This is an error.  We can't modify the user settings
            ## if the user doesn't exist.
            return 'Invalid User Id', 417
        else:
            query.user_name = user_name
            query.display_name = display_name
            query.cell_number = cell_number
            query.company = company
            query.updated = datetime.today()

            db.session.commit()
            return redirect('/')
    else:
        ## Serialize the data for the response.  We need to empty the
        ## password because it will not serialize (and we don't need it).
        schema = UserSchema()
        query.password = ''
        data = schema.dump(query)

        return render_template('user.html', user=data)

@app.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    data = {}
    message = None

    if request.method == 'POST':
        user_name = request.form.get('user_name')
        password = request.form.get('password')
        display_name = request.form.get('display_name')
        cell_number = request.form.get('cell_number')
        company = request.form.get('company')

        user = User(user_name    = user_name,
                    password     = '',
                    display_name = display_name,
                    cell_number  = cell_number,
                    company      = company,
                    thumbnail    = '')

        schema = UserSchema()
        data = schema.dump(user)

        ## Require a minimum of 8 characters
        if (len(password) < 8):
            ## This is an invalid password
            message = "Please choose a password with a minimum of 8 characters"
        else:
            ## Store settings in local database
            query = User.query.filter(User.user_name == user_name).one_or_none()
            if query is None:
                user.password = AppUser.hash_password(password)
                db.session.add(user)
                db.session.commit()
                return redirect('/')
            else:
                ## This user already exists
                message = "That user already exists!"

    return render_template('user.html',
                           user=data, message=message, adding=True)

@app.route('/device/new')
@login_required
def new_device():
    ## Get the defaults from the database
    settings = get_current_user_settings()

    ## Get the location of the caller
    city = ''
    try:
        if (len(request.access_route) > 0):
            location = DbIpCity.get(request.access_route[0], api_key='free')
            city = location.city
    except:
        pass

    # Create a new Device entry
    schema = DeviceSchema()
    device = Device(
        id_user         = current_user.get_id(),
        name            = "",
        image           = '',
        bucket          = "s3://{0}".format(default_settings['bucket']),
        type            = default_settings['device']['type'],
        prediction      = "",
        location        = city,
        frame_rate      = settings['frame_rate'],
        refresh_rate    = settings['refresh_rate'],
        notes           = "",
        high_threshold  = 15,
        low_threshold   = 0,
        maximum         = 15,
        minimum         = 0,
        units           = ""
    )

    # Add the device to the database
    db.session.add(device)
    db.session.commit()

    ## Once the device is created, the id has been populated
    device.image = gauge_image.get_name(device.id)
    device.name = 'Device' + str(device.id)
    db.session.commit()

    ## Delete the image (if it exists) and schedule the device to be polled
    schedule_device(device, True)

    # Redirect to the device page.
    return redirect("/device/setting/{}".format(device.id), code=302)

@app.route('/device/<int:device_id>')
@login_required
def one_device(device_id):
    query = Device.query.filter(Device.id == device_id).one()

    # Serialize the data for the response
    schema = DeviceSchema()
    data = schema.dump(query)

    ## Pull the readings from the remote device and pass them to the
    ## rendering engine.
    first = True
    rdata = {'date': '',
             'units': query.units,
             'readings': {}}
    readings = remote_device.get_readings(query.name)
    for timestamp in readings:
      if (first):
          first = False
          rdata['date'] = timestamp.strftime('%B %d, %Y')
      key = timestamp.strftime('%H:%M:%S')
      rdata['readings'][key] = [str(readings[timestamp][0]), False]

    query_reading = Reading.query.filter(Reading.id_device == device_id).all()
    if query_reading is not None and len(query_reading) > 0:
        ## Look for alert level readings set the flag to True
        for r in query_reading:
          if (r.alert and key in rdata['readings']):
              key = r.timestamp.strftime('%H:%M:%S')
              rdata['readings'][key][1] = True

        # Serialize the data for the response
        schema = ReadingSchema()
        index = len(query_reading) - 1
        reading = schema.dump(query_reading[index])

    # Otherwise, nope, didn't find that reading
    else:
        reading = []

    messages = []
    notifications = Notification.query.filter(Notification.id_user == current_user.get_id() and Notification.id_device == device_id).all()
    for notification in notifications:
        ## This if check shouldn't be necessary, but the query filter doesn't
        ## seem to filter out notifications for other devices
        if (notification.id_device == device_id):
          messages.append(notification.updated.strftime('%Y-%m-%dT%H:%M:%S') +
                          ': ' + notification.text)

    ## Adjust the image name so that we force the browser to not use
    ## the cache to load the image
    data['image'] = data['image'] + "?load=" + datetime.today().strftime('%Y-%m-%dT%H:%M:%S')

    return render_template('one_device.html',
                           device=data, reading=reading, rdata=rdata,
                           messages=messages)

@app.route('/device/setting/<int:device_id>', methods=['GET', 'POST'])
@login_required
def show_device_setting(device_id):
    if request.method == 'POST':
        query = Device.query.filter(Device.id == device_id).one_or_none()
        delete = request.form.get('delete')
        if (delete == None):
            rebuild_image = False

            ## Save the values in the local database
            name = request.form.get('name')
            type = request.form.get('device_type')
            frame_rate = request.form.get('frame_rate')
            refresh_rate = request.form.get('refresh_rate')
            notes = request.form.get('notes')
            high_threshold = request.form.get('high_threshold')
            low_threshold = request.form.get('low_threshold')
            maximum = request.form.get('maximum')
            minimum = request.form.get('minimum')
            units = request.form.get('units')

            ## Store settings in local database
            if query is None:
                ## This should never happen
                return 'Invalid Device Id', 417
            else:
                ## Fix user input in case they inverted the lows and highs
                if (float(minimum) > float(maximum)):
                    mtmp = maximum
                    maximum = minimum
                    minimum = mtmp
                if (float(low_threshold) > float(high_threshold)):
                    ttmp = high_threshold
                    high_threshold = low_threshold
                    low_threshold = ttmp
                if (float(low_threshold) < float(minimum)):
                    low_threshold = minimum
                if (float(high_threshold) > float(maximum)):
                    high_threshold = maximum
                rebuild_image = (query.high_threshold != high_threshold or
                                 query.low_threshold != low_threshold or
                                 query.maximum != maximum or
                                 query.minimum != minimum)
                query.name = name
                query.type = type
                query.frame_rate = frame_rate
                query.refresh_rate = refresh_rate
                query.notes = notes
                query.high_threshold = high_threshold
                query.low_threshold = low_threshold
                query.maximum = maximum
                query.minimum = minimum
                query.units = units
                query.updated = datetime.today()

            db.session.commit()

            ## Update the refresh rate in the remote device and reschedule
            ## the device just in case the refresh rate has changed.
            remote_device.set_refresh_rate(query.name, refresh_rate)
            schedule_device(query, rebuild_image)

            return redirect("/device/{}".format(device_id))
        else:
            gauge_image.delete(device_id)
            if query is not None:
                if (scheduler.get_job(query.name) is not None):
                    scheduler.remove_job(query.name)
                db.session.delete(query)
                db.session.commit()
            return redirect('/')
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

        ## Adjust the image name so that we force the browser to not use
        ## the cache to load the image
        data['image'] = data['image'] + "?load=" + datetime.today().strftime('%Y-%m-%dT%H:%M:%S')

        names = remote_device.get_kinesis_streams()
        return render_template('setting_device.html', device=data, names=names)

@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


scheduler.start()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True, use_reloader=False)
# [START gae_python37_render_template]
