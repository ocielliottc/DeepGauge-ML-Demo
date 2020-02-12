import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

basedir = os.path.abspath(os.path.dirname(__file__))

# Get the underlying Flask app instance
application = Flask(__name__)

# Build the Sqlite ULR for SqlAlchemy
# sqlite_url = "sqlite:////" + os.path.join(basedir, "deepgauge.db")
sqlite_url = "sqlite:///:memory:"



# Configure the SqlAlchemy part of the app instance
application.config["SQLALCHEMY_ECHO"] = False
application.config["SQLALCHEMY_DATABASE_URI"] = sqlite_url
application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
application.config['PROJECT'] = "dashboard"

# Create the SqlAlchemy db instance
db = SQLAlchemy(application)

# Initialize Marshmallow
ma = Marshmallow(application)
